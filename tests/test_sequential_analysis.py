"""Offline integration checks of scoring, exclusions, and publication scope."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from analyse_sequential_results import analyze, label, metrics, read, save_json
from run_sequential_experiment import SafeTransport, execute


def fixture_config(directory):
    models = [{"id": "openai/gpt-4.1", "label": "GPT-4.1"},
              {"id": "google/gemma-3-4b-it", "label": "Gemma 3 4B"}]
    catalogue = Path(directory)/"catalogue.json"
    save_json(catalogue, {"data": [{"id": m["id"], "pricing": {"prompt": ".000001", "completion": ".000002"}} for m in models]})
    mid = {"panel_id": "mid_2023", "modes": ["car", "local_pt", "long_distance_rail"],
           "arms": ["unanchored", "overall_rate_anchored"], "mutually_exclusive": False,
           "baseline": {"car": .6, "local_pt": .2, "long_distance_rail": .3},
           "cards": [{"card_id": "one", "feature": "anzauto_gr1", "weight": .25,
                      "description": "The only supplied cohort attribute is cars: No car. All other information is unspecified.",
                      "observed": {"car": .5, "local_pt": .2, "long_distance_rail": .3}},
                     {"card_id": "two", "feature": "anzauto_gr1", "weight": .75,
                      "description": "The only supplied cohort attribute is cars: 4 or more cars. All other information is unspecified.",
                      "observed": {"car": .7, "local_pt": .2, "long_distance_rail": .3}}], "prompts": {}}
    for arm in mid["arms"]:
        mid["prompts"][arm] = {cid: f"MID|{arm}|{cid}" for cid in ("one", "two", "no_persona")}
    fmg_cards = [{"card_id": f"fmg_{purpose}_{region}", "feature": "purpose_x_flight_region",
                 "description": "PUBLIC GENERIC CARD", "weight": 1/6,
                 "observed": {"car": .3, "transit": .7}, "original_native_counts": "PRIVATE_NATIVE_COUNTS"}
                for purpose in ("business", "private") for region in ("domestic", "continental", "intercontinental")]
    fmg = {"panel_id": "fmg_2025", "modes": ["car", "transit"], "arms": ["unanchored"],
           "mutually_exclusive": True, "baseline": {"car": .3, "transit": .7}, "cards": fmg_cards,
           "source_private_note": "CONFIDENTIAL_SOURCE_30_ROWS",
           "prompts": {"unanchored": {c: "FMG|"+c for c in [x["card_id"] for x in fmg_cards]+["no_persona"]}}}
    return {"models": models, "panels": [mid, fmg], "looks": [2, 4], "endpoint_count": 6,
            "primary_family_alpha": .04, "secondary_alpha_per_endpoint": .01/6,
            "temperature": .7, "max_tokens": 450, "seed_base": 100,
            "max_cost_usd": 10, "max_runtime_seconds": 60, "max_workers": 1,
            "transport_attempts": 3, "request_timeout_seconds": 3,
            "iid_assumption_acknowledged": True, "catalogue_path": str(catalogue)}


class SequentialAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = fixture_config(self.root)
        self.config_path = self.root/"private_config.json"
        save_json(self.config_path, self.config)
        self.run, self.output = self.root/"run", self.root/"public"
        counter = [0]

        def opener(request, timeout):
            body = json.loads(request.data)
            text, model, round_number = body["messages"][0]["content"], body["model"], body["seed"]-99
            counter[0] += 1
            provider = "fixed"
            if text.startswith("MID|unanchored") and "gemma" in model and round_number >= 3:
                provider = "changed"
            if text.startswith("FMG"):
                prediction = {"car": .2, "transit": .8, "rationale": "Possible hypothesis."}
            else:
                prediction = {"car": .4 if round_number % 2 else .6,
                              "local_pt": .2, "long_distance_rail": .3, "rationale": "Possible hypothesis."}
            if text.startswith("FMG") and model == "openai/gpt-4.1":
                prediction = {"wrong_format": 1}
            response = {"id": f"unique-{counter[0]}", "model": model, "provider": provider,
                        "usage": {"cost": .00001},
                        "choices": [{"message": {"content": json.dumps(prediction)}}]}
            return io.BytesIO(json.dumps(response).encode())

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "TEST_ONLY_FAKE_KEY"}):
            transport = SafeTransport(self.config, self.run/"raw", time.monotonic()+60, opener=opener)
            with patch("builtins.print"):
                self.summary = execute(self.config, self.run, prepare_only=False, transport=transport)

    def test_complete_prefix_ensemble_and_round_estimands_differ(self):
        qa = analyze(self.config_path, self.run, self.output)
        numbers = read(self.output/"table_numbers.json")
        block = next(b for b in numbers["blocks"] if b["panel_id"] == "mid_2023" and
                     b["model_id"] == "openai/gpt-4.1" and b["arm"] == "overall_rate_anchored")
        self.assertEqual(qa["reported_blocks"], 6)
        self.assertEqual(block["complete_prefix_rounds"], 4)
        self.assertAlmostEqual(block["ensemble_mae_pp"], 5)
        self.assertAlmostEqual(block["mean_single_round_mae_pp"], 100*(.25*.1+.75*.2)/3)
        self.assertLess(block["ensemble_mae_pp"], block["mean_single_round_mae_pp"])
        self.assertEqual(block["primary_checkpoint_round"], 4)

    def test_failed_and_drift_blocks_remain_visible_without_claims(self):
        analyze(self.config_path, self.run, self.output)
        blocks = read(self.output/"table_numbers.json")["blocks"]
        missing = next(b for b in blocks if b["panel_id"] == "fmg_2025" and b["model_id"] == "openai/gpt-4.1")
        drift = next(b for b in blocks if b["panel_id"] == "mid_2023" and "gemma" in b["model_id"] and b["arm"] == "unanchored")
        self.assertEqual(missing["complete_prefix_rounds"], 0)
        self.assertNotIn("ensemble_mae_pp", missing)
        self.assertEqual(drift["complete_prefix_rounds"], 2)
        self.assertIsNone(drift["primary_decision"])
        self.assertFalse(drift["inference_assumptions_ok"])
        figures = read(self.output/"figure_data.json")
        self.assertFalse(figures["metadata"]["fmg_model_available"])
        self.assertTrue(all("openai/gpt-4.1" not in row["predictions"] for row in figures["fmg"]))
        self.assertTrue(all("google/gemma-3-4b-it" in row["predictions"] for row in figures["fmg"]))

    def test_only_six_authorized_fmg_derivatives_are_exported(self):
        analyze(self.config_path, self.run, self.output)
        targets = read(self.output/"derived_fmg_targets.json")
        self.assertEqual(len(targets), 6)
        self.assertAlmostEqual(sum(t["weight"] for t in targets), 1)
        for file in self.output.iterdir():
            text = file.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_NATIVE_COUNTS", text)
            self.assertNotIn("CONFIDENTIAL_SOURCE_30_ROWS", text)
            self.assertNotIn("TEST_ONLY_FAKE_KEY", text)
            self.assertNotIn("original_native_counts", text)
        with self.assertRaises(ValueError):
            label({"card_id": "native_vhg_group_01"}, "fmg_2025")

    def test_saved_score_tampering_is_rejected(self):
        summary = read(self.run/"summary.json")
        block = next(b for b in summary["blocks"].values() if b["complete_rounds"])
        block["round_scores"][0]["mae_pp"] += .1
        save_json(self.run/"summary.json", summary)
        with self.assertRaisesRegex(ValueError, "Reconstruction mismatch"):
            analyze(self.config_path, self.run, self.output)
        self.assertFalse(self.output.exists())

    def test_raw_request_tampering_is_rejected(self):
        path = next((self.run/"raw").glob("*.request.json"))
        request = read(path)
        request["messages"][0]["content"] = "different prompt"
        save_json(path, request)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            analyze(self.config_path, self.run, self.output)

    def test_incomplete_study_is_not_analyzed(self):
        (self.run/"summary.json").rename(self.run/"saved_summary.json")
        with self.assertRaisesRegex(RuntimeError, "completed run summary"):
            analyze(self.config_path, self.run, self.output)

    def test_mode_weights_and_categorical_metric(self):
        panel = self.config["panels"][1]
        preds = {c["card_id"]: {"car": .2, "transit": .8} for c in panel["cards"]}
        result = metrics(panel, preds)
        self.assertAlmostEqual(result["mae_pp"], 10)
        self.assertAlmostEqual(result["categorical_total_variation_pp"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
