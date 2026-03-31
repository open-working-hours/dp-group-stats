"""
DP Group Stats — Aggregation Simulation

Simulates differential-privacy aggregation over realistic synthetic data
to determine optimal epsilon, K_MIN, split, dominance threshold, and temporal
resolution parameters.

Distribution modes:
  --spread      Nationwide (default for --sweep)
  --pilot       Concentrated single-hospital (Berlin)
  --hospital    Hospital-level cells (no specialty split)

Temporal resolution:
  --period weekly|biweekly|monthly
  --dynamic     Adaptive schedule: monthly->biweekly->weekly over the year
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from dataclasses import dataclass, field
from random import Random

from .config import ContributionBounds
from .mechanisms import laplace_noise
from .policy import PublicationStatus, get_publication_status

__all__ = [
    "SimUser",
    "CellState",
    "PeriodMetrics",
    "ScenarioResult",
    "build_schedule",
    "create_users",
    "generate_hours",
    "run_scenario",
    "main",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPECIALTIES = [
    ("internal_medicine", 0.25),
    ("surgery", 0.20),
    ("cardiology", 0.15),
    ("pediatrics", 0.15),
    ("anesthesiology", 0.15),
    ("radiology", 0.10),
]

STATE_HOSPITALS: dict[str, int] = {
    "NW": 202, "BY": 193, "BW": 147, "NI": 136, "HE": 104,
    "SH": 61, "RP": 56, "ST": 49, "BE": 48, "SN": 43,
    "MV": 43, "TH": 40, "HH": 35, "BB": 30, "SL": 20, "HB": 11,
}

TOTAL_HOSPITALS = sum(STATE_HOSPITALS.values())
STATE_WEIGHTS = {s: c / TOTAL_HOSPITALS for s, c in STATE_HOSPITALS.items()}

PILOT_SPECIALTIES = [
    ("internal_medicine", 0.30),
    ("surgery", 0.25),
    ("cardiology", 0.20),
    ("anesthesiology", 0.15),
    ("radiology", 0.10),
]

BOUNDS = ContributionBounds()

# ---------------------------------------------------------------------------
# Dynamic schedule: builds list of (period_weeks, n_sim_weeks) segments
# ---------------------------------------------------------------------------

PERIOD_WEEKS = {"weekly": 1, "biweekly": 2, "monthly": 4}


def build_schedule(period: str, n_weeks: int, dynamic: bool) -> list[int]:
    """Return a list of period lengths (in weeks) for each aggregation period.

    For static modes: all periods have the same length.
    For dynamic mode (52 weeks):
      - Weeks 1-8:   monthly  (2 periods of 4 weeks)
      - Weeks 9-20:  biweekly (6 periods of 2 weeks)
      - Weeks 21-52: weekly   (32 periods of 1 week)
    Total: 40 periods, spending cap across fewer early periods.
    """
    if not dynamic:
        pw = PERIOD_WEEKS[period]
        return [pw] * (n_weeks // pw)

    # Dynamic: monthly(8w) -> biweekly(12w) -> weekly(remaining)
    schedule: list[int] = []
    used = 0

    # Phase 1: monthly (weeks 1-8)
    monthly_weeks = min(8, n_weeks)
    for _ in range(monthly_weeks // 4):
        schedule.append(4)
    used += (monthly_weeks // 4) * 4

    # Phase 2: biweekly (next 12 weeks)
    biweekly_weeks = min(12, n_weeks - used)
    for _ in range(biweekly_weeks // 2):
        schedule.append(2)
    used += (biweekly_weeks // 2) * 2

    # Phase 3: weekly (remaining)
    remaining = n_weeks - used
    for _ in range(remaining):
        schedule.append(1)

    return schedule


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SimUser:
    """A synthetic user with a fixed state, specialty, and overtime profile."""
    user_id: int
    state: str
    specialty: str
    is_high_overtime: bool
    cumulative_epsilon: float = 0.0


@dataclass
class CellState:
    """Tracks publication-status streaks for one (state, specialty) cell."""
    was_active: bool = False
    consecutive_eligible: int = 0
    consecutive_ineligible: int = 0


@dataclass
class PeriodMetrics:
    """Aggregated metrics for one simulation period (noise errors, cell counts)."""
    period: int = 0
    period_weeks: int = 1
    total_cells: int = 0
    published_cells: int = 0
    cooling_down_cells: int = 0
    warming_up_cells: int = 0
    suppressed_cells: int = 0
    dominance_suppressed: int = 0
    absolute_errors_planned: list[float] = field(default_factory=list)
    absolute_errors_actual: list[float] = field(default_factory=list)
    noise_stds_planned: list[float] = field(default_factory=list)
    noise_stds_actual: list[float] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Summary output of a single simulation run (publication rates, errors, budget)."""
    label: str = ""
    users: int = 0
    epsilon: float = 0.0
    split_planned: float = 0.0
    split_actual: float = 0.0
    dominance: float = 0.0
    k_min: int = 11
    period: str = "weekly"
    # Mid-point metrics
    pub_pct_mid: float = 0.0
    mae_planned_mid: float = 0.0
    mae_actual_mid: float = 0.0
    # End metrics
    pub_pct_end: float = 0.0
    mae_planned_end: float = 0.0
    mae_actual_end: float = 0.0
    dominance_suppressed_pct_end: float = 0.0
    noise_lt_3h_pct: float = 0.0
    noise_lt_5h_pct: float = 0.0
    # Budget
    min_user_epsilon: float = 0.0
    mean_user_epsilon: float = 0.0
    median_user_epsilon: float = 0.0
    max_user_epsilon: float = 0.0
    n_periods: int = 0


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------


def weighted_choice(rng: Random, weights: dict[str, float]) -> str:
    keys = list(weights.keys())
    vals = [weights[k] for k in keys]
    total = sum(vals)
    r = rng.random() * total
    cumulative = 0.0
    for k, v in zip(keys, vals):
        cumulative += v
        if r <= cumulative:
            return k
    return keys[-1]


def pick_specialty(rng: Random, specialties: list[tuple[str, float]] | None = None) -> str:
    specs = specialties or SPECIALTIES
    r = rng.random()
    cumulative = 0.0
    for name, prob in specs:
        cumulative += prob
        if r <= cumulative:
            return name
    return specs[-1][0]


def create_users(n_users: int, rng: Random, pilot: bool = False) -> list[SimUser]:
    """Generate *n_users* synthetic users distributed across states and specialties."""
    users = []
    for i in range(n_users):
        if pilot:
            state = "BE"
            specialty = pick_specialty(rng, PILOT_SPECIALTIES)
        else:
            state = weighted_choice(rng, STATE_WEIGHTS)
            specialty = pick_specialty(rng)
        is_high = rng.random() < 0.05
        users.append(SimUser(user_id=i, state=state, specialty=specialty, is_high_overtime=is_high))
    return users


def generate_hours(user: SimUser, rng: Random) -> tuple[float, float]:
    """Return (planned, actual) clipped hours for a single week."""
    planned = rng.gauss(39.0, 3.0)
    planned = BOUNDS.clip_planned(planned)
    if user.is_high_overtime:
        overtime = rng.expovariate(1.0 / 15.0)
    else:
        overtime = rng.expovariate(1.0 / 5.0)
    actual = planned + overtime
    actual = BOUNDS.clip_actual(actual)
    return planned, actual


# ---------------------------------------------------------------------------
# Cell key function
# ---------------------------------------------------------------------------


def cell_key_fn(user: SimUser, hospital_level: bool) -> tuple[str, str]:
    """Return the cell grouping key for a user.

    hospital_level=False: (state, specialty) -- default
    hospital_level=True:  (state, "_hospital") -- single cell per hospital/state
    """
    if hospital_level:
        return (user.state, "_hospital")
    return (user.state, user.specialty)


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------


def run_scenario(
    n_users: int,
    epsilon: float,
    split_planned_ratio: float,
    dominance_threshold: float,
    seed: int,
    n_weeks: int = 52,
    k_min: int = 11,
    activation_weeks: int = 2,
    deactivation_grace_weeks: int = 2,
    pilot: bool = False,
    period: str = "weekly",
    dynamic: bool = False,
    hospital_level: bool = False,
    annual_cap: float | None = None,
) -> ScenarioResult:
    """Run a full DP aggregation simulation and return summary metrics."""
    rng = Random(seed)

    schedule = build_schedule(period, n_weeks, dynamic)
    n_periods = len(schedule)

    # If annual_cap is set, compute epsilon per period = cap / n_periods
    if annual_cap is not None:
        epsilon = annual_cap / n_periods

    eps_planned = epsilon * split_planned_ratio
    eps_actual = epsilon * (1.0 - split_planned_ratio)

    users = create_users(n_users, rng, pilot=pilot)
    next_user_id = n_users

    cell_states: dict[tuple[str, str], CellState] = {}
    user_epsilon: dict[int, float] = {u.user_id: 0.0 for u in users}
    all_period_metrics: dict[int, PeriodMetrics] = {}

    for p_idx, period_weeks in enumerate(schedule):
        p = p_idx + 1

        # Accumulate data: cell -> user_id -> [planned_sum, actual_sum, n_weeks]
        cell_accum: dict[tuple[str, str], dict[int, list[float]]] = {}

        for w in range(period_weeks):
            # Churn
            n_leave = max(1, int(len(users) * 0.02))
            if n_leave < len(users):
                rng.shuffle(users)
                users = users[n_leave:]

            n_join = max(1, int(n_users * 0.01))
            for _ in range(n_join):
                if pilot:
                    state = "BE"
                    specialty = pick_specialty(rng, PILOT_SPECIALTIES)
                else:
                    state = weighted_choice(rng, STATE_WEIGHTS)
                    specialty = pick_specialty(rng)
                is_high = rng.random() < 0.05
                new_user = SimUser(user_id=next_user_id, state=state, specialty=specialty, is_high_overtime=is_high)
                users.append(new_user)
                user_epsilon[new_user.user_id] = 0.0
                next_user_id += 1

            for u in users:
                planned, actual = generate_hours(u, rng)
                key = cell_key_fn(u, hospital_level)
                if key not in cell_accum:
                    cell_accum[key] = {}
                if u.user_id not in cell_accum[key]:
                    cell_accum[key][u.user_id] = [0.0, 0.0, 0]
                cell_accum[key][u.user_id][0] += planned
                cell_accum[key][u.user_id][1] += actual
                cell_accum[key][u.user_id][2] += 1

        # Aggregate per-user averages
        cell_data: dict[tuple[str, str], list[tuple[int, float, float]]] = {}
        for ck, user_data in cell_accum.items():
            records = []
            for uid, (p_sum, a_sum, n_w) in user_data.items():
                records.append((uid, p_sum / n_w, a_sum / n_w))
            cell_data[ck] = records

        metrics = PeriodMetrics(period=p, period_weeks=period_weeks)
        all_cells = set(cell_states.keys()) | set(cell_data.keys())
        metrics.total_cells = len(all_cells)

        for ck in all_cells:
            records = cell_data.get(ck, [])
            n = len(records)

            if ck not in cell_states:
                cell_states[ck] = CellState()
            cs = cell_states[ck]

            passes_k_min = n >= k_min
            passes_dominance = True
            dominance_fail = False
            if n > 0:
                total_actual = sum(r[2] for r in records)
                if total_actual > 0:
                    max_actual = max(r[2] for r in records)
                    if max_actual / total_actual > dominance_threshold:
                        passes_dominance = False
                        dominance_fail = True

            eligible = passes_k_min and passes_dominance

            if eligible:
                cs.consecutive_eligible += 1
                cs.consecutive_ineligible = 0
            else:
                cs.consecutive_ineligible += 1
                cs.consecutive_eligible = 0

            status = get_publication_status(
                was_active=cs.was_active,
                consecutive_eligible=cs.consecutive_eligible,
                consecutive_ineligible=cs.consecutive_ineligible,
                activation_weeks=activation_weeks,
                deactivation_grace_weeks=deactivation_grace_weeks,
            )

            if status == PublicationStatus.published:
                metrics.published_cells += 1
            elif status == PublicationStatus.cooling_down:
                metrics.cooling_down_cells += 1
            elif status == PublicationStatus.warming_up:
                metrics.warming_up_cells += 1
            else:
                metrics.suppressed_cells += 1
                if passes_k_min and dominance_fail:
                    metrics.dominance_suppressed += 1

            cs.was_active = status in (PublicationStatus.published, PublicationStatus.cooling_down)

            if status in (PublicationStatus.published, PublicationStatus.cooling_down) and n > 0:
                sens_planned = (BOUNDS.planned_weekly_max - BOUNDS.planned_weekly_min) / n
                sens_actual = (BOUNDS.actual_weekly_max - BOUNDS.actual_weekly_min) / n

                noise_p = laplace_noise(eps_planned, sens_planned, rng)
                noise_a = laplace_noise(eps_actual, sens_actual, rng)

                metrics.absolute_errors_planned.append(abs(noise_p))
                metrics.absolute_errors_actual.append(abs(noise_a))

                scale_p = sens_planned / eps_planned
                scale_a = sens_actual / eps_actual
                metrics.noise_stds_planned.append(scale_p * math.sqrt(2))
                metrics.noise_stds_actual.append(scale_a * math.sqrt(2))

                for uid, _, _ in records:
                    user_epsilon[uid] = user_epsilon.get(uid, 0.0) + epsilon

        all_period_metrics[p] = metrics

    # --- Compile results ---
    label_parts = []
    if pilot:
        label_parts.append("pilot")
    else:
        label_parts.append("spread")
    if hospital_level:
        label_parts.append("hosp")
    if dynamic:
        label_parts.append("dyn")
    label = "+".join(label_parts)

    period_label = "dynamic" if dynamic else period
    result = ScenarioResult(
        label=label,
        users=n_users,
        epsilon=epsilon,
        split_planned=split_planned_ratio,
        split_actual=1.0 - split_planned_ratio,
        dominance=dominance_threshold,
        k_min=k_min,
        period=period_label,
        n_periods=n_periods,
    )

    mid = n_periods // 2
    for tag, pidx in [("mid", mid), ("end", n_periods)]:
        m = all_period_metrics.get(pidx)
        if not m or m.total_cells == 0:
            continue

        pub_pct = (m.published_cells / m.total_cells) * 100
        mae_p = sum(m.absolute_errors_planned) / len(m.absolute_errors_planned) if m.absolute_errors_planned else 0.0
        mae_a = sum(m.absolute_errors_actual) / len(m.absolute_errors_actual) if m.absolute_errors_actual else 0.0

        if tag == "mid":
            result.pub_pct_mid = pub_pct
            result.mae_planned_mid = mae_p
            result.mae_actual_mid = mae_a
        else:
            result.pub_pct_end = pub_pct
            result.mae_planned_end = mae_p
            result.mae_actual_end = mae_a
            result.dominance_suppressed_pct_end = (m.dominance_suppressed / m.total_cells) * 100
            if m.noise_stds_actual:
                n_pub = len(m.noise_stds_actual)
                result.noise_lt_3h_pct = sum(1 for s in m.noise_stds_actual if s < 3.0) / n_pub * 100
                result.noise_lt_5h_pct = sum(1 for s in m.noise_stds_actual if s < 5.0) / n_pub * 100

    active_ids = {u.user_id for u in users}
    active_epsilons = sorted(user_epsilon.get(uid, 0.0) for uid in active_ids if user_epsilon.get(uid, 0.0) > 0)
    if active_epsilons:
        result.min_user_epsilon = active_epsilons[0]
        result.mean_user_epsilon = sum(active_epsilons) / len(active_epsilons)
        result.median_user_epsilon = active_epsilons[len(active_epsilons) // 2]
        result.max_user_epsilon = active_epsilons[-1]

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

HEADER = [
    "mode", "users", "k_min", "period", "n_per", "epsilon", "split", "dom",
    "pub%_mid", "pub%_end",
    "MAE_pln", "MAE_act",
    "dom_s%", "<3h%", "<5h%",
    "max_eps/yr",
]


def result_to_row(r: ScenarioResult) -> list[str]:
    split_str = f"{r.split_planned:.1f}/{r.split_actual:.1f}"
    p_short = {"weekly": "w", "biweekly": "bw", "monthly": "m", "dynamic": "dyn"}.get(r.period, r.period[:3])
    return [
        r.label,
        str(r.users),
        str(r.k_min),
        p_short,
        str(r.n_periods),
        f"{r.epsilon:.1f}",
        split_str,
        f"{r.dominance:.2f}",
        f"{r.pub_pct_mid:.1f}",
        f"{r.pub_pct_end:.1f}",
        f"{r.mae_planned_end:.2f}",
        f"{r.mae_actual_end:.2f}",
        f"{r.dominance_suppressed_pct_end:.1f}",
        f"{r.noise_lt_3h_pct:.1f}",
        f"{r.noise_lt_5h_pct:.1f}",
        f"{r.max_user_epsilon:.1f}",
    ]


def print_results(results: list[ScenarioResult]) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    for r in results:
        writer.writerow(result_to_row(r))
    print(buf.getvalue(), end="")


def print_results_table(results: list[ScenarioResult]) -> None:
    rows = [HEADER] + [result_to_row(r) for r in results]
    col_widths = [max(len(row[i]) for row in rows) for i in range(len(HEADER))]

    def fmt_row(row: list[str]) -> str:
        return " | ".join(val.rjust(w) for val, w in zip(row, col_widths))

    print(fmt_row(rows[0]))
    print("-+-".join("-" * w for w in col_widths))
    for row in rows[1:]:
        print(fmt_row(row))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate DP group stats aggregation")
    parser.add_argument("--users", type=int, default=2000)
    parser.add_argument("--epsilon", type=float, default=1.0)
    parser.add_argument("--annual-cap", type=float, default=None, help="Annual epsilon cap (overrides --epsilon, sets eps=cap/n_periods)")
    parser.add_argument("--split", type=float, default=0.3)
    parser.add_argument("--dominance", type=float, default=0.30)
    parser.add_argument("--k-min", type=int, default=11)
    parser.add_argument("--weeks", type=int, default=52)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--period", choices=["weekly", "biweekly", "monthly"], default="weekly")
    parser.add_argument("--dynamic", action="store_true", help="Dynamic schedule: monthly->biweekly->weekly")
    parser.add_argument("--pilot", action="store_true", help="Berlin single-hospital scenario")
    parser.add_argument("--hospital", action="store_true", help="Hospital-level cells (no specialty split)")
    parser.add_argument("--sweep", action="store_true", help="Full spread sweep")
    parser.add_argument("--sweep-pilot", action="store_true", help="Pilot sweep")
    parser.add_argument("--sweep-dynamic", action="store_true", help="Compare static vs dynamic schedules")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")

    args = parser.parse_args()

    if args.sweep:
        _run_spread_sweep(args)
    elif args.sweep_pilot:
        _run_pilot_sweep(args)
    elif args.sweep_dynamic:
        _run_dynamic_sweep(args)
    else:
        _run_single(args)


def _run_single(args: argparse.Namespace) -> None:
    mode = "pilot" if args.pilot else "spread"
    sched = "dynamic" if args.dynamic else args.period
    print(
        f"Running: {mode}, users={args.users}, eps={args.epsilon}, "
        f"cap={args.annual_cap}, k_min={args.k_min}, period={sched}, "
        f"hospital={args.hospital}, seed={args.seed}\n",
        file=sys.stderr,
    )

    r = run_scenario(
        n_users=args.users,
        epsilon=args.epsilon,
        split_planned_ratio=args.split,
        dominance_threshold=args.dominance,
        seed=args.seed,
        n_weeks=args.weeks,
        k_min=args.k_min,
        pilot=args.pilot,
        period=args.period,
        dynamic=args.dynamic,
        hospital_level=args.hospital,
        annual_cap=args.annual_cap,
    )

    if args.csv:
        print_results([r])
    else:
        print_results_table([r])


def _run_spread_sweep(args: argparse.Namespace) -> None:
    users_values = [500, 2000, 5000, 10000]
    epsilon_values = [0.5, 1.0, 2.0, 4.0]
    k_min_values = [5, 7, 11]
    period_values = ["weekly", "monthly"]

    combos = [(u, e, k, p) for u in users_values for e in epsilon_values for k in k_min_values for p in period_values]
    total = len(combos)
    print(f"Running {total} spread scenarios (seed={args.seed})...\n", file=sys.stderr)

    results = []
    for i, (n_users, eps, k_min, period) in enumerate(combos, 1):
        r = run_scenario(
            n_users=n_users, epsilon=eps, split_planned_ratio=0.3,
            dominance_threshold=0.30, seed=args.seed, n_weeks=args.weeks,
            k_min=k_min, pilot=False, period=period,
        )
        results.append(r)
        if i % 10 == 0:
            print(f"  {i}/{total}", file=sys.stderr)

    print(f"\nAll {total} complete.\n", file=sys.stderr)
    if args.csv:
        print_results(results)
    else:
        print_results_table(results)


def _run_pilot_sweep(args: argparse.Namespace) -> None:
    users_values = [30, 50, 80, 120, 200]
    epsilon_values = [1.0, 2.0, 4.0]
    k_min_values = [3, 5, 7, 11]
    period_values = ["weekly", "monthly"]

    combos = [(u, e, k, p) for u in users_values for e in epsilon_values for k in k_min_values for p in period_values]
    total = len(combos)
    print(f"Running {total} pilot scenarios (seed={args.seed})...\n", file=sys.stderr)

    results = []
    for i, (n_users, eps, k_min, period) in enumerate(combos, 1):
        r = run_scenario(
            n_users=n_users, epsilon=eps, split_planned_ratio=0.3,
            dominance_threshold=0.30, seed=args.seed, n_weeks=args.weeks,
            k_min=k_min, pilot=True, period=period,
        )
        results.append(r)
        if i % 10 == 0:
            print(f"  {i}/{total}", file=sys.stderr)

    print(f"\nAll {total} complete.\n", file=sys.stderr)
    if args.csv:
        print_results(results)
    else:
        print_results_table(results)


def _run_dynamic_sweep(args: argparse.Namespace) -> None:
    """Compare static monthly/weekly vs dynamic vs hospital-level, all at cap=100."""
    users_values = [50, 80, 120, 200]
    cap = 100.0

    results = []
    configs = [
        (True, False, "monthly", False),
        (True, False, "biweekly", False),
        (True, False, "weekly", False),
        (True, False, "weekly", True),
        (True, True, "monthly", False),
        (True, True, "weekly", True),
    ]

    total = len(users_values) * len(configs)
    print(f"Running {total} dynamic/hospital scenarios at cap={cap} (seed={args.seed})...\n", file=sys.stderr)

    for n_users in users_values:
        for pilot, hosp, period, dyn in configs:
            r = run_scenario(
                n_users=n_users, epsilon=1.0,
                split_planned_ratio=0.3, dominance_threshold=0.30,
                seed=args.seed, n_weeks=args.weeks, k_min=5,
                pilot=pilot, period=period, dynamic=dyn,
                hospital_level=hosp, annual_cap=cap,
            )
            results.append(r)

    print(f"\nAll {total} complete.\n", file=sys.stderr)
    if args.csv:
        print_results(results)
    else:
        print_results_table(results)


if __name__ == "__main__":
    main()
