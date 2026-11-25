"""Priors as objects, and the plots and summaries the priors notebook
(notebooks/01-simple-regression/01-priors.ipynb) needs.

scaffold() puts functions/ on the import path, so the notebook imports this
with `import priors`. The R project's functions/priors.R and the Stata
project's plot_priors.ado, prior_interval.ado, and prior_share.ado do the
same.

    wide = priors.normal(0, 1)
    narrow = priors.normal(0, 0.2)
    priors.plot_priors([wide, narrow], xlabel="α", possible=(-1, 1))
    priors.interval_text(narrow)      # "-0.39 to 0.39"
    priors.share(wide, -1, 1)         # 0.68
"""

import re
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

import framework as fw


@dataclass(frozen=True)
class Prior:
    """A prior: its name, a frozen scipy distribution, and where
    plot_priors() writes the name, on the curve's right flank."""

    name: str
    dist: object
    label_at: float

    def __repr__(self):
        return f"<prior {self.name}>"


def normal(mean=0, sd=1):
    return Prior(f"Normal({mean:g}, {sd:g})", stats.norm(mean, sd), mean + 1.1 * sd)


def exponential(rate=1):
    return Prior(f"Exponential({rate:g})", stats.expon(scale=1 / rate), 0.6 / rate)


def half_normal(sd=1):
    """A normal folded at 0: positive values only, for SDs."""
    return Prior(f"Half-normal(0, {sd:g})", stats.halfnorm(scale=sd), 1.2 * sd)


class _HalfT:
    """A Student t folded at 0, with the pdf, cdf, and ppf that Prior uses.
    scipy has no half-t."""

    def __init__(self, df, scale):
        self.t = stats.t(df, scale=scale)

    def pdf(self, x):
        return np.where(np.asarray(x) < 0, 0.0, 2 * self.t.pdf(x))

    def cdf(self, x):
        return np.maximum(2 * self.t.cdf(x) - 1, 0.0)

    def ppf(self, p):
        return self.t.ppf((1 + np.asarray(p)) / 2)

    def rvs(self, size=None):
        return np.abs(self.t.rvs(size=size))


def half_t(df=3, scale=2.5):
    """A Student t folded at 0. brms's default for a residual SD is
    Half-t(3, 0, 2.5)."""
    return Prior(f"Half-t({df:g}, 0, {scale:g})", _HalfT(df, scale), 0.8 * scale)


def interval(prior, level=0.95):
    """The central interval holding `level` of the prior, as (lower, upper)."""
    tail = (1 - level) / 2
    return prior.dist.ppf(tail), prior.dist.ppf(1 - tail)


def interval_text(prior, level=0.95, digits=2):
    """interval() as text, such as "-1.96 to 1.96"."""
    return " to ".join(f"{bound:.{digits}f}" for bound in interval(prior, level))


def share(prior, lower=-np.inf, upper=np.inf):
    """The share of the prior between lower and upper."""
    return prior.dist.cdf(upper) - prior.dist.cdf(lower)


def plot_priors(priors, xlabel, limits=None, possible=None):
    """Density curves of one prior, or of a list of priors, on shared axes.
    With two or more, each is labeled on its curve. Colours follow the list
    order, from the palette scaffold.py sets. limits=(lower, upper) fixes the
    x axis, so separate plots compare; without it the axis spans the priors'
    central 99.8%. possible=(lower, upper) shades the parameter's possible
    values."""
    if isinstance(priors, Prior):
        priors = [priors]
    if limits is None:
        limits = (min(p.dist.ppf(0.001) for p in priors), max(p.dist.ppf(0.999) for p in priors))
    grid = np.linspace(*limits, 501)
    curves = pd.concat(
        pd.DataFrame({"prior": p.name, "value": grid, "density": p.dist.pdf(grid)}) for p in priors
    )

    fig, ax = plt.subplots(figsize=(6, 3))
    if possible is not None:
        ax.axvspan(*possible, color="0.9", zorder=0)
    sns.lineplot(data=curves, x="value", y="density", hue="prior", linewidth=2, legend=False, ax=ax)
    if len(priors) > 1:  # one curve needs no label: the title names it
        for line, p in zip(ax.lines, priors):
            ax.annotate(p.name, (p.label_at, p.dist.pdf(p.label_at)), xytext=(3, 3),
                        textcoords="offset points", color=line.get_color())
    ax.set(xlabel=xlabel, ylabel="Density", title=list_text([p.name for p in priors]))
    ax.set_ylim(bottom=0)
    if possible is not None:  # caption in a strip kept clear below the axis title
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        fig.text(0.99, 0.01, "Grey band: possible values.", ha="right", va="bottom", fontsize=8)
    plt.show()


def list_text(names):
    """Names joined for a title: "A", "A and B", "A, B, and C"."""
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def mean_sd_table(data, *columns, digits=2):
    """Mean and SD of the chosen columns, one row per column, rounded."""
    table = data[list(columns)].agg(["mean", "std"]).T.rename(columns={"std": "sd"})
    return table.round(digits) + 0.0  # + 0.0 turns -0.00 into 0.00


def standardize(x):
    """Mean 0, SD 1, with the sample SD (n - 1), as in R's sd()."""
    return (x - x.mean()) / x.std()


def read_mobility():
    """ELS:2002 students with both SES measures, with family SES (parent_ses_z)
    and adult SES (adult_ses_z) standardized. read_mobility() in the R project
    does the same."""
    els = fw.data_read(
        "inputs.final.els_clean",
        usecols=["student_id", "w1_ses", "w4_ses"],
        dtype={"student_id": str},
    )
    els = els.dropna(subset=["w1_ses", "w4_ses"]).copy()
    els["parent_ses_z"] = standardize(els["w1_ses"])
    els["adult_ses_z"] = standardize(els["w4_ses"])
    return els


# Prior predictive simulation -------------------------------------------------
#
#     sets = {
#         "Weaker": priors.prior_set(alpha=priors.normal(0, 1), beta=priors.normal(0, 1), sigma=priors.half_t(3, 2.5)),
#         "Stronger": priors.prior_set(alpha=priors.normal(0, 0.2), beta=priors.normal(0, 0.5), sigma=priors.exponential(1)),
#     }
#     draws = priors.draw_priors(sets)
#     priors.plot_prior_lines(draws, "alpha + beta * parent_ses_z")
#     simulated = priors.simulate_outcomes(draws, students, "alpha + beta * parent_ses_z")
#     priors.plot_simulated(simulated, "parent_ses_z")
#     stats = priors.simulated_stats(simulated, outcome_sd=lambda d: d["y"].std())
#     priors.plot_simulated_stats(stats, reference={"outcome_sd": 1}, log_x=True)


def prior_set(**priors):
    """The priors for one model: one named prior per parameter, any names."""
    return dict(priors)


def prior_set_table(sets):
    """One row per prior set, one column per parameter: the name of its
    prior. sets is a dict of prior_set()s."""
    return pd.DataFrame(
        [{"set": name, **{param: p.name for param, p in s.items()}} for name, s in sets.items()]
    )


def draw_priors(sets, n=4000):
    """n independent draws of every parameter from each set: one row per set
    and draw, one column per parameter."""
    draws = pd.concat(
        pd.DataFrame({"set": name, "draw": np.arange(1, n + 1),
                      **{param: p.dist.rvs(size=n) for param, p in s.items()}})
        for name, s in sets.items()
    )
    draws["set"] = pd.Categorical(draws["set"], categories=list(sets))
    return draws.reset_index(drop=True)


def formula_predictors(mu, draws):
    """The names in mu, an expression string, that are not columns of draws:
    the predictors."""
    names = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", mu)
    return [n for n in dict.fromkeys(names) if n not in draws.columns and n not in _FUNCTIONS]


# Names pandas' eval knows as functions, not predictors
_FUNCTIONS = {"exp", "log", "sqrt", "abs", "sin", "cos", "where"}


def plot_prior_lines(draws, mu, n_lines=100, x_range=(-2, 2), band=(-2, 2),
                     xlabel=None, ylabel="Expected outcome"):
    """The line each of the first n_lines draws implies for mu, an expression
    in the parameters and one predictor, over x_range of that predictor;
    other predictors are held at 0. One panel per set; band shades the
    outcome's plausible range. Axis labels default to the variable names."""
    predictors = formula_predictors(mu, draws)
    x = predictors[0]
    grid = pd.DataFrame({x: x_range, **{other: 0.0 for other in predictors[1:]}})
    lines = draws[draws["draw"] <= n_lines].merge(grid, how="cross")
    lines["mu"] = lines.eval(mu)

    sets = list(draws["set"].cat.categories)
    fig, axes = plt.subplots(1, len(sets), figsize=(8, 3.5), sharey=True, squeeze=False)
    for ax, name in zip(axes.flat, sets):
        ax.axhspan(*band, color="0.9", zorder=0)
        for _, line in lines[lines["set"] == name].groupby("draw"):
            ax.plot(line[x], line["mu"], color="C0", alpha=0.3, linewidth=0.8)
        ax.set(title=name, xlabel=xlabel or x)
    axes[0, 0].set_ylabel(ylabel)
    fig.suptitle(f"Implied lines, {n_lines} draws from each prior set")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.text(0.99, 0.01, f"Grey band: {band[0]:g} to {band[1]:g} on the outcome's scale.",
             ha="right", va="bottom", fontsize=8)
    plt.show()


def simulate_outcomes(draws, data, mu, family="normal", n_draws=None):
    """Simulated outcomes: for each draw (the first n_draws, or all), one
    outcome per row of data. mu is an expression in the parameters and data
    columns. family: "normal" (needs a sigma parameter), "bernoulli" (mu on
    the log-odds scale), or "poisson" (mu on the log scale). Adds row, mu,
    and y."""
    if n_draws is not None:
        draws = draws[draws["draw"] <= n_draws]
    rows = data.reset_index(drop=True).assign(row=lambda d: np.arange(1, len(d) + 1))
    simulated = draws.merge(rows, how="cross")
    simulated["mu"] = simulated.eval(mu)
    if family == "normal":
        simulated["y"] = np.random.normal(simulated["mu"], simulated["sigma"])
    elif family == "bernoulli":
        simulated["y"] = np.random.binomial(1, 1 / (1 + np.exp(-simulated["mu"])))
    elif family == "poisson":
        simulated["y"] = np.random.poisson(np.exp(simulated["mu"]))
    else:
        raise ValueError('family must be "normal", "bernoulli", or "poisson"')
    return simulated


def plot_simulated(simulated, x, n_draws=16, ncol=8, reference=(-2, 2),
                   xlabel=None, ylabel="Simulated outcome"):
    """simulate_outcomes() as small scatter plots of y against x, for the
    first n_draws draws of each set, ncol to a row, the sets one after
    another, on shared axes so the sets compare. Dashed lines mark reference
    values of the outcome."""
    shown = simulated[simulated["draw"] <= n_draws]
    panels = [(name, draw) for name in shown["set"].cat.categories for draw in range(1, n_draws + 1)]
    nrow = -(-len(panels) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 6), sharex=True, sharey=True, squeeze=False)
    for ax, (name, draw) in zip(axes.flat, panels):
        panel = shown[(shown["set"] == name) & (shown["draw"] == draw)]
        for value in reference:
            ax.axhline(value, linestyle="--", color="#D55E00", linewidth=0.7, zorder=3)
        ax.scatter(panel[x], panel["y"], s=2, alpha=0.5, linewidths=0)
        ax.set_title(f"{name} {draw}", fontsize=7, pad=2)
        ax.set_xticks([-2, 0, 2])
        ax.tick_params(labelsize=6)
    fig.supxlabel(xlabel or x)
    fig.supylabel(ylabel)
    fig.suptitle(f"Simulated data sets, {n_draws} draws from each prior set, {shown['row'].nunique()} rows each")
    fig.tight_layout(w_pad=0.2, h_pad=0.4, rect=(0, 0.03, 1, 1))
    fig.text(0.99, 0.01, f"Red dashed lines: {' and '.join(f'{v:g}' for v in reference)} on the outcome's scale.",
             ha="right", va="bottom", fontsize=8)
    plt.show()


def simulated_stats(simulated, **stats):
    """Statistics of each simulated data set: one row per set and draw. Each
    statistic is a function of one data set, such as
    outcome_sd=lambda d: d["y"].std() or share_one=lambda d: d["y"].mean()."""
    return (
        simulated.groupby(["set", "draw"], observed=True)
        .apply(lambda d: pd.Series({name: f(d) for name, f in stats.items()}), include_groups=False)
        .reset_index()
    )


def plot_simulated_stats(stats, reference=None, log_x=False, bins=50):
    """simulated_stats() as histograms: one panel per set and statistic.
    reference is a dict of values to mark, such as {"outcome_sd": 1} for the
    observed outcome SD. log_x=True puts the x axis on a log scale, for
    statistics with long right tails."""
    names = [c for c in stats.columns if c not in ("set", "draw")]
    sets = list(stats["set"].cat.categories)
    fig, axes = plt.subplots(len(sets), len(names), figsize=(7, 4), sharex="col", squeeze=False)
    for i, name in enumerate(sets):
        for j, stat in enumerate(names):
            ax = axes[i, j]
            values = stats.loc[stats["set"] == name, stat]
            edges = (np.geomspace(values[values > 0].min(), values.max(), bins + 1) if log_x
                     else np.linspace(values.min(), values.max(), bins + 1))
            ax.hist(values, bins=edges)
            if log_x:
                ax.set_xscale("log")
                ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
            if reference and stat in reference:
                ax.axvline(reference[stat], linestyle="--", color="#D55E00", linewidth=1.2)
            if i == 0:
                ax.set_title(stat, fontsize=9)
            if j == len(names) - 1:
                ax.yaxis.set_label_position("right")
                ax.set_ylabel(name, rotation=270, labelpad=12)
    fig.supylabel("Simulated data sets")
    fig.suptitle(f"Statistics of {stats['draw'].nunique():,} simulated data sets per prior set")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    if reference:
        values = ", ".join(f"{k} = {v:g}" for k, v in reference.items())
        noun = "lines: values" if len(reference) > 1 else "line: the value"
        fig.text(0.99, 0.01, f"Red dashed {noun} in the observed data ({values}).",
                 ha="right", va="bottom", fontsize=8)
    plt.show()

