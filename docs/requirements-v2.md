# dp-group-stats: Privacy Requirements v2

**Created:** 2026-03-19
**Updated:** 2026-03-20
**Status:** Working draft
**Purpose:** Define a buildable privacy specification for repeated publication of small-group working-hours statistics.
**See also:** `dp-group-stats-accounting-model.md` for the detailed composition, budget, and ledger design.

---

## 1. Scope

The system publishes aggregate statistics about working hours for small professional groups, repeatedly over time.

Typical groupings include:
- national total
- state x specialty
- hospital
- hospital x specialty
- state x specialty x role

These groupings overlap. This is not a single clean tree by default. It is an overlapping lattice of rollups.

### 1.1 Intuitive model: hierarchical dimensions

The most useful mental model is not "one hierarchy for everything" but "multiple hierarchical dimensions."

Each published statistic can be described as a cell over several axes:
- entity
- profession
- time

Each axis may itself have a hierarchy:

```text
Entity
Germany
└─ State
   └─ Hospital

Profession
All workers
└─ Specialty
   └─ Role

Time
All time
└─ Year
   └─ Quarter
      └─ Month
         └─ Week
```

Examples of release cells:
- `(Bavaria, Cardiology, All roles, Week 12)`
- `(Charite, Cardiology, Junior doctors, Week 12)`
- `(Germany, All specialties, All roles, March 2026)`

This is why the overall release structure is not one global tree:
- `hospital x specialty` belongs naturally under the entity hierarchy and the profession hierarchy at the same time
- different published cells combine levels from different axes
- the result is closer to a hierarchical data cube than to a single parent-child tree

Trees are still useful inside specific release families, but the full release universe should be modeled as combinations across hierarchical dimensions.

The first version should optimize for:
- a clear privacy definition
- a mechanism that can be implemented and tested
- a small number of publishable group families
- explicit accounting across overlap and time

The first version should not optimize for:
- maximum release coverage
- full Census-style hierarchical optimization
- advanced continual-observation mechanisms unless clearly needed
- proving privacy by simulation alone

---

## 2. Release Model

### 2.1 Reporting cadence

- Release cadence: weekly
- Each release publishes aggregates for a predefined set of eligible cells
- Releases are repeated over many weeks, so composition over time is a core requirement

### 2.2 Unit of protection

Recommended baseline:
- one user's bounded contribution to one reporting week

This is the privacy unit the mechanism should protect in v1.

Reason:
- it matches the weekly publication cadence
- it is materially more realistic than full user-level privacy
- it is clearer than talking about an individual shift or day when the published output is weekly

### 2.3 Protected contribution structure

Each user submits one `WorkEvent` per day with two values: `planned_hours` and `actual_hours`. The weekly contribution per user is therefore a pair:
- `planned_weekly = sum(planned_hours)` over the week (contractual/scheduled)
- `actual_weekly = sum(actual_hours)` over the week (hours actually worked)

Overtime is derived: `overtime = actual - planned`. It is not a separate protected quantity.

### 2.4 Clipping bounds

Each quantity needs its own range:

| Quantity | Proposed clip | Rationale |
|----------|---------------|-----------|
| `planned_weekly` | [0, 80] hours | Contractual hours rarely exceed 80h/week |
| `actual_weekly` | [0, 120] hours | Covers extreme on-call weeks in healthcare (validated by simulation) |

Counts are not clipped or noised — they are public under the substitution neighboring relation (see Section 4.3).

The asymmetric bounds mean planned gets less noise than actual (smaller range → lower sensitivity). This is desirable: planned hours are more stable and the overtime signal depends on both. The actual bound of 120h was validated by simulation as sufficient to cover realistic extreme weeks while reducing noise compared to earlier 140h assumption.

### 2.5 Published quantities

The public output may be a mean, but the internal mechanism should operate on:
- bounded sums (one for planned, one for actual)
- counts

For each released cell and week:
1. clip each user's `planned_weekly` to `[0, 80]` and `actual_weekly` to `[0, 120]`
2. compute true count `n` (public, not noised)
3. compute true clipped sums `s_planned` and `s_actual`
4. add calibrated noise to `s_planned` and `s_actual` (2 noisy quantities per cell)
5. derive released means as `noisy_sum / true_count` and overtime as `actual_mean - planned_mean`

**Per-cell ε cost:**
- ε_planned for noisy planned sum
- ε_actual for noisy actual sum
- **Total per cell per week: ε_planned + ε_actual** (sequential composition, same user)

The split across ε_planned and ε_actual is a tuning decision. Weighting toward actual (higher sensitivity, higher interest for overtime detection) is a reasonable starting point. A future optimization could use a vector/joint-noise mechanism for tighter composition.

This is preferable to treating "mean" as the primitive release object because:
- sensitivity is easier to reason about
- consistency constraints are easier to express
- release quality can be evaluated separately for counts, sums, and means

### 2.6 Cell universe

The set of potentially publishable cells should be fixed in advance whenever possible.

Reason:
- if cells only appear when data exists, existence itself can leak information
- predefined taxonomies reduce the need for DP partition selection in v1

If the set of candidate cells cannot be fixed in advance, DP partition selection becomes a separate requirement.

---

## 3. Threat Model

The system must defend against attackers who can observe all public releases and combine them with outside knowledge.

### 3.1 Attacks in scope

- Hierarchical subtraction: infer a small child cell from parent and sibling cells
- Cross-dimensional overlap: infer the same group's value from multiple rollups that contain the same people
- Temporal differencing: infer a person's weekly hours from changes between adjacent releases
- Auxiliary-knowledge attacks: attacker knows all but one contributor in a cell
- Concentration attacks: one contributor dominates a cell, so the aggregate is too revealing even with DP noise

### 3.2 Not fully solved by DP alone

The following are policy or publication problems, not pure mechanism problems:
- releasing very small groups
- releasing highly concentrated cells
- revealing a cell's first appearance exactly when it crosses a threshold

These need additional release safeguards on top of DP.

---

## 4. Privacy Definition

### 4.1 Baseline guarantee

v1 should target user-week contribution `(epsilon, delta)`-DP: the mechanism protects one user's bounded contribution to one reporting week.

Neighboring datasets (i.e. datasets that differ by one protected finalized user-week) differ in exactly one protected weekly contribution.

This must hold for the entire public release mechanism over:
- all published cells in that week
- all overlapping groupings released together
- all repeated releases over time after composition accounting

### 4.2 Accounting model

The implementation may use:
- `(epsilon, delta)`-DP directly
- `rho`-zCDP or another internal accountant, converted back to an external `(epsilon, delta)` statement

The external-facing guarantee should still be reported in a form users and reviewers can understand.

### 4.3 Sensitivity control

Sensitivity must be bounded explicitly by clipping.

**Neighboring relation (substitution):** neighboring datasets differ in one user's contribution values, not in the user's presence. One dataset has user U contributing `(p₁, a₁)`, the other has `(p₂, a₂)`, both clipped to bounds. The set of users (and therefore the count) is the same in both.

This means:
- **Counts are not protected and are treated as public.** The true count is used in deriving published means. No noise is added to counts and no ε is spent on them.
- **The DP guarantee protects contribution values only:** an attacker cannot distinguish what hours a specific user worked, but can infer how many users are in a group.

Under this relation, the concrete sensitivities are:

| Quantity | Sensitivity | Derivation |
|----------|-------------|------------|
| planned sum | 80 | max(U_planned) - min(L_planned) = 80 - 0 |
| actual sum | 120 | max(U_actual) - min(L_actual) = 120 - 0 |
| count | not noised | public under substitution relation |

The published mean is derived as `noisy_sum / true_count`. This is less noisy than `noisy_sum / noisy_count` and uses all per-cell ε budget on the quantities that matter.

**Per cell per week, the ε cost is:**
- ε_planned for noisy planned sum
- ε_actual for noisy actual sum
- **Total: ε_planned + ε_actual**

The neighboring relation must be written down explicitly in the implementation docs. It cannot stay implicit.

---

## 5. Non-DP Release Safeguards

These are important, but they are not the formal privacy guarantee.

### 5.1 Minimum group threshold

- Do not release cells below `K_MIN`
- **Finalized value: `K_MIN = 5`** (validated by simulation; justified by labor data being less sensitive than medical or financial data, and by the dominance rule providing additional protection for small groups)

This is a publication rule, not a substitute for DP.

### 5.2 Dominance or concentration rule

Do not call this `l-diversity`.

The correct concept here is a dominance or concentration rule. This addresses low-variance or highly concentrated cells that remain sensitive even when DP noise is added.

**v1 rule (decided 2026-03-20):** top-1 dominance on clipped actual hours. Suppress if:

```
max(user_clipped_actual) / sum(all_clipped_actual) > 0.30
```

Design choices:
- **Top-1 only** (not top-k) — sufficient for healthcare working hours where coordinated cliques are unlikely
- **Actual hours only** — wider range (0–120) makes concentration more dangerous than planned hours (0–80)
- **Clipped values** — the check uses the same clipped values that enter the DP mechanism
- **30% threshold** — with K_MIN = 5, equal share is 20%; 30% means one person contributes 1.5× the average share. Validated by simulation.

See `dp-group-stats-accounting-model.md` §6.2 for rationale.

### 5.3 Temporal activation rule

To reduce threshold-crossing leakage:
- a cell should not become public immediately after a single week above threshold
- require `N` consecutive eligible weeks before first publication
- apply a symmetric rule for deactivation or use a short grace window

This is a release policy to reduce boundary leakage. It is not the DP proof.

---

## 6. Overlap And Consistency

### 6.1 Important correction

The publishable structure is not automatically a tree.

Examples:
- `hospital` and `state x specialty` overlap, but one is not always a parent of the other
- `state x specialty x role` cross-cuts other releases

Because of this, "parent equals weighted average of children" is only valid inside explicitly chosen release families where a true partition relationship holds.

### 6.2 v1 consistency rule

Only enforce consistency within declared parent-child families.

Examples of candidate families:
- `national -> state`
- `state x specialty -> hospital x specialty within that state`
- `hospital -> hospital x specialty`

Do not try to enforce one global consistency constraint across every rollup at once in v1.

### 6.3 Practical implication

If consistency is desired, the mechanism should internally maintain noisy counts and noisy sums. Means can then be derived after consistency post-processing.

If only means are published and counts remain internal, that is acceptable, but the internal count and sum objects still need to exist.

---

## 7. Composition

### 7.1 Across overlapping cells

If a single protected weekly contribution affects multiple released cells in the same week, those releases compose sequentially.

This includes:
- multiple hierarchy levels
- multiple cross-tabs
- multiple summaries derived from the same users

This is a fact of the privacy definition, not a policy choice.

### 7.2 Across disjoint cells

Within the same release, disjoint partitions compose in parallel.

This is only available where disjointness is actually true and documented. It should not be assumed loosely.

### 7.3 Budget allocation across release families

Budget allocation across release families should be **proportional to need, not uniform**.

Finer-level groups (e.g., hospital × specialty) are typically smaller and need more ε to produce useful statistics. Coarser-level groups (e.g., state × specialty) are larger and produce useful statistics even with small ε, because large N naturally drowns out noise.

Example: total per-user per-week budget = 1.0, two release families:

| Family | Typical N | ε allocation | Noise std on mean (actual, sens=120) |
|--------|-----------|-------------|--------------------------------------|
| State × specialty | 200 | 0.3 | 2.0 hours |
| Hospital × specialty | 15 | 0.7 | 11.4 hours |

vs. uniform split:

| Family | Typical N | ε allocation | Noise std on mean |
|--------|-----------|-------------|-------------------|
| State × specialty | 200 | 0.5 | 1.2 hours |
| Hospital × specialty | 15 | 0.5 | 16.0 hours |

The bottom-heavy allocation sacrifices unnecessary precision at the state level to make the hospital level substantially more useful, with the same total per-user budget.

This is consistent with Ko et al. (2025) who prove optimal allocation is bottom-heavy. The optimal split depends on the actual group size distribution and should be informed by simulation.

The library should support configurable per-family ε allocation. The specific split is a product decision.

### 7.4 Budget cap

**Decided (2026-03-20): per-user annual budget cap.**

The per-user ledger tracks the total ε any single user has been exposed to across all cells they appear in, across all weeks. This is the meaningful privacy guarantee — the budget lives with the user, not with cells or families.

Per-cell caps are simpler but weaker; they don't account for users appearing in multiple families. The per-user cap subsumes per-cell tracking.

**Finalized value: ε_annual = 150** (validated by simulation). Working hours are less sensitive than medical or financial data, justifying a lenient cap. With one release family at ε = 1.0/week, worst-case annual spend is 52, well within the cap. The headroom allows adding release families later without hitting the cap.

See `dp-group-stats-accounting-model.md` §4 for the full per-user accounting design, including ledger structure and the separation between noise calibration (per-family config) and budget accounting (per-user tracking).

### 7.5 Adaptive budget management

Instead of a hard cutoff when the budget cap is reached, the library should support **graceful degradation**: decrease ε per release as cumulative exposure approaches the cap.

**Simple approach — even spread over remaining time:**

```
ε_week(t) = ε_remaining / weeks_remaining_in_budget_period
```

This ensures budget is never exhausted abruptly. If spending has been on track, ε_week stays roughly constant. If overspent early, it tightens. The cell never goes dark — it just gets noisier.

**Combined with temporal coarsening:** when per-week noise exceeds a utility threshold (e.g., noise_std > 10 hours on the mean), the system can automatically aggregate over longer periods (monthly or quarterly) to produce fewer, more accurate releases from the same remaining budget.

**Design goal:** eliminate budget-based suppression entirely. Cells are suppressed only for K_MIN or dominance reasons (fixed policy), never because budget ran out. The public output shape stays stable; only precision changes.

This avoids the information leakage problem of hard suppression (the act of suppressing reveals budget state) and provides a smoother experience for data consumers.

### 7.6 Across time

Weekly publication composes over time.

Baseline assumption:
- naive sequential composition

Operational policy:
- maintain a rolling or annual privacy budget ledger
- stop or coarsen publication when the budget is exhausted

The ledger is an operational control layered on top of formal accounting. It does not replace formal accounting.

---

## 8. Temporal Model

The first version should assume repeated weekly releases under standard composition.

Advanced mechanisms such as the tree mechanism or budget recycling should be treated as future optimizations unless the v1 release pattern clearly matches their assumptions.

Reason:
- they add design complexity
- they are not required to define a correct baseline mechanism
- the first blocker is not advanced theory, but a precise release model

---

## 9. Utility Targets

The mechanism is only useful if published results remain interpretable for collective bargaining, policy, and campaign use.

Initial utility assumptions:
- weekly releases are useful, but monthly or quarterly rollups may be needed for the smallest groups
- groups near the suppression floor will often be too noisy to be decision-useful
- practical usefulness may begin closer to group size 20 than to the minimum release threshold

Utility targets should be defined as decision thresholds, for example:
- can we detect a 5-hour difference between two groups?
- can we detect a sustained overtime increase over 8-12 weeks?
- what error is acceptable for bargaining use versus public campaigning?

These are not privacy guarantees. They are product requirements.

---

## 10. Validation

Validation has three separate goals and they should not be mixed together.

### 10.1 Mechanism correctness

This is the highest priority.

Examples:
- clipping works as specified
- count and sum sensitivities match the defined neighboring relation
- noise distribution matches the intended mechanism
- composition accounting matches the reference accountant
- suppression and dominance rules are applied exactly as documented

### 10.2 Utility evaluation

Examples:
- mean absolute error by group size
- trend detection over repeated weekly releases
- ordering preservation between groups with real differences
- utility loss from allocating budget across more release families

### 10.3 Attack experiments

Examples:
- subtraction attacks with auxiliary knowledge
- temporal differencing around join and leave events
- concentration-heavy scenarios

Important:
- these experiments help choose parameters and release policy
- they do not prove DP
- the proof comes from the mechanism definition and the accountant

---

## 11. Recommended v1 Implementation

v1 should be narrow and defensible.

Recommended baseline:
1. Define one protected unit: one user's bounded weekly contribution
2. Fix the initial publishable cell universe in advance
3. Start with a small number of release families that have real partition structure
4. Clip contributions to fixed bounds
5. Add calibrated noise to sums (counts are not noised)
6. Derive means in post-processing
7. Apply non-DP safeguards: `K_MIN`, dominance rule, temporal activation rule
8. Track composition across cells and weeks with a reference accountant
9. Add consistency post-processing only inside the declared release families

The first version should avoid:
- releasing every imaginable cross-tab
- claiming one global consistency relation across a non-tree structure
- calling dominance checks `l-diversity`
- relying on simulation as a substitute for a written privacy definition

### 11.1 Current v1 defaults

The following defaults are the current implementation starting point for v1:

- **Protected unit:** one finalized user-week
- **Protected record contents:** `(planned_weekly, actual_weekly, assignment_snapshot)`
- **Finalization rule:** only finalized weeks are eligible for aggregation
- **Mutability:** finalized weeks are immutable for aggregation purposes
- **Backfills:** no historical backfills in v1; late-finalized weeks only enter future release windows
- **Primary public release family:** `state x specialty` (a single flat family of disjoint cells)
- **Release family model:** granularity tuple `(geography_level, time_level, work_category_level)` — see `dp-group-stats-accounting-model.md` §1
- **Public outputs:** `planned mean` and `overtime mean`
- **Counts:** kept internal in v1; not published. Not noised (public under substitution relation).
- **ε split:** ε_planned = 0.2, ε_actual = 0.8 (no ε spent on counts). Finalized by simulation.
- **Annual ε cap:** 150 per user. Finalized by simulation.
- **K_MIN:** 5. Finalized by simulation.
- **Clipping bounds:** planned [0, 80], actual [0, 120]. Finalized by simulation.
- **Suppression behavior:** stable public shape with generic `suppressed` status and no public reason codes
- **Dominance rule:** top-1, clipped actual hours, 30% threshold. See Section 5.2.
- **Aggregation cadence:** configurable per release family (not hardcoded to weekly). Each release family declares its own period (weekly, biweekly, monthly). The specific cadence per family is a product decision, deferred for now.
- **Suppressed cells (K_MIN, dominance, warming_up):** no noise generated, no ε cost. Cooling_down cells do cost ε.
- **Assignment rule:** hospital/specialty/role snapshot is frozen at week finalization. Split assignments within a week are prevented by UX.
- **Temporal activation:** publish only after `N = 2` consecutive eligible weeks
- **Temporal deactivation:** remove only after a 2-week grace period below eligibility
- **Candidate cell universe:** defined in advance from configured taxonomies / allowed combinations
- **Mechanism baseline:** Laplace mechanism with simple additive `epsilon` accounting
- **Budget accounting:** per-user annual cap with per-user ledger. See `dp-group-stats-accounting-model.md` §4.
- **Budget management:** pre-computed schedule + graceful degradation (time-based). See `dp-group-stats-accounting-model.md` §5.
- **Future extensions:** tighter accountants, additional release families, consistency post-processing, and more advanced temporal mechanisms remain possible later

## 12. Open Decisions

These decisions should be resolved before implementation starts in earnest.

1. ~~What exactly is one protected weekly contribution in the data model?~~ **Resolved:** a pair `(planned_weekly, actual_weekly)` clipped to `[0,80]` and `[0,120]` respectively. Counts are public under substitution relation (no noise, no ε). See Section 2.3-2.4, 4.3.
2. ~~Are releases based on one weekly per-user summary, or multiple lower-level events aggregated first?~~ **Resolved:** daily `WorkEvent` rows are summed to one weekly per-user pair before clipping and noise. See Section 2.3.
3. ~~Which release families are in scope for v1?~~ **Deferred.** The library must be general — any release family expressible as a partition should work. Specific families (e.g., national level, pilot hospital) are product decisions for OWH, not library concerns.
4. ~~Will counts be public, internal only, or published in coarsened form?~~ **Resolved:** Counts are never published. Internal only. See Section 11.1.
5. ~~What clipping bounds `[L, U]` are defensible for working hours?~~ **Resolved:** planned `[0, 80]`, actual `[0, 120]`. Validated by simulation. See Section 2.4.
6. ~~What `(epsilon, delta)` budget is acceptable per release and per year?~~ **Resolved:** annual per-user cap ε = 150. Per-family ε is a product decision (working assumption: 1.0). Validated by simulation.
7. ~~What `K_MIN` and dominance thresholds are acceptable?~~ **Resolved:** K_MIN = 5 (validated by simulation). Dominance: top-1, clipped actual, 30% threshold (validated by simulation). See Sections 5.1, 5.2.
8. ~~What temporal activation and deactivation rule should be used?~~ **Deferred.** Library supports configurable activation/deactivation. Specific N values are product decisions. See Section 11.1 for current defaults.
9. ~~Is a fixed candidate cell universe sufficient, or is DP partition selection needed?~~ **Deferred.** V1 assumes fixed universe. DP partition selection is a future extension.
10. ~~Which accountant should be used in implementation?~~ **Working assumption:** Start with simple additive ε accounting (Laplace mechanism). Design should allow swapping in a tighter accountant (zCDP, PLD) later.

---

## 13. Key Design Principle

The first goal is not to build the most sophisticated privacy system possible.

The first goal is to build a mechanism that can be stated precisely:
- what data unit it protects
- what outputs it releases
- what guarantee it provides
- what policy safeguards it layers on top
- how composition is tracked across overlap and time

If those five things are precise, the library can be built, tested, and justified. If they are vague, the rest of the design will stay unstable.
