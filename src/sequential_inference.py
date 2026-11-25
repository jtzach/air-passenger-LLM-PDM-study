"""Frozen-look median inference and secondary bounded-mean confidence sequences.

This module never calls a model or reads credentials. The primary median method
requires independent, identically distributed *complete rounds*. The secondary
betting method requires a constant conditional mean. Neither assumption is
established merely by submitting different seeds to a hosted model.

The primary alpha is divided over the entire frozen endpoint family AND all
scheduled looks. The betting CS is already time-uniform, so its separate alpha
is divided over endpoints only. Do not select the narrower of these intervals:
they estimate different quantities (median versus mean).
"""
from dataclasses import asdict, dataclass
import math
from statistics import mean, median
from typing import Iterable, Mapping, Sequence

DEFAULT_FRACTIONS = (0.01, 0.03, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99)


@dataclass(frozen=True)
class Interval:
    estimate: float
    lower: float
    upper: float
    n: int
    alpha: float
    estimand: str
    method: str

    @property
    def width(self):
        return self.upper - self.lower

    def as_dict(self):
        return {**asdict(self), "width": self.width}


def _probability(value, name="alpha"):
    if isinstance(value, bool) or not math.isfinite(value) or not 0 < value < 1:
        raise ValueError(f"{name} must be finite and strictly between zero and one")


def _samples(values: Iterable[float], bounds=None):
    result = tuple(float(x) for x in values)
    if not result or any(not math.isfinite(x) for x in result):
        raise ValueError("A nonempty sequence of finite observations is required")
    if bounds is not None:
        lo, hi = map(float, bounds)
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
            raise ValueError("Bounds must be finite and strictly increasing")
        if any(x < lo or x > hi for x in result):
            raise ValueError("Observation outside the prespecified support; do not clip it")
    return result


def binomial_half_cdf(k: int, n: int) -> float:
    """Exact integer summation for P(Binomial(n, 1/2) <= k)."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be a nonnegative integer")
    if not isinstance(k, int) or isinstance(k, bool):
        raise ValueError("k must be an integer")
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(math.comb(n, j) for j in range(k + 1)) / (1 << n)


def sign_pvalue(values, threshold=0.0, direction="greater") -> float:
    """One-sided exact test of P(X > threshold) <= 1/2 (or X < threshold).

    Equal observations remain in n as nonsuccesses. They are NOT discarded.
    This makes threshold ties conservative for the strict-majority claim.
    Multiplicity and repeated looks must be handled by the caller.
    """
    xs = _samples(values)
    if not math.isfinite(threshold) or direction not in ("greater", "less"):
        raise ValueError("Invalid threshold or direction")
    wins = sum(x > threshold if direction == "greater" else x < threshold for x in xs)
    return binomial_half_cdf(len(xs) - wins, len(xs))


def exact_median_interval(values, *, alpha=0.05, bounds=(-math.inf, math.inf)) -> Interval:
    """Noninterpolated order-statistic CI, conservative with atoms/ties.

    Choose the largest k with P(Bin(n, 1/2) <= k-1) <= alpha/2 and return
    [X_(k), X_(n-k+1)]. If no k qualifies, return the full known support.
    This is a fixed-look CI; use scheduled_median_analysis for monitoring.
    """
    _probability(alpha)
    xs = sorted(_samples(values))
    lo, hi = map(float, bounds)
    if math.isnan(lo) or math.isnan(hi) or lo >= hi or xs[0] < lo or xs[-1] > hi:
        raise ValueError("Invalid support or out-of-support observations")
    n = len(xs)
    k = 0
    for candidate in range(1, n // 2 + 1):
        if binomial_half_cdf(candidate - 1, n) <= alpha / 2:
            k = candidate
        else:
            break
    return Interval(median(xs), xs[k-1] if k else lo, xs[n-k] if k else hi,
                    n, alpha, "population median of the round-level quantity",
                    "exact noninterpolated binomial order statistics")


def classify_interval(interval: Interval, *, margin=0.5, precision=0.25):
    """Positive means improvement; precision is a maximum CI half-width.

    Practical equivalence concerns the interval's estimand, not its tails.
    A precise result straddling a decision boundary remains inconclusive.
    """
    if margin <= 0 or precision <= 0 or not all(map(math.isfinite, (margin, precision))):
        raise ValueError("Margin and precision must be finite and positive")
    if interval.lower > margin:
        return "meaningful_improvement"
    if interval.upper < -margin:
        return "meaningful_degradation"
    if interval.lower >= -margin and interval.upper <= margin:
        return "practically_equivalent"
    if interval.width <= 2 * precision:
        return "precise_but_inconclusive"
    return "continue"


def scheduled_median_analysis(values, *, endpoint_count: int, looks=(16, 32, 64),
                              family_alpha=0.04, bounds=(-100.0, 100.0),
                              margin=0.5, precision=0.25,
                              iid_assumption_acknowledged=False):
    """Primary analysis at a registered look; Bonferroni across endpoints/looks.

    Do not set endpoint_count to the number of endpoints that happen to survive.
    It is the complete number registered before any fresh responses are read.
    Directional p-values shown are adjusted for both directions, every endpoint
    and every look; this is conservative and aligns with the two-sided CI.
    """
    _probability(family_alpha, "family_alpha")
    if not isinstance(endpoint_count, int) or isinstance(endpoint_count, bool) or endpoint_count < 1:
        raise ValueError("endpoint_count must be a positive integer")
    looks = tuple(looks)
    if not looks or any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in looks) or tuple(sorted(set(looks))) != looks:
        raise ValueError("Looks must be distinct increasing positive integers")
    xs = _samples(values)
    if len(xs) not in looks:
        raise ValueError("An unregistered look cannot drive a primary decision")
    alpha = family_alpha / (endpoint_count * len(looks))
    interval = exact_median_interval(xs, alpha=alpha, bounds=bounds)
    adjustment = 2 * endpoint_count * len(looks)
    decision = classify_interval(interval, margin=margin, precision=precision)
    if not iid_assumption_acknowledged:
        decision = "assumption_not_established"
    elif decision == "continue" and len(xs) == looks[-1]:
        decision = "maximum_rounds_inconclusive"
    return {
        **interval.as_dict(), "family_alpha": family_alpha,
        "endpoint_count": endpoint_count, "scheduled_looks": list(looks),
        "margin": margin, "precision_half_width": precision,
        "decision": decision,
        "p_improvement_adjusted": min(1.0, adjustment * sign_pvalue(xs, margin, "greater")),
        "p_degradation_adjusted": min(1.0, adjustment * sign_pvalue(xs, -margin, "less")),
        "n_strict_improvements": sum(x > margin for x in xs),
        "n_strict_degradations": sum(x < -margin for x in xs),
        "n_threshold_ties": sum(x in (-margin, margin) for x in xs),
        "iid_assumption_acknowledged": iid_assumption_acknowledged,
        "identical_observations": len(set(xs)) == 1,
    }


def _logmeanexp(values):
    maximum = max(values)
    if maximum == math.inf:
        return math.inf
    if maximum == -math.inf:
        return -math.inf
    return maximum + math.log(sum(math.exp(x - maximum) for x in values) / len(values))


def _log_wealth(xs, candidate, fractions, direction):
    """One-sided mixture of nonnegative betting martingales, normalized [0,1]."""
    if direction == "lower":
        ys, candidate = xs, candidate
    else:
        ys, candidate = tuple(1-x for x in xs), 1-candidate
    if candidate == 0:
        if any(y > 0 for y in ys):
            return math.inf
        return _logmeanexp([len(ys) * math.log1p(-c) for c in fractions])
    logs = []
    for c in fractions:
        logs.append(sum(math.log1p(c * (y / candidate - 1)) for y in ys))
    return _logmeanexp(logs)


def betting_mean_cs(values, *, bounds=(0.0, 1.0), alpha=0.01,
                    fractions=DEFAULT_FRACTIONS) -> Interval:
    """Time-uniform bounded-mean CS using a frozen fixed-fraction mixture.

    For X in [0,1] and c in (0,1), positive wealth has factors
    1 + c*(X/m - 1), and negative wealth applies the same to 1-X and 1-m.
    Each side is compared with 2/alpha. Ville plus a union bound controls
    both sides at every time. Mixture fractions must not be fitted to this run.
    Numerical roots are rounded outward, preserving conservative inclusion.
    """
    _probability(alpha)
    xs = _samples(values, bounds)
    fractions = tuple(fractions)
    if not fractions:
        raise ValueError("A frozen nonempty mixture is required")
    for c in fractions:
        _probability(c, "fraction")
    a, b = map(float, bounds)
    unit = tuple((x-a)/(b-a) for x in xs)
    threshold = math.log(2/alpha)
    left, right = 0.0, 1.0
    if _log_wealth(unit, 0.0, fractions, "lower") >= threshold:
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = (lo+hi)/2
            if _log_wealth(unit, mid, fractions, "lower") >= threshold:
                lo = mid
            else:
                hi = mid
        left = lo  # outward from excluded lower candidates
    if _log_wealth(unit, 1.0, fractions, "upper") >= threshold:
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = (lo+hi)/2
            if _log_wealth(unit, mid, fractions, "upper") >= threshold:
                hi = mid
            else:
                lo = mid
        right = hi  # outward from excluded upper candidates
    return Interval(mean(xs), a+(b-a)*left, a+(b-a)*right, len(xs), alpha,
                    "constant conditional mean of the round-level quantity",
                    "two-sided fixed-mixture betting confidence sequence")


def scheduled_hoeffding_interval(values, *, bounds=(0.0, 1.0), alpha=0.05) -> Interval:
    """Reference fixed-look bound; alpha must already include look multiplicity."""
    _probability(alpha)
    xs = _samples(values, bounds)
    lo, hi = map(float, bounds)
    radius = (hi-lo) * math.sqrt(math.log(2/alpha)/(2*len(xs)))
    center = mean(xs)
    return Interval(center, max(lo, center-radius), min(hi, center+radius),
                    len(xs), alpha, "constant conditional mean", "fixed-look Hoeffding")


def panel_mae(predictions: Sequence[float], targets: Sequence[float],
              cell_weights: Sequence[float]) -> float:
    """One complete panel produces ONE loss in pp, regardless of cell count."""
    q, p = _samples(predictions, (0, 1)), _samples(targets, (0, 1))
    w = _samples(cell_weights)
    if len(q) != len(p) or len(p) != len(w) or any(x < 0 for x in w) or not math.isclose(sum(w), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("Complete equal-length panels and nonnegative unit-sum weights required")
    return 100 * sum(a * abs(x-y) for x, y, a in zip(q, p, w))


def panel_mae_upper_bound(targets, cell_weights) -> float:
    """Tight support upper bound from fixed survey targets (not observed runs)."""
    p, w = _samples(targets, (0, 1)), _samples(cell_weights)
    if len(p) != len(w) or any(x < 0 for x in w) or not math.isclose(sum(w), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("Invalid panel weights")
    return 100 * sum(a * max(x, 1-x) for x, a in zip(p, w))


def family_stop(decisions: Mapping[str, Mapping], *, required_endpoints,
                budget_exhausted=False, operational_failure=False):
    """Symmetric global stopping; never stop because just one result is favorable."""
    if operational_failure:
        return "stop_operational_failure"
    if budget_exhausted:
        return "stop_budget_report_unresolved"
    required = tuple(required_endpoints)
    if not required or len(set(required)) != len(required) or set(required) != set(decisions):
        raise ValueError("Every frozen endpoint must appear exactly once")
    states = [decisions[key]["decision"] for key in required]
    if "assumption_not_established" in states:
        return "do_not_claim_inference_assumption_unestablished"
    terminal = {"meaningful_improvement", "meaningful_degradation", "practically_equivalent",
                "precise_but_inconclusive", "maximum_rounds_inconclusive"}
    return "stop_all_endpoints_resolved_or_capped" if all(x in terminal for x in states) else "continue"
