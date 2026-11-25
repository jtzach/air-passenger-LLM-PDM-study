"""Independent algebra, exact finite-sample coverage, and stopping checks.

Run: python -m unittest discover -s tests -p test_sequential_inference.py -v
No API calls, random simulation, or external packages are used.
"""
import itertools
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sequential_inference import (
    DEFAULT_FRACTIONS, Interval, _log_wealth, betting_mean_cs,
    binomial_half_cdf, classify_interval, exact_median_interval,
    family_stop, panel_mae, panel_mae_upper_bound, scheduled_median_analysis,
    scheduled_hoeffding_interval, sign_pvalue,
)


class ExactMedianTests(unittest.TestCase):
    def test_exact_binomial_reference(self):
        self.assertEqual([binomial_half_cdf(k, 4) for k in range(5)],
                         [1/16, 5/16, 11/16, 15/16, 1])
        self.assertEqual(binomial_half_cdf(-1, 4), 0)
        self.assertEqual(sign_pvalue([1]*16), 1/65536)

    def test_threshold_ties_are_not_removed(self):
        self.assertEqual(sign_pvalue([.5]*16, .5), 1.0)
        self.assertEqual(sign_pvalue([1]*8 + [.5]*8, .5), binomial_half_cdf(8, 16))

    def test_published_order_statistic_formula(self):
        # For n=20, tails through 5 are .0206947, so the 95% CI uses ranks 6,15.
        ci = exact_median_interval(range(1, 21), alpha=.05)
        self.assertEqual((ci.lower, ci.upper), (6, 15))
        self.assertEqual(ci.estimate, 10.5)

    def test_insufficient_rounds_use_full_support(self):
        ci = exact_median_interval([2]*3, alpha=.001, bounds=(-30, 5))
        self.assertEqual((ci.lower, ci.upper), (-30, 5))

    def test_ties_allow_median_but_not_mean_zero_width(self):
        median_ci = exact_median_interval([.3]*32, alpha=.001, bounds=(0, 1))
        mean_ci = betting_mean_cs([.3]*32, alpha=.001)
        self.assertEqual((median_ci.lower, median_ci.upper), (.3, .3))
        self.assertGreater(mean_ci.width, .05)

    def test_exhaustive_sequential_coverage_under_fair_signs(self):
        # All 4,096 equally likely IID paths. 0 is a population median of +/-1.
        # Bonferroni across three inspections must bound *ever* excluding 0.
        looks, family_alpha, endpoints = (4, 8, 12), .2, 2
        cache = {}
        for n in looks:
            for wins in range(n+1):
                ci = exact_median_interval([-1]*(n-wins)+[1]*wins,
                    alpha=family_alpha/(endpoints*len(looks)), bounds=(-1, 1))
                cache[n, wins] = not ci.lower <= 0 <= ci.upper
        failed = 0
        for path in itertools.product((0, 1), repeat=looks[-1]):
            failed += any(cache[n, sum(path[:n])] for n in looks)
        self.assertLessEqual(failed / 2**looks[-1], family_alpha/endpoints)

    def test_direction_symmetry_and_pvalue_alignment(self):
        options = dict(endpoint_count=16, iid_assumption_acknowledged=True)
        positive = scheduled_median_analysis([1]*16, **options)
        negative = scheduled_median_analysis([-1]*16, **options)
        self.assertEqual(positive["decision"], "meaningful_improvement")
        self.assertEqual(negative["decision"], "meaningful_degradation")
        self.assertEqual(positive["p_improvement_adjusted"], negative["p_degradation_adjusted"])
        self.assertLessEqual(positive["p_improvement_adjusted"], .04)
        self.assertEqual(positive["lower"], -negative["upper"])

    def test_multiplicity_assumptions_and_registered_looks(self):
        with self.assertRaises(ValueError):
            scheduled_median_analysis([1]*15, endpoint_count=16)
        with self.assertRaises(ValueError):
            scheduled_median_analysis([1]*16, endpoint_count=0)
        with self.assertRaises(ValueError):
            scheduled_median_analysis([1]*16, endpoint_count=1, looks=(16, 16))
        result = scheduled_median_analysis([1]*16, endpoint_count=16)
        self.assertEqual(result["decision"], "assumption_not_established")
        self.assertEqual(result["alpha"], .04/(16*3))

    def test_median_equivalence_and_inconclusive_cap(self):
        options = dict(endpoint_count=16, iid_assumption_acknowledged=True)
        equivalent = scheduled_median_analysis([0]*16, **options)
        uncertain = scheduled_median_analysis([-1, 1]*32, **options)
        self.assertEqual(equivalent["decision"], "practically_equivalent")
        self.assertEqual(uncertain["decision"], "maximum_rounds_inconclusive")


class BettingMeanTests(unittest.TestCase):
    def test_expected_wealth_is_one_under_nonhalf_bernoulli(self):
        # Exact integration of the wealth under the tested true mean.
        p, n = .2, 8
        for direction in ("lower", "upper"):
            expectation = 0
            for wins in range(n+1):
                xs = (1,)*wins + (0,)*(n-wins)
                probability = math.comb(n, wins)*p**wins*(1-p)**(n-wins)
                expectation += probability*math.exp(_log_wealth(xs, p, DEFAULT_FRACTIONS, direction))
            self.assertAlmostEqual(expectation, 1.0, places=11)

    def test_exact_anytime_error_probability(self):
        # At every prefix of every fair-Bernoulli path, not just the final look.
        n, alpha, p = 12, .2, .5
        cache = {}
        threshold = math.log(2/alpha)
        for t in range(1, n+1):
            for wins in range(t+1):
                xs = (1,)*wins + (0,)*(t-wins)
                cache[t, wins] = any(_log_wealth(xs, p, DEFAULT_FRACTIONS, side) >= threshold
                                    for side in ("lower", "upper"))
        failed = 0
        for path in itertools.product((0, 1), repeat=n):
            failed += any(cache[t, sum(path[:t])] for t in range(1, n+1))
        self.assertLessEqual(failed / 2**n, alpha)

    def test_endpoints_scaling_and_mirror_symmetry(self):
        xs = [.1, .2, .4, .7]*4
        ci = betting_mean_cs(xs, alpha=.02)
        scaled = betting_mean_cs([100*x-25 for x in xs], bounds=(-25, 75), alpha=.02)
        mirror = betting_mean_cs([1-x for x in xs], alpha=.02)
        self.assertAlmostEqual(scaled.lower, 100*ci.lower-25, places=10)
        self.assertAlmostEqual(scaled.upper, 100*ci.upper-25, places=10)
        self.assertAlmostEqual(mirror.lower, 1-ci.upper, places=12)
        self.assertAlmostEqual(mirror.upper, 1-ci.lower, places=12)
        self.assertLessEqual(ci.lower, ci.estimate)
        self.assertGreaterEqual(ci.upper, ci.estimate)
        zero = betting_mean_cs([0]*80)
        one = betting_mean_cs([1]*80)
        self.assertEqual(zero.lower, 0)
        self.assertEqual(one.upper, 1)
        self.assertGreater(zero.upper, 0)
        self.assertLess(one.lower, 1)

    def test_validity_checks_and_lower_alpha_widens_interval(self):
        for xs in ([], [float("nan")], [-.1], [1.1]):
            with self.assertRaises(ValueError):
                betting_mean_cs(xs)
        with self.assertRaises(ValueError):
            betting_mean_cs([.2], fractions=(1.0,))
        xs = [.1]*40
        self.assertGreaterEqual(betting_mean_cs(xs, alpha=.001).width,
                                betting_mean_cs(xs, alpha=.05).width)

    def test_hoeffding_reference_known_radius(self):
        ci = scheduled_hoeffding_interval([.5]*100, alpha=.05)
        radius = math.sqrt(math.log(40)/200)
        self.assertAlmostEqual(ci.lower, .5-radius)
        self.assertAlmostEqual(ci.upper, .5+radius)


class PanelAndStoppingTests(unittest.TestCase):
    def test_one_round_weights_and_analytic_support(self):
        self.assertAlmostEqual(panel_mae([.1, .9], [.2, .5], [.25, .75]), 32.5)
        upper = panel_mae_upper_bound([.2, .5], [.25, .75])
        self.assertAlmostEqual(upper, 57.5)
        self.assertAlmostEqual(panel_mae([1, 1], [.2, .5], [.25, .75]), upper)
        with self.assertRaises(ValueError):
            panel_mae([.1], [.2, .5], [.25, .75])
        with self.assertRaises(ValueError):
            panel_mae([.1, .9], [.2, .5], [1, 1])

    def test_never_stop_for_one_favorable_result(self):
        decisions = {"a": {"decision": "meaningful_improvement"},
                     "b": {"decision": "continue"}}
        self.assertEqual(family_stop(decisions, required_endpoints=("a", "b")), "continue")
        decisions["b"]["decision"] = "meaningful_degradation"
        self.assertEqual(family_stop(decisions, required_endpoints=("a", "b")),
                         "stop_all_endpoints_resolved_or_capped")
        self.assertEqual(family_stop(decisions, required_endpoints=("a", "b"), budget_exhausted=True),
                         "stop_budget_report_unresolved")
        with self.assertRaises(ValueError):
            family_stop(decisions, required_endpoints=("a",))

    def test_boundary_precision_does_not_become_significance(self):
        ci = Interval(.5, .4, .6, 64, .001, "median", "test fixture")
        self.assertEqual(classify_interval(ci, margin=.5, precision=.25), "precise_but_inconclusive")


if __name__ == "__main__":
    unittest.main(verbosity=2)
