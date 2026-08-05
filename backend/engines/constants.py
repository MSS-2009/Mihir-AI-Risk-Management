"""Pinned simulation settings.

These are fixed so results are comparable across runs, industries, and releases.
Changing any of them changes every published number, so they live in one place
and are surfaced in the traceability envelope.
"""

# Pinned. The regression targets are defined at this count.
N_SIMS = 50_000

# The robustness and fragility sweeps run at the SAME count, deliberately.
#
# Measured: the fragility ranking is unstable below 50k. At 10k the top pair
# changes; at 50k it reproduces the reference ordering (tariff x logistics,
# tariff x stockout, logistics x stockout). Since the ranking IS the product
# output, it has to be computed where it is stable.
#
# Measured: the band spread also shrinks with n_sims (8.3% -> 6.0% -> 5.6% at
# eps=0.10 for 10k -> 20k -> 50k). Part of the apparent spread at low n is
# percentile-estimator jitter rather than dependence, so the larger sample is
# the more honest band, not merely the more precise one.
#
# Cost: ~90 sequential portfolio runs, about 5s. The sweep therefore runs on its
# own endpoint and loads after the dashboard paints, rather than blocking it.
N_SIMS_SWEEP = 50_000

# Threads are NOT used for the sweep. Measured: 8 BLAS-contending workers give a
# 2.2x speedup but change matmul reduction order and break bit-exact
# reproducibility. Determinism is non-negotiable, so the sweep stays sequential.
SWEEP_PARALLEL = False

DEFAULT_SEED = 42

# Tolerances for calibration tests. The closed form carries no Monte Carlo
# noise but the simulation it is compared against does, so equality is the
# wrong assertion.
CLOSED_FORM_TOL_50K = 0.005   # 0.5%
CLOSED_FORM_TOL_10K = 0.010   # 1.0%

# Expected annual loss is stable to ~0.03% across variants; tail percentiles
# are not stable better than ~3%. Test them accordingly.
EAL_REGRESSION_TOL = 0.002    # 0.2%
TAIL_REGRESSION_TOL = 0.03    # 3.0%
