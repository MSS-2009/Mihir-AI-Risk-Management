"""t-copula dependence, correlation matrix validation and repair.

Why a t-copula rather than Gaussian: the Gaussian copula has zero asymptotic
tail dependence, meaning extreme events become independent in the limit no
matter what correlation you set. That assumption underpinned the 2008 CDO
mispricing. df=4 keeps joint tails fat; below ~3 the variance misbehaves, above
~10 it converges to Gaussian and loses the point.

We make no claim on t-versus-Gaussian, which is a small effect at this number of
domains. The claim is correlated-versus-independent, which is large and robust.

THE SHARED-DRAWS RULE (correctness, not optimization)
-----------------------------------------------------
`CopulaDraws` is frozen and holds the standard normals and the chi-square draws.
Every robustness perturbation and every fragility probe reuses the SAME object
and varies ONLY the correlation matrix (hence only the Cholesky factor). If the
draws were re-randomised per perturbation, the reported band would measure Monte
Carlo noise rather than dependence misspecification: at eps=0.05 the true band
spread is around 3.8% while P99 sampling noise at 20k sims is around 2.4%, so
the signal would be swamped by the thing it is supposed to exclude.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.stats import t as student_t

logger = logging.getLogger(__name__)

# Copula degrees of freedom. See module docstring.
COPULA_DF = 4

# Off-diagonal default for any pair a pack does not name explicitly.
BASELINE_CORRELATION = 0.20


@dataclass(frozen=True)
class CopulaDraws:
    """Frozen Monte Carlo inputs, shared across every matrix variation.

    Only the correlation matrix may change between uses of this object. That is
    the entire point: it makes the robustness band a pure function of dependence.
    """

    normals: np.ndarray   # (n_sims, d) iid standard normal
    chi2: np.ndarray      # (n_sims,) chi-square with `df` degrees of freedom
    df: int
    n_sims: int
    d: int
    seed: int


def draw_copula_inputs(d: int, n_sims: int, seed: int, df: int = COPULA_DF) -> CopulaDraws:
    """Draw the shared standard normals and chi-square variates once."""
    rng = np.random.default_rng(seed)
    return CopulaDraws(
        normals=rng.standard_normal((n_sims, d)),
        chi2=rng.chisquare(df, n_sims),
        df=df,
        n_sims=n_sims,
        d=d,
        seed=seed,
    )


def uniforms_for(draws: CopulaDraws, corr: np.ndarray) -> np.ndarray:
    """Map the shared draws through a correlation matrix to (n_sims, d) uniforms.

    The ONLY thing that varies between calls is `corr`.
    """
    if corr.shape != (draws.d, draws.d):
        raise ValueError(f"matrix is {corr.shape}, expected ({draws.d}, {draws.d})")
    L = np.linalg.cholesky(corr)
    z = draws.normals @ L.T
    t_stat = z / np.sqrt(draws.chi2 / draws.df)[:, None]
    return student_t.cdf(t_stat, df=draws.df)


def independent_uniforms(n_sims: int, d: int, seed: int) -> np.ndarray:
    """Plain iid uniforms for the independent baseline.

    Deliberately NOT built from CopulaDraws: the shared chi-square variate is
    precisely what creates t-copula tail dependence, so reusing it would leave
    the "independent" baseline dependent in the tail and understate the premium.
    """
    return np.random.default_rng(seed).random((n_sims, d))


# ---------------------------------------------------------------------------
# Matrix construction, validation, repair
# ---------------------------------------------------------------------------


def build_matrix(
    keys: list[str],
    pairs: dict[tuple[str, str], float],
    baseline: float = BASELINE_CORRELATION,
) -> np.ndarray:
    """Dense correlation matrix from a sparse set of named strong pairs.

    Unnamed off-diagonal pairs take `baseline`. Pair keys are order-insensitive.
    """
    d = len(keys)
    idx = {k: i for i, k in enumerate(keys)}
    m = np.full((d, d), float(baseline))
    np.fill_diagonal(m, 1.0)
    for (a, b), rho in pairs.items():
        if a not in idx or b not in idx:
            raise KeyError(f"correlation pair ({a}, {b}) references a domain not in {keys}")
        i, j = idx[a], idx[b]
        m[i, j] = m[j, i] = float(rho)
    return m


def is_pd(corr: np.ndarray) -> bool:
    try:
        np.linalg.cholesky(corr)
        return True
    except np.linalg.LinAlgError:
        return False


def require_pd(corr: np.ndarray, name: str) -> np.ndarray:
    """Validate a hand-authored pack matrix. Fails loudly, by design.

    A pack matrix that is not positive-definite is an authoring error and must
    surface at import and in tests, not get silently repaired into something the
    author never reviewed.
    """
    if not is_pd(corr):
        eigs = np.linalg.eigvalsh(corr)
        raise ValueError(
            f"correlation matrix for '{name}' is not positive-definite "
            f"(min eigenvalue {eigs.min():.6f}). Fix the authored pairs, or call "
            f"ensure_pd() explicitly if this matrix is user-supplied."
        )
    return corr


def nearest_pd(m: np.ndarray) -> np.ndarray:
    """Project onto the nearest positive-definite correlation matrix.

    Symmetrise, clip eigenvalues to a small positive floor, then rescale to a
    unit diagonal. Used for user edits and for perturbed matrices in the
    robustness sweep, where leaving the neighbourhood of PD matrices is expected.
    """
    m = (m + m.T) / 2.0
    w, v = np.linalg.eigh(m)
    w = np.clip(w, 1e-6, None)
    m = v @ np.diag(w) @ v.T
    d = np.sqrt(np.diag(m))
    m = m / np.outer(d, d)
    np.fill_diagonal(m, 1.0)
    return m


def ensure_pd(corr: np.ndarray, context: str = "matrix") -> tuple[np.ndarray, bool]:
    """Return (matrix, was_repaired). Logs when a repair happens."""
    if is_pd(corr):
        return corr, False
    logger.warning(
        "%s was not positive-definite (min eigenvalue %.6f); projected to nearest PD",
        context,
        np.linalg.eigvalsh(corr).min(),
    )
    repaired = nearest_pd(corr)
    if not is_pd(repaired):  # pragma: no cover - numerical guard
        raise ValueError(f"could not repair {context} to positive-definite")
    return repaired, True


def perturbed_matrix(base: np.ndarray, eps: float, rng: np.random.Generator) -> np.ndarray:
    """One symmetric perturbation of `base`, projected back to PD.

    This is the neighbourhood the robustness band sweeps: plausible alternative
    dependence structures a reasonable analyst might have written instead.
    """
    d = base.shape[0]
    noise = rng.normal(0.0, eps, (d, d))
    noise = (noise + noise.T) / 2.0
    np.fill_diagonal(noise, 0.0)
    m = np.clip(base + noise, -0.95, 0.95)
    np.fill_diagonal(m, 1.0)
    return nearest_pd(m)
