"""Offline publication-boundary tests; no network or protected source workbook."""
from copy import deepcopy
from pathlib import Path
import json
import io
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_sequential_resume import fixture, RecordingTransport
from resume_sequential_experiment import prepare, execute
from run_experiment import read_json, sha
from run_sequential_experiment import atomic_json
from export_sequential_archive import export_archive, clean_public, validate_evaluation_config
from test_sequential_analysis import fixture_config
from analyse_sequential_results import analyze
from run_sequential_experiment import SafeTransport, execute as execute_original


def completed_fixture(directory):
    config, parent = fixture(directory)
    output = Path(directory)/"resumed"
    _, audit, _ = prepare(config, parent, output)
    execute(config, parent, output, prepare_only=False,
            transport=RecordingTransport(output, audit["accounted_prior_cost_usd"]))
    library = Path(directory)/"prompts.json"
    atomic_json(library, {"panels": [{k: p[k] for k in ("panel_id", "modes", "arms", "mutually_exclusive", "prompts")} for p in config["panels"]]})
    return config, parent, output, library


class SequentialArchiveTests(unittest.TestCase):
    def test_preserves_original_and_replacement_records_and_costs(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, run, library = completed_fixture(d)
            before = {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob("*") if p.is_file()}
            target = Path(d)/"public"
            report = export_archive(run, target, library)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["status_counts"]["in_progress"], 1)
            self.assertEqual(report["analysis_dispositions"]["excluded_administrative_partial_round"], 2)
            self.assertFalse(report["private_source_rows_or_counts_exported"])
            self.assertEqual(report["redacted_files"], [])
            self.assertEqual(before, {str(p.relative_to(run)): sha(p.read_bytes()) for p in run.rglob("*") if p.is_file()})
            with zipfile.ZipFile(target/"request_archive.zip") as z:
                names = z.namelist()
                self.assertTrue(any("administrative_replacement1" in n for n in names))
                self.assertIn("parent_snapshot/pause_state.json", names)
                self.assertNotIn("private_config.json", names)
                for path in (run/"raw").glob("*.json"):
                    self.assertEqual(path.read_bytes(), z.read("raw/"+path.name))
                    self.assertEqual(path.read_bytes(), (target/"archive/raw"/path.name).read_bytes())

    def test_account_redaction_is_copy_only_and_preserves_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, run, library = completed_fixture(d)
            path = next(p for p in (run/"raw").glob("*administrative_replacement1.json") if not p.name.endswith(".request.json"))
            obj = read_json(path)
            obj["response"]["account_id"] = "PRIVATE_TEST_ACCOUNT"
            obj["response"]["metadata"] = {"api_key": "sk-or-v1-"+"a"*40}
            path.write_text(json.dumps(obj), encoding="utf-8")
            before = path.read_bytes()
            target = Path(d)/"public"
            report = export_archive(run, target, library)
            self.assertEqual(report["redacted_files"], ["raw/"+path.name])
            exported = read_json(target/"archive/raw"/path.name)
            self.assertEqual(exported["prediction"], obj["prediction"])
            self.assertEqual(exported["response"]["choices"], obj["response"]["choices"])
            self.assertNotIn("PRIVATE_TEST_ACCOUNT", json.dumps(exported))
            self.assertEqual(path.read_bytes(), before)
            manifest = read_json(target/"request_archive_manifest.json")
            entry = next(x for x in manifest["files"] if x["path"] == "raw/"+path.name)
            self.assertIn("/response/account_id", entry["redacted_fields"])

    def test_unknown_protected_fields_and_unapproved_prompts_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, run, library = completed_fixture(d)
            path = next(p for p in (run/"raw").glob("*administrative_replacement1.json") if not p.name.endswith(".request.json"))
            obj = read_json(path)
            obj["source_rows"] = [{"private_count": 123456}]
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected raw record fields"):
                export_archive(run, Path(d)/"public", library)
            del obj["source_rows"]
            path.write_text(json.dumps(obj), encoding="utf-8")
            request_path = path.with_name(path.stem+".request.json")
            request = read_json(request_path)
            request["messages"][0]["content"] = "UNAPPROVED CONTENT"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "public-safe prompt"):
                export_archive(run, Path(d)/"public", library)
            self.assertFalse((Path(d)/"public").exists())

    def test_incomplete_run_and_modified_original_records_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _, parent = fixture(d)
            with self.assertRaisesRegex(RuntimeError, "Final summary required"):
                export_archive(parent, Path(d)/"public")
        with tempfile.TemporaryDirectory() as d:
            _, _, run, library = completed_fixture(d)
            path = next(p for p in (run/"raw").glob("*.json") if not p.name.endswith(".request.json") and "replacement" not in p.name)
            obj = read_json(path)
            obj["validation_error"] = "modified original record"
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "original paused-run record changed"):
                export_archive(run, Path(d)/"public", library)

    def test_derived_config_whitelist_blocks_counts_and_extra_groups(self):
        with tempfile.TemporaryDirectory() as d:
            config, _ = fixture(d)
            panel = config["panels"][0]
            panel["panel_id"] = "mid_2023"
            for card in panel["cards"]:
                card["label"] = card["card_id"]
            fmg = deepcopy(panel)
            fmg["panel_id"] = "fmg_2025"
            fmg["cards"] = [{"card_id": f"fmg_{p}_{r}", "label": f"{p} / {r}", "description": "Generic profile",
                             "feature": "purpose_x_flight_region", "weight": 1/6, "observed": {"a": .2, "b": .8}}
                            for p in ("business", "private") for r in ("domestic", "continental", "intercontinental")]
            fmg["prompts"] = {"unanchored": {c["card_id"]: "Generic prompt" for c in fmg["cards"]} | {"no_persona": "Generic control"}}
            config["panels"].append(fmg)
            config["endpoint_count"] = 2
            config["secondary_alpha_per_endpoint"] = .005
            config["source_hashes"] = {"private_fmg_derived_targets_sha256": "a"*64, "mid_personas_sha256": "b"*64}
            library = {"panels": [{k: p[k] for k in ("panel_id", "modes", "arms", "mutually_exclusive", "prompts")} for p in config["panels"]]}
            validate_evaluation_config(config, {"plan": {"config_sha256": sha(config)}}, library)
            config["panels"][1]["cards"][0]["passenger_count"] = 123456
            with self.assertRaisesRegex(ValueError, "source counts/rows"):
                validate_evaluation_config(config, {"plan": {"config_sha256": sha(config)}}, library)

    def test_exact_config_export_allows_offline_replay_without_private_file(self):
        with tempfile.TemporaryDirectory() as d:
            config = fixture_config(d)
            config["models"] = config["models"][:1]
            config.update(looks=[1], endpoint_count=3, secondary_alpha_per_endpoint=.01/3)
            config["source_hashes"] = {"private_fmg_derived_targets_sha256": "a"*64, "mid_personas_sha256": "b"*64}
            for panel in config["panels"]:
                panel.pop("source_private_note", None)
                for card in panel["cards"]:
                    card.pop("original_native_counts", None)
                    card["label"] = card["card_id"]
            config_path = Path(d)/"local_evaluation.json"
            config_path.write_text(json.dumps(config, indent=3), encoding="utf-8")
            exact_bytes = config_path.read_bytes()
            library = Path(d)/"library.json"
            atomic_json(library, {"panels": [{k: p[k] for k in ("panel_id", "modes", "arms", "mutually_exclusive", "prompts")} for p in config["panels"]]})
            run, out = Path(d)/"run", Path(d)/"public"
            counter = [0]
            def opener(request, timeout):
                body = json.loads(request.data)
                counter[0] += 1
                prediction = ({"car": .2, "transit": .8} if body["messages"][0]["content"].startswith("FMG") else
                              {"car": .5, "local_pt": .2, "long_distance_rail": .3})
                prediction["rationale"] = "Test hypothesis"
                response = {"id": "test-"+str(counter[0]), "model": body["model"], "provider": "fixed",
                            "choices": [{"message": {"content": json.dumps(prediction)}}], "usage": {"cost": .0001}}
                return io.BytesIO(json.dumps(response).encode())
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "TEST_ONLY_FAKE_KEY"}), patch("builtins.print"):
                transport = SafeTransport(config, run/"raw", time.monotonic()+60, opener=opener)
                execute_original(config, run, prepare_only=False, transport=transport)
            report = export_archive(run, out, library, config_path)
            self.assertTrue(report["approved_derived_evaluation_config_exported"])
            self.assertEqual((out/"evaluation_config.json").read_bytes(), exact_bytes)
            self.assertEqual((out/"archive/evaluation_config.json").read_bytes(), exact_bytes)
            qa = analyze(out/"evaluation_config.json", out/"archive", Path(d)/"offline_replay")
            self.assertEqual(qa["status"], "PASS")
            self.assertEqual(qa["fmg_derived_groups_exported"], 6)


if __name__ == "__main__":
    unittest.main()
