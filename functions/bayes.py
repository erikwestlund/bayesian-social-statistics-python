"""Helpers for the Bayesian notebooks: the analysis sample, Stan models, and fits.

scaffold() puts functions/ on the import path, so notebooks import this with
`import bayes`. The Stan programs are in stan/, shared with the R project.
"""

from pathlib import Path

import cmdstanpy
import framework as fw
import numpy as np
import pandas as pd

# cmdstanpy logs each chain's start and finish, and every rejected proposal
# during warmup. The notebooks report the diagnostics that matter instead.
cmdstanpy.disable_logging()

# Every variable in the model is in SD units, standardized with fixed,
# documented constants rather than sample statistics. Math T-scores are scaled
# by NCES to mean 50 and SD 10, so (score - 50) / 10 is in SD units. SES is the
# NCES composite as it is: the average of components NCES standardized to mean
# 0 and SD 1. The composite's own SD is about 0.75. Fixed constants keep the
# priors free of the data and keep coefficients comparable across studies.
PREDICTORS = ["w1_math_z", "w1_ses"]
OUTCOME = "w2_math_z"

# Weakly informative priors in SD units. The intercept is the expected
# follow-up score, in SDs from the T-score mean, for a student at 50 in the
# base year with SES 0: Normal(0, 1) allows anything within about 2 SD. A slope
# beyond 2 SD of outcome per SD of a predictor would be implausible. The
# residual SD has prior mean 1, the outcome's own SD.
WEAK = {
    "alpha_mean": 0.0,
    "alpha_sd": 1.0,
    "beta_mean": [0.0, 0.0],
    "beta_sd": [1.0, 1.0],
    "sigma_rate": 1.0,
}


def to_sd(score):
    """A math T-score in SD units from the T-score mean."""
    return (score - 50) / 10


def to_points(sd_units):
    """SD units back to T-score points (a difference, not a score)."""
    return 10 * sd_units


def analysis_sample(clean: pd.DataFrame) -> pd.DataFrame:
    """Students with both math scores and SES, with the math scores in SD units."""
    sample = clean.dropna(subset=["w1_math", "w2_math", "w1_ses"]).copy()
    sample["w1_math_z"] = to_sd(sample["w1_math"])
    sample["w2_math_z"] = to_sd(sample["w2_math"])
    return sample.reset_index(drop=True)


def model(name: str) -> cmdstanpy.CmdStanModel:
    """Compile stan/<name>.stan, or reuse the executable when it is current."""
    return cmdstanpy.CmdStanModel(stan_file=str(Path(fw.project_root()) / "stan" / f"{name}.stan"))


def stan_data(
    data: pd.DataFrame,
    priors: dict | None = None,
    prior_only: bool = False,
    predict: bool = False,
) -> dict:
    """The data block for stan/regression.stan.

    priors=None gives flat priors: uniform on alpha, beta, and log(sigma).
    """
    flat = priors is None
    priors = WEAK if flat else priors
    return {
        "N": len(data),
        "K": len(PREDICTORS),
        "X": data[PREDICTORS].to_numpy(),
        "y": data[OUTCOME].to_numpy(),
        "prior": int(not flat),
        "alpha_mean": priors["alpha_mean"],
        "alpha_sd": priors["alpha_sd"],
        "beta_mean": priors["beta_mean"],
        "beta_sd": priors["beta_sd"],
        "sigma_rate": priors["sigma_rate"],
        "prior_only": int(prior_only),
        "predict": int(predict),
    }


def sample(stan_model: cmdstanpy.CmdStanModel, data: dict, seed: int = 123, **kwargs) -> cmdstanpy.CmdStanMCMC:
    """Four chains of 1,000 warmup and 1,000 sampling iterations, without progress bars."""
    options = {"chains": 4, "iter_warmup": 1000, "iter_sampling": 1000, "seed": seed, "show_progress": False}
    options.update(kwargs)
    return stan_model.sample(data=data, **options)


def simulate(n: int, alpha: float, beta: list[float], sigma: float, rng: np.random.Generator) -> pd.DataFrame:
    """Fake students from the regression model, with predictors that look like HSLS:09.

    Parameters are in SD units. Base-year math is normal with mean 0.17 and
    SD 1 in SD units (51.7 and 10 as a T-score). SES is normal with mean 0.08
    and SD 0.8 and correlates 0.43 with base-year math. These round the values
    in the HSLS:09 analysis sample. The follow-up score comes from the model
    with the given parameters. The math scores are returned in both units.
    """
    mean = np.array([0.17, 0.08])
    sd = np.array([1.0, 0.8])
    correlation = np.array([[1.0, 0.43], [0.43, 1.0]])
    covariance = correlation * np.outer(sd, sd)
    x = rng.multivariate_normal(mean, covariance, size=n)
    fake = pd.DataFrame({"w1_math_z": x[:, 0], "w1_ses": x[:, 1]})
    fake["w2_math_z"] = alpha + x @ np.asarray(beta) + rng.normal(0, sigma, size=n)
    fake["w1_math"] = 50 + 10 * fake["w1_math_z"]
    fake["w2_math"] = 50 + 10 * fake["w2_math_z"]
    return fake


def draws(fit: cmdstanpy.CmdStanMCMC, names: list[str] | None = None) -> pd.DataFrame:
    """Posterior draws as a data frame, one row per draw, with chain and draw columns.

    The columns are alpha, beta[1], beta[2], sigma unless names are given.
    """
    names = names or ["alpha", "beta[1]", "beta[2]", "sigma"]
    # Select the variables before building the frame: a fit with predict=1
    # holds two values per student per draw, too many to load to keep four
    variables = sorted({name.split("[")[0] for name in names})
    frame = fit.draws_pd(vars=variables)[names]
    # draws_pd() orders rows by chain, then by draw within the chain
    per_chain = fit.num_draws_sampling
    frame.insert(0, "chain", np.repeat(np.arange(1, fit.chains + 1), per_chain))
    frame.insert(1, "draw", np.tile(np.arange(1, per_chain + 1), fit.chains))
    return frame.reset_index(drop=True)


def interval(values, level: float = 0.95) -> tuple[float, float]:
    """The central (equal-tailed) interval holding the given share of the values."""
    tail = (1 - level) / 2
    low, high = np.quantile(values, [tail, 1 - tail])
    return float(low), float(high)
