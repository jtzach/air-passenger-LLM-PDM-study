"""Offline tests of the explicit administrative-pause amendment; no network."""
from copy import deepcopy
from pathlib import Path
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_sequential_runner import configuration, envelope
import run_sequential_experiment as original
from run_experiment import read_json, sha
from resume_sequential_experiment import audit_parent, amended_tasks, initial_blocks, append_score, execute, prepare
from analyse_sequential_results import analyze


def fixture(directory, *, partial="unknown", halt=False, complete_cached=False):
    config = configuration(directory)
    config.update(looks=[4, 8], max_runtime_seconds=600, max_workers=1)
    parent = Path(directory)/"parent"
    original.freeze_plan(config, parent)
    original.atomic_json(parent/"execution_started.json", {"started_utc": "2026-11-25T14:00:00+00:00"})
    block = next(iter(initial_blocks(config).values()))
    for r in (1, 2):
        rr = {}
        for task in original.request_tasks(config, r):
            rec = write_record(parent, task)
            rr[task["card_id"]] = rec
            original.record_identity(block, rec)
        append_score(block, rr, r)
    if halt:
        block["halt_reason"] = "incomplete_round_invalid_output"
        block["incomplete_round"] = 3
    original.atomic_json(parent/"progress.json", {"round": 2, "global_stop": None,
        "blocks": {block["block_id"]: original.public_block_state(block)}})
    tasks = original.request_tasks(config, 3)
    chosen = tasks if complete_cached else tasks[:2]
    for i, task in enumerate(chosen):
        status = "valid" if complete_cached or i == 0 else {"unknown": "in_progress", "invalid": "invalid_output", "valid": "valid"}[partial]
        write_record(parent, task, status=status)
    unknown = [x["task_id"] for x in map(read_json, (parent/"raw").glob("*.json"))
               if x.get("status") == "in_progress"]
    original.atomic_json(parent/"pause_state.json", {"status": "PAUSED_BY_USER",
        "paused_utc": "2026-11-25T14:01:00+00:00", "last_completed_global_round": 2,
        "in_progress_unknown_outcomes": unknown})
    return config, parent


def write_record(directory, task, status="valid", *, provider="provider-one"):
    response = envelope(gid=task["task_id"], provider=provider)
    raw, pred, norm = original.parse_prediction(response, task["modes"], task["mutually_exclusive"])
    rec = {k: v for k, v in task.items() if k != "request"}
    rec.update(status=status, started_utc="2026-11-25T14:00:30+00:00", attempts=[],
        request_sha256=sha(task["request"]), accounted_cost_usd=.03 if status == "in_progress" else .0001)
    if status == "valid":
        rec.update(response=response, raw_prediction=raw, prediction=pred, normalization=norm,
                   returned_provider=provider, returned_model="test/model", generation_id=task["task_id"])
    original.atomic_json(directory/"raw"/(task["task_id"]+".request.json"), task["request"])
    original.atomic_json(directory/"raw"/(task["task_id"]+".json"), rec)
    return rec


class RecordingTransport:
    def __init__(self, output, prior_cost, *, drift=False, stop=False):
        self.output, self.spent, self.tasks, self.drift, self.stop = output, prior_cost, [], drift, stop

    def run(self, task):
        self.tasks.append(deepcopy(task))
        if self.stop:
            return {"status": "budget_stop"}
        rec = write_record(self.output, task, provider="changed" if self.drift else "provider-one")
        self.spent += rec["accounted_cost_usd"]
        return rec


class AdministrativeResumeTests(unittest.TestCase):
    def test_preparation_preserves_all_parent_files_and_new_seeds(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d)
            before = {str(x.relative_to(parent)): x.read_bytes() for x in parent.rglob("*") if x.is_file()}
            output = Path(d)/"resumed"
            with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen", side_effect=AssertionError("network")):
                result = execute(config, parent, output)
            self.assertEqual(result["status"], "prepared_only_no_calls")
            audit = read_json(output/"administrative_audit.json")
            self.assertEqual(audit["prior_active_execution_seconds"], 60)
            self.assertAlmostEqual(audit["unknown_outcome_reservations_usd"], .03)
            self.assertEqual(len(audit["excluded_from_scoring_task_ids"]), 3)
            fresh = amended_tasks(config, 3, audit)
            old = {t["card_id"]: t for t in original.request_tasks(config, 3)}
            for task in fresh:
                self.assertNotEqual(task["task_id"], old[task["card_id"]]["task_id"])
                expected = deepcopy(old[task["card_id"]]["request"])
                expected["seed"] += 1000000
                self.assertEqual(task["request"], expected)
            self.assertEqual(before, {str(x.relative_to(parent)): x.read_bytes() for x in parent.rglob("*") if x.is_file()})
            for path in (parent/"raw").glob("*.json"):
                self.assertEqual(path.read_bytes(), (output/"raw"/path.name).read_bytes())
            self.assertEqual(result["plan_sha256"], execute(config, parent, output)["plan_sha256"])

    def test_known_invalid_and_original_halt_never_rescued(self):
        for halt in (False, True):
            with tempfile.TemporaryDirectory() as d:
                config, parent = fixture(d, partial="invalid", halt=halt)
                audit, blocks = audit_parent(config, parent)
                self.assertEqual(audit["replacement_blocks"], [])
                block = next(iter(blocks.values()))
                self.assertEqual(block["complete_rounds"], 2)
                self.assertEqual(block["halt_reason"], "incomplete_round_invalid_output")

    def test_completed_cached_round_retained_regardless_of_score(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d, complete_cached=True)
            audit, blocks = audit_parent(config, parent)
            self.assertEqual(audit["replacement_blocks"], [])
            self.assertEqual(next(iter(blocks.values()))["complete_rounds"], 3)

    def test_partial_service_drift_prevents_replacement(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d, partial="valid")
            task = original.request_tasks(config, 3)[0]
            write_record(parent, task, provider="changed")
            audit, blocks = audit_parent(config, parent)
            self.assertEqual(audit["replacement_blocks"], [])
            block = next(iter(blocks.values()))
            self.assertFalse(block["inference_assumptions_ok"])
            self.assertEqual(block["halt_reason"], "provider_or_model_changed")

    def test_execute_round_replacement_analysis_and_single_start(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d)
            output = Path(d)/"resumed"
            _, audit, _ = prepare(config, parent, output)
            transport = RecordingTransport(output, audit["accounted_prior_cost_usd"])
            report = execute(config, parent, output, prepare_only=False, transport=transport)
            self.assertEqual(len([t for t in transport.tasks if t["round"] == 3]), 3)
            self.assertTrue(all("__administrative_replacement1" in t["task_id"] for t in transport.tasks if t["round"] == 3))
            self.assertGreaterEqual(next(iter(report["blocks"].values()))["complete_rounds"], 4)
            self.assertGreater(report["accounted_cost_usd"], audit["accounted_prior_cost_usd"])
            config_path = Path(d)/"config.json"
            original.atomic_json(config_path, config)
            qa = analyze(config_path, output, Path(d)/"analysis")
            self.assertEqual(qa["status"], "PASS")
            costs = read_json(Path(d)/"analysis/cost_and_status.json")
            self.assertEqual(costs["administrative_pause"]["excluded_partial_requests"], 2)
            self.assertAlmostEqual(costs["administrative_pause"]["unknown_outcomes_reserved_usd"], .03)
            with self.assertRaisesRegex(RuntimeError, "already started"):
                execute(config, parent, output, prepare_only=False, transport=transport)

    def test_prior_cost_required_and_resumed_drift_halts(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d)
            output = Path(d)/"resumed"
            _, audit, _ = prepare(config, parent, output)
            transport = RecordingTransport(output, audit["accounted_prior_cost_usd"], drift=True)
            report = execute(config, parent, output, prepare_only=False, transport=transport)
            block = next(iter(report["blocks"].values()))
            self.assertEqual(block["complete_rounds"], 2)
            self.assertFalse(block["inference_assumptions_ok"])
            self.assertEqual(block["halt_reason"], "provider_or_model_changed")
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d)
            with self.assertRaisesRegex(RuntimeError, "include every prior"):
                execute(config, parent, Path(d)/"resumed", prepare_only=False,
                        transport=RecordingTransport(Path(d)/"resumed", 0))

    def test_pause_excluded_from_runtime_and_budget_stop_respected(self):
        with tempfile.TemporaryDirectory() as d:
            config, parent = fixture(d)
            output = Path(d)/"resumed"
            _, audit, _ = prepare(config, parent, output)
            transport = RecordingTransport(output, audit["accounted_prior_cost_usd"], stop=True)
            report = execute(config, parent, output, prepare_only=False, transport=transport)
            self.assertEqual(report["global_stop"], "cost_cap")
            self.assertGreater(len(transport.tasks), 0)  # November pause timestamp does not exhaust resumed wall clock.
            self.assertLess(report["active_execution_seconds"], 65)


if __name__ == "__main__":
    unittest.main()
