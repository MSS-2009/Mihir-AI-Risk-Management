"""Parameters estimated from a customer's own history, with provenance.

The intellectual core of v3. Everything here shrinks toward the published prior
by how much evidence there actually is, so a customer with three months of
history does not get a parameter derived from three months of history.
"""
from .estimator import (
    BLENDED_ABOVE,
    MEASURED_ABOVE,
    EstimationResult,
    ParameterEstimate,
    estimate_marginals,
    provenance_for,
)
from .frequency import (
    DEFAULT_PRIOR_STRENGTH_YEARS,
    FrequencyPosterior,
    estimate_frequency,
    estimate_frequency_triple,
    pert_mean,
    to_pert_triple,
)
from .magnitude import MagnitudePosterior, estimate_magnitude, to_magnitude_pair
from .observe import Observations, observe_all

__all__ = [
    "estimate_marginals", "EstimationResult", "ParameterEstimate", "provenance_for",
    "MEASURED_ABOVE", "BLENDED_ABOVE",
    "estimate_frequency", "estimate_frequency_triple", "to_pert_triple",
    "FrequencyPosterior", "pert_mean", "DEFAULT_PRIOR_STRENGTH_YEARS",
    "estimate_magnitude", "to_magnitude_pair", "MagnitudePosterior",
    "observe_all", "Observations",
]
