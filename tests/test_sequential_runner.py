"""Offline runner tests; all network responses are local fixtures."""
from copy import deepcopy
from pathlib import Path
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from run_sequential_experiment import (
    SafeTransport, atomic_json, baseline_and_cap, execute, freeze_plan,
    panel_loss, parse_prediction, request_tasks, validate_config,
)
from run_experiment import read_json, sha


def configuration(directory):
    catalogue = Path(directory)/"catalogue.json"
    atomic_json(catalogue, {"data": [{"id": "test/model", "pricing": {
        "prompt": "0.000001", "completion": "0.000002", "request": "0"}}]})
    return {
        "models": [{"id": "test/model"}], "looks": [2, 4], "endpoint_count": 1,
        "primary_family_alpha": .04, "secondary_alpha_per_endpoint": .01,
        "temperature": .7, "max_tokens": 450, "seed_base": 25112026,
        "max_cost_usd": 10, "max_runtime_seconds": 60, "max_workers": 1,
        "transport_attempts": 3, "request_timeout_seconds": 3,
        "iid_assumption_acknowledged": True, "catalogue_path": str(catalogue),
        "panels": [{"panel_id": "test", "modes": ["a", "b"], "arms": ["unanchored"],
            "mutually_exclusive": False, "baseline": {"a": .5, "b": .5},
            "cards": [{"card_id": "one", "feature": "generic", "description": "PRIVATE_METADATA",
                       "weight": .4, "observed": {"a": .0123456789, "b": .4}},
                      {"card_id": "two", "feature": "generic", "description": "PRIVATE_DESCRIPTION",
                       "weight": .6, "observed": {"a": .2, "b": .8}}],
            "prompts": {"unanchored": {"one": "APPROVED_ONE", "two": "APPROVED_TWO",
                                       "no_persona": "APPROVED_CONTROL"}}}],
    }


def envelope(a=.2, b=.8, gid="generation-1", provider="provider-one"):
    return {"id": gid, "provider": provider, "model": "test/model",
            "choices": [{"message": {"content": json.dumps({"a": a, "b": b, "rationale": "Possible explanation."})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "cost": .0001}}


class FakeTransport:
    def __init__(self, fail_round=None, drift_round=None, budget_round=None):
        self.spent, self.tasks = 0, []
        self.fail_round, self.drift_round, self.budget_round = fail_round, drift_round, budget_round

    def run(self, task):
        self.tasks.append(task)
        if task["round"] == self.budget_round:
            return {"status": "budget_stop"}
        self.spent += .0001
        if task["round"] == self.fail_round:
            return {"status": "invalid_output"}
        return {"status": "valid", "prediction": {"a": .2, "b": .8},
                "returned_provider": "changed" if task["round"] == self.drift_round else "fixed",
                "returned_model": "test/model", "generation_id": task["task_id"]}


class PromptAndFreezeTests(unittest.TestCase):
    def test_private_fields_cannot_change_payload(self):
        with tempfile.TemporaryDirectory() as d:
            config = configuration(d)
            first = request_tasks(config, 1)
            changed = deepcopy(config)
            p = changed["panels"][0]
            p["baseline"] = {"a": .0123456789, "b": .987654321}
            p["cards"][0].update(weight=.9, observed={"a": .8, "b": .2}, description="SECRET_NEW")
            p["cards"][1]["weight"] = .1
            self.assertEqual(first, request_tasks(changed, 1))
            payloads = json.dumps([x["request"] for x in first])
            self.assertNotIn("0.0123456789", payloads)
            self.assertNotIn("PRIVATE", payloads)
            self.assertNotIn("observed", payloads)
            self.assertEqual({x["request"]["messages"][0]["content"] for x in first},
                             {"APPROVED_ONE", "APPROVED_TWO", "APPROVED_CONTROL"})

    def test_freeze_and_prepare_never_need_key_or_call_network(self):
        with tempfile.TemporaryDirectory() as d:
            config = configuration(d)
            out = Path(d)/"run"
            with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen", side_effect=AssertionError("network")):
                report = execute(config, out, prepare_only=True)
            self.assertEqual(report["status"], "prepared_only_no_calls")
            self.assertEqual(report["maximum_planned_requests"], 12)
            self.assertFalse((out/"raw").exists())
            before = (out/"frozen_plan.json").read_bytes()
            freeze_plan(config, out)
            self.assertEqual(before, (out/"frozen_plan.json").read_bytes())
            changed = deepcopy(config)
            changed["panels"][0]["cards"][0]["observed"]["a"] = .3
            with self.assertRaises(RuntimeError):
                freeze_plan(changed, out)

    def test_endpoint_registry_and_prompts_must_be_complete(self):
        with tempfile.TemporaryDirectory() as d:
            config = configuration(d)
            validate_config(config)
            config["endpoint_count"] = 2
            with self.assertRaises(ValueError): validate_config(config)
            config["endpoint_count"] = 1
            del config["panels"][0]["prompts"]["unanchored"]["no_persona"]
            with self.assertRaises(ValueError): validate_config(config)

    def test_provider_pin_is_explicit_in_every_request(self):
        with tempfile.TemporaryDirectory() as d:
            config = configuration(d)
            config["models"][0]["provider_only"] = ["provider/variant"]
            validate_config(config)
            for task in request_tasks(config, 1):
                self.assertEqual(task["request"]["provider"]["only"], ["provider/variant"])
                self.assertFalse(task["request"]["provider"]["allow_fallbacks"])
            config["models"][0]["provider_only"] = []
            with self.assertRaises(ValueError): validate_config(config)


class ParsingAndTransportTests(unittest.TestCase):
    def test_exclusive_normalization_is_small_logged_and_nonexclusive_untouched(self):
        raw, normalized, detail = parse_prediction(envelope(.2, .799), ["a", "b"], True)
        self.assertEqual(raw["b"], .799)
        self.assertAlmostEqual(normalized["a"]+normalized["b"], 1)
        self.assertTrue(detail["normalized"])
        raw, normalized, _ = parse_prediction(envelope(.8, .8), ["a", "b"], False)
        self.assertEqual(raw, normalized)
        with self.assertRaises(ValueError): parse_prediction(envelope(.2, .7), ["a", "b"], True)
        with self.assertRaises(ValueError): parse_prediction(envelope(True, .8), ["a", "b"], False)
        with self.assertRaises(ValueError): parse_prediction(envelope(float("nan"), .8), ["a", "b"], False)

    def test_paid_call_logging_cache_and_key_redaction(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"OPENROUTER_API_KEY": "SECRET_TEST_KEY"}):
            config, seen = configuration(d), []
            task = request_tasks(config, 1)[0]
            def opener(request, timeout):
                seen.append(json.loads(request.data))
                response = envelope()
                response["user_id"] = "private-account"
                return io.BytesIO(json.dumps(response).encode())
            transport = SafeTransport(config, Path(d)/"raw", time.monotonic()+10, opener=opener)
            record = transport.run(task)
            self.assertEqual(record["status"], "valid")
            self.assertEqual(seen, [task["request"]])
            transport.run(task)
            self.assertEqual(len(seen), 1)
            self.assertAlmostEqual(transport.spent, .0001)
            for f in (Path(d)/"raw").glob("*.json"):
                self.assertNotIn("SECRET_TEST_KEY", f.read_text())
                self.assertNotIn("private-account", f.read_text())

    def test_invalid_output_is_not_retried_and_budget_stops_before_call(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"OPENROUTER_API_KEY": "SECRET_TEST_KEY"}):
            config, calls = configuration(d), []
            def opener(request, timeout):
                calls.append(1)
                bad = envelope()
                bad["choices"][0]["message"]["content"] = '{"unexpected":1}'
                return io.BytesIO(json.dumps(bad).encode())
            transport = SafeTransport(config, Path(d)/"raw", time.monotonic()+10, opener=opener)
            self.assertEqual(transport.run(request_tasks(config, 1)[0])["status"], "invalid_output")
            self.assertEqual(len(calls), 1)
            config["max_cost_usd"] = .00001
            self.assertEqual(transport.run(request_tasks(config, 2)[0])["status"], "budget_stop")
            self.assertEqual(len(calls), 1)

    def test_interrupted_request_is_not_silently_repeated(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"OPENROUTER_API_KEY": "SECRET_TEST_KEY"}):
            config = configuration(d)
            task = request_tasks(config, 1)[0]
            dest = Path(d)/"raw"/(task["task_id"]+".json")
            atomic_json(dest, {"request_sha256": sha(task["request"]), "status": "in_progress", "accounted_cost_usd": .01})
            transport = SafeTransport(config, Path(d)/"raw", time.monotonic()+10,
                                      opener=lambda *a, **k: self.fail("No resubmission"))
            self.assertEqual(transport.run(task)["status"], "interrupted_unknown_outcome")
            self.assertEqual(transport.spent, .01)


class DriverTests(unittest.TestCase):
    def test_full_run_has_one_score_per_complete_round(self):
        with tempfile.TemporaryDirectory() as d:
            config, transport = configuration(d), FakeTransport()
            with patch("builtins.print"):
                report = execute(config, Path(d)/"run", prepare_only=False, transport=transport)
            block = next(iter(report["blocks"].values()))
            self.assertEqual(len(transport.tasks), 12)
            self.assertEqual(block["complete_rounds"], 4)
            self.assertEqual([x["round"] for x in block["looks"]], [2, 4])
            self.assertEqual(block["halt_reason"], "maximum_rounds_inconclusive")
            self.assertEqual(block["looks"][-1]["primary_median"]["n"], 4)

    def test_first_incomplete_round_halts_without_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            config, transport = configuration(d), FakeTransport(fail_round=2)
            with patch("builtins.print"):
                report = execute(config, Path(d)/"run", prepare_only=False, transport=transport)
            block = next(iter(report["blocks"].values()))
            self.assertEqual(block["complete_rounds"], 1)
            self.assertEqual(block["halt_reason"], "incomplete_round_invalid_output")
            self.assertEqual(len(transport.tasks), 4)
            self.assertEqual(block["looks"], [])

    def test_provider_drift_halts_and_disables_claims(self):
        with tempfile.TemporaryDirectory() as d:
            config, transport = configuration(d), FakeTransport(drift_round=2)
            with patch("builtins.print"):
                report = execute(config, Path(d)/"run", prepare_only=False, transport=transport)
            block = next(iter(report["blocks"].values()))
            self.assertEqual(block["complete_rounds"], 1)
            self.assertFalse(block["inference_assumptions_ok"])
            self.assertEqual(block["halt_reason"], "provider_or_model_changed")

    def test_budget_stop_does_not_create_unregistered_inference(self):
        with tempfile.TemporaryDirectory() as d:
            config, transport = configuration(d), FakeTransport(budget_round=2)
            with patch("builtins.print"):
                report = execute(config, Path(d)/"run", prepare_only=False, transport=transport)
            block = next(iter(report["blocks"].values()))
            self.assertEqual(report["global_stop"], "cost_cap")
            self.assertEqual(block["complete_rounds"], 1)
            self.assertEqual(block["looks"], [])

    def test_local_scoring_and_cap(self):
        with tempfile.TemporaryDirectory() as d:
            panel = configuration(d)["panels"][0]
            observed = {c["card_id"]: c["observed"] for c in panel["cards"]}
            self.assertEqual(panel_loss(panel, observed), 0)
            baseline, cap = baseline_and_cap(panel)
            self.assertGreaterEqual(cap, baseline)
            self.assertEqual(baseline, panel_loss(panel, {c["card_id"]: panel["baseline"] for c in panel["cards"]}))

    def test_exclusive_cap_matches_simplex_vertices_and_is_tighter(self):
        panel = {"modes": ["a", "b", "c"], "mutually_exclusive": True,
                 "baseline": {"a": .2, "b": .3, "c": .5},
                 "cards": [{"card_id": "one", "weight": .4, "observed": {"a": .2, "b": .3, "c": .5}},
                           {"card_id": "two", "weight": .6, "observed": {"a": .1, "b": .4, "c": .5}}]}
        _, cap = baseline_and_cap(panel)
        worst = {c["card_id"]: {"a": 1, "b": 0, "c": 0} for c in panel["cards"]}
        self.assertAlmostEqual(cap, panel_loss(panel, worst))
        self.assertAlmostEqual(cap, 100*(.4*1.6+.6*1.8)/3)
        for mode in panel["modes"]:
            vertex = {c["card_id"]: {m: float(m==mode) for m in panel["modes"]} for c in panel["cards"]}
            self.assertLessEqual(panel_loss(panel, vertex), cap)
        panel["mutually_exclusive"] = False
        _, componentwise = baseline_and_cap(panel)
        self.assertLess(cap, componentwise)


if __name__ == "__main__":
    unittest.main(verbosity=2)
