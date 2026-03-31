# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-03-23

### Added
- Laplace mechanism with configurable epsilon and sensitivity
- Publication state machine (warming up / published / cooling down / suppressed)
- Contribution clipping with configurable bounds (planned/actual hours)
- K-anonymity threshold and top-1 dominance rule
- Temporal coarsening: weekly, biweekly, or monthly aggregation periods
- Adaptive epsilon schedule that never overshoots an annual budget cap
- Confidence intervals for Laplace-noised means
- `PrivacyLedger` Protocol with `InMemoryPrivacyLedger` reference implementation
- Simulation module with CLI (`dp-group-stats-sim`) for parameter sweeps
- 43 tests, 100% type annotation coverage
