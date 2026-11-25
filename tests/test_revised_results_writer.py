"""Synthetic edge cases for publication logic, never used as study results."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
import write_revised_results as writer


def fixture(prefix=0):
    numbers = {"completed_utc": "synthetic-test-only", "plan_sha256": "0"*64,
        "registered_endpoint_count": 12, "looks": [16, 32, 64], "primary_family_alpha": .04,
        "secondary_alpha_per_endpoint": .01/12, "practical_margin_pp": .5,
        "baseline_mae_by_panel": {"mid_2023": 6., "fmg_2025": 6.},
        "blocks": [], "availability": [], "hint_comparisons": [],
        "fmg_derived_groups": []}
    details, predictions = {}, []
    for card in sorted(writer.FMG_IDS):
        target = {mode: .1 for mode in writer.FMG_MODES}
        if "_business_" in card:
            target["taxi_ridehail"], target["other"] = .2, 0.
        numbers["fmg_derived_groups"].append({"card_id": card, "group": card, "weight": 1/6, "observed": target})
    for panel in writer.PANELS:
        for model in writer.MODEL_LABELS:
            for arm in writer.ARMS[panel]:
                bid = "|".join((panel, model, arm))
                n = prefix if model == "openai/gpt-4.1" and (panel == "fmg_2025" or arm == "overall_rate_anchored") else 0
                look = 16 if n >= 16 else None
                row = {"block_id": bid, "panel_id": panel, "model_id": model, "arm": arm,
                    "complete_prefix_rounds": n, "halt_reason": "incomplete_round_invalid_output",
                    "baseline_mae_pp": 6., "inference_assumptions_ok": True,
                    "primary_checkpoint_round": look, "primary_decision": "continue" if look else None,
                    "primary_median_gain_pp": 1. if look else None,
                    "primary_lower_pp": -1. if look else None, "primary_upper_pp": 2. if look else None,
                    "mean_cs_lower_pp": -5. if look else None, "mean_cs_upper_pp": 6. if look else None}
                if n:
                    row.update(ensemble_mae_pp=5., no_card_ensemble_mae_pp=8.)
                request_count = n*(24 if panel == "mid_2023" else 7)
                availability = {"block_id": bid, "attempted_requests": request_count,
                    "valid_responses_outside_prefix": 0}
                numbers["blocks"].append(row)
                numbers["availability"].append(availability)
                details[bid] = {"metrics": copy.deepcopy(row), "availability": availability,
                    "latest_primary": {"n": look, "estimate": 1., "lower": -1., "upper": 2.} if look else None}
                if not n:
                    continue
                if panel == "mid_2023":
                    cards = [("cars0", "No car", "anzauto_gr1"), ("cars4", "4 or more cars", "anzauto_gr1"),
                             ("region", "Urban region - small-town and village area", "RegioStaR7")]
                    cards += [(f"filler{i}", f"Synthetic {i}", "synthetic") for i in range(20)]
                    targets = {card: {m: .2 for m in writer.MID_MODES} for card, _, _ in cards}
                    targets["cars4"]["long_distance_rail"] = .1
                else:
                    cards = [(r["card_id"], r["group"], "purpose_region") for r in numbers["fmg_derived_groups"]]
                    targets = {r["card_id"]: r["observed"] for r in numbers["fmg_derived_groups"]}
                for card, group, feature in cards:
                    for mode, target in targets[card].items():
                        predicted = target + (.1 if panel == "fmg_2025" and "_business_" in card and mode == "taxi_ridehail" else .01)
                        predictions.append({"block_id": bid, "panel_id": panel, "model_id": model,
                            "arm": arm, "card_id": card, "group": group, "feature": feature,
                            "mode": mode, "observed": target, "predicted_mean": predicted,
                            "n_rounds": n, "card_weight": 1., "signed_error_pp": 100*(predicted-target)})
    total = sum(r["attempted_requests"] for r in numbers["availability"])
    numbers["cost"] = {"attempted_requests": total, "status_counts": {"valid": total},
        "attempt_records": total, "requests_with_retries": 0, "retained_prefix_requests": total,
        "accounted_cost_usd": .25, "normalized_exclusive_responses": 0, "global_stop": None}
    findings = {"conditional_claim_counts": dict(writer.Counter(r["primary_decision"] or "no_valid_checkpoint" for r in numbers["blocks"]))}
    return numbers, findings, predictions, details


class PublicationWriterTests(unittest.TestCase):
    def test_missing_inputs_do_not_create_placeholder_files(self):
        with tempfile.TemporaryDirectory() as name:
            source, destination = Path(name)/"source", Path(name)/"generated"
            with self.assertRaises(FileNotFoundError):
                writer.write(source, destination)
            self.assertFalse(destination.exists())

    def test_all_failed_blocks_are_reported_without_scores(self):
        args = fixture()
        writer.validate(*args)
        text = writer.metrics_table(args[0], args[3])
        self.assertEqual(text.count("No valid look"), 12)
        self.assertEqual(text.count("invalid output"), 12)
        self.assertIn("A dash means unavailable, not zero", text)
        narrative = writer.results_text(args[0])
        self.assertIn("0 reached a usable registered checkpoint", narrative)
        self.assertIn("conservative estimates", narrative)

    def test_partial_prefix_is_descriptive_only(self):
        args = fixture(7)
        writer.validate(*args)
        table = writer.metrics_table(args[0], args[3])
        self.assertEqual(table.count("No valid look"), 12)
        self.assertIn("7 & 5.00 & 8.00 & ---", table)

    def test_earlier_checkpoint_is_distinguished_from_ensemble_prefix(self):
        args = fixture(20)
        writer.validate(*args)
        table = writer.metrics_table(args[0], args[3])
        self.assertEqual(table.count("20 (16)"), 2)
        self.assertEqual(table.count("Unresolved at last look"), 2)
        self.assertIn("All 2 secondary mean confidence sequences remained inconclusive", writer.results_text(args[0]))

    def test_selected_examples_use_exact_modes_and_purpose_weights(self):
        args = fixture(20)
        rows = writer.observations(args[0], args[2])
        self.assertEqual(len(rows), 4)
        self.assertAlmostEqual(rows[0]["data_pp"], -10.)
        self.assertAlmostEqual(rows[0]["llm_pp"], -10.)
        self.assertAlmostEqual(rows[2]["data_pp"], 10.)
        self.assertAlmostEqual(rows[2]["llm_pp"], 19.)
        self.assertAlmostEqual(sum(rows[2]["normalized_weights"].values()), 2.)
        self.assertEqual(set(rows[3]["modes"]), set(writer.CAR_MODES))
        self.assertNotIn("taxi_ridehail", rows[3]["modes"])

    def test_no_model_replacement_when_fixed_model_unavailable(self):
        args = fixture()
        rows = writer.observations(args[0], args[2])
        self.assertTrue(all(row["llm_pp"] is None for row in rows))
        self.assertIsNotNone(rows[2]["data_pp"])
        self.assertIn("---", writer.observations_table(rows))

    def test_missing_endpoint_and_fabricated_zero_prefix_score_rejected(self):
        args = fixture()
        args[0]["blocks"].pop()
        with self.assertRaisesRegex(ValueError, "twelve registered"):
            writer.validate(*args)
        args = fixture()
        row = args[0]["blocks"][0]
        row["ensemble_mae_pp"] = 0.
        args[3][row["block_id"]]["metrics"] = copy.deepcopy(row)
        with self.assertRaisesRegex(ValueError, "zero-prefix"):
            writer.validate(*args)

    def test_tex_escaping_does_not_leak_special_characters(self):
        self.assertEqual(writer.tex("a_b & 15%"), r"a\_b \& 15\%")
        self.assertEqual(writer.number(-.0001, signed=True), "+0.00")


if __name__ == "__main__":
    unittest.main()
