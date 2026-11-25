"""Export finalized request/audit records and approved derived evaluation targets.

The allowlist includes original interrupted records and administrative replacements.
Source records are read-only. Account/credential metadata are redacted only in
exported copies, with source and exported hashes in the manifest.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
import zipfile

from run_experiment import ROOT, read_json, sha, utc
from run_sequential_experiment import validate_config

SENSITIVE_KEYS = {"userid", "accountid", "apikey", "authorization", "accesstoken", "refreshtoken",
                  "clientsecret", "password", "credential", "credentials"}
FORBIDDEN_FIELDS = {"private_config", "source_rows", "source_workbook", "passenger_volume", "observed", "targets"}
RAW_FIELDS = {"task_id", "block_id", "panel_id", "panel_index", "model_id", "arm", "card_id", "round",
    "modes", "mutually_exclusive", "supersedes_task_id", "request_sha256", "started_utc", "attempts",
    "status", "accounted_cost_usd", "reservation_upper_bound_usd", "response_sha256", "response",
    "raw_prediction", "prediction", "normalization", "returned_provider", "returned_model", "generation_id",
    "finished_utc", "cost_exceeded_reservation", "validation_error", "response_text"}
REQUEST_FIELDS = {"model", "messages", "temperature", "max_tokens", "seed", "response_format", "provider"}
CONFIG_FIELDS = {"version", "study_date", "endpoint", "models", "panels", "temperature", "max_tokens",
    "seed_base", "shuffle_seed", "looks", "endpoint_count", "primary_family_alpha", "secondary_alpha_per_endpoint",
    "precision_half_width_pp", "practical_margin_pp", "iid_assumption_acknowledged", "max_cost_usd",
    "max_runtime_seconds", "max_workers", "transport_attempts", "request_timeout_seconds", "failure_policy",
    "catalogue_path", "provider_policy", "fmg_external_processing", "fmg_publication", "fmg_target_caveat",
    "public_access_context_sources", "source_hashes"}
FMG_IDS = {f"fmg_{purpose}_{region}" for purpose in ("business", "private")
           for region in ("domestic", "continental", "intercontinental")}


def clean_public(value):
    if isinstance(value, dict):
        return {k: (v if isinstance(v, str) and v.startswith("[REDACTED") else "[REDACTED_PRIVATE_METADATA]") if re.sub(r"[^a-z]", "", k.lower()) in SENSITIVE_KEYS
                else clean_public(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_public(x) for x in value]
    if isinstance(value, str):
        value = re.sub(r"\bsk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{20,}\b", "[REDACTED_CREDENTIAL]", value)
        value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+-]+", "Bearer [REDACTED_CREDENTIAL]", value)
        value = re.sub(r'(?i)([\"\']?(?:user_id|account_id|api_key|access_token)[\"\']?\s*[:=]\s*)[\"\'][^\"\']+[\"\']',
                       r'\1"[REDACTED_PRIVATE_METADATA]"', value)
    return value


def changed_fields(before, after, pointer=""):
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [p for k in before for p in changed_fields(before[k], after[k], pointer+"/"+str(k))]
    if isinstance(before, list) and isinstance(after, list):
        return [p for i, (a, b) in enumerate(zip(before, after)) for p in changed_fields(a, b, pointer+"/"+str(i))]
    return [pointer or "/"]


def reject_private_fields(obj):
    if isinstance(obj, dict):
        if FORBIDDEN_FIELDS & set(obj):
            raise ValueError("Unexpected protected-source field in public archive input")
        for key, value in obj.items():
            if key not in ("response", "raw_prediction", "prediction"):
                reject_private_fields(value)
    elif isinstance(obj, list):
        for value in obj:
            reject_private_fields(value)


def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode("utf-8")


def validate_evaluation_config(config, frozen, library):
    """Release only the explicitly approved six-group derived scoring schema."""
    validate_config(config)
    if set(config)-CONFIG_FIELDS or sha(config) != frozen["plan"]["config_sha256"]:
        raise ValueError("Evaluation configuration schema or frozen fingerprint differs")
    if clean_public(config) != config:
        raise ValueError("Evaluation configuration contains sensitive account metadata")
    if set(config.get("source_hashes", {})) != {"private_fmg_derived_targets_sha256", "mid_personas_sha256"}:
        raise ValueError("Unexpected source-reference metadata")
    if any(not re.fullmatch(r"[0-9a-f]{64}", x) for x in config["source_hashes"].values()):
        raise ValueError("Source references must be hashes, not source contents")
    if {p["panel_id"] for p in config["panels"]} != {"mid_2023", "fmg_2025"}:
        raise ValueError("Unapproved evaluation panel")
    public_panels = {p["panel_id"]: p for p in library["panels"]}
    for panel in config["panels"]:
        if set(panel) != {"panel_id", "modes", "arms", "mutually_exclusive", "baseline", "cards", "prompts"}:
            raise ValueError("Unexpected protected-source fields in evaluation panel")
        public = public_panels[panel["panel_id"]]
        for key in ("modes", "arms", "mutually_exclusive", "prompts"):
            if panel[key] != public[key]:
                raise ValueError("Evaluation prompt/outcome definition differs from public library")
        if panel["panel_id"] == "fmg_2025" and {c["card_id"] for c in panel["cards"]} != FMG_IDS:
            raise ValueError("FMG evaluation data must contain exactly six approved derived groups")
        for card in panel["cards"]:
            if set(card) != {"card_id", "description", "feature", "label", "observed", "weight"}:
                raise ValueError("Unexpected source counts/rows or extra card fields")
            if set(card["observed"]) != set(panel["modes"]):
                raise ValueError("Unexpected target mode keys")


def export_archive(run_dir, output_dir, prompt_library=None, evaluation_config=None):
    run_dir, output_dir = Path(run_dir), Path(output_dir)
    if not (run_dir/"summary.json").exists():
        raise RuntimeError("Final summary required; incomplete study archives are not published")
    summary, frozen = read_json(run_dir/"summary.json"), read_json(run_dir/"frozen_plan.json")
    if not summary.get("completed_utc") or any(not b.get("halt_reason") for b in summary["blocks"].values()):
        raise ValueError("Study summary is not finalized")
    if frozen["plan_sha256"] != sha(frozen["plan"]) or summary["plan_sha256"] != frozen["plan_sha256"]:
        raise ValueError("Frozen plan and summary fingerprint differ")
    prompts = read_json(prompt_library or ROOT/"config/sequential_prompt_library_20261125.json")
    allowed_prompts = {(p["panel_id"], arm, cid): text for p in prompts["panels"]
                       for arm, cards in p["prompts"].items() for cid, text in cards.items()}
    planned = {t["task_id"]: t for t in frozen["plan"]["tasks"]}
    amendment = frozen["plan"].get("administrative_amendment", {})
    excluded = set(amendment.get("excluded_from_scoring_task_ids", []))
    entries, manifest, records, index = {}, [], [], []

    def add(path):
        relative = path.relative_to(run_dir).as_posix()
        source_bytes = path.read_bytes()
        obj = json.loads(source_bytes)
        reject_private_fields(obj)
        cleaned = clean_public(obj)
        output_bytes = source_bytes if cleaned == obj else json_bytes(cleaned)
        entries[relative] = output_bytes
        manifest.append({"path": relative, "source_sha256": sha(source_bytes), "export_sha256": sha(output_bytes),
                         "bytes": len(output_bytes), "private_metadata_redacted": cleaned != obj,
                         "redacted_fields": changed_fields(obj, cleaned)})

    response_paths = [p for p in sorted((run_dir/"raw").glob("*.json")) if not p.name.endswith(".request.json")]
    request_paths = list((run_dir/"raw").glob("*.request.json"))
    if len(request_paths) != len(response_paths):
        raise ValueError("Request/result pair inventory is incomplete")
    for path in response_paths:
        record = read_json(path)
        if set(record)-RAW_FIELDS:
            raise ValueError("Unexpected raw record fields; review before publishing")
        task_id = record["task_id"]
        if task_id not in planned or task_id != path.stem:
            raise ValueError("Raw record absent from frozen plan")
        request_path = path.with_name(path.stem+".request.json")
        request = read_json(request_path)
        if (set(request) != REQUEST_FIELDS or len(request["messages"]) != 1 or
            set(request["messages"][0]) != {"role", "content"} or request["messages"][0]["role"] != "user"):
            raise ValueError("Unexpected API request structure")
        if request["messages"][0]["content"] != allowed_prompts[(record["panel_id"], record["arm"], record["card_id"])]:
            raise ValueError("Request text differs from the public-safe prompt library")
        if clean_public(request) != request:
            raise ValueError("A request contains sensitive material; do not publish a changed scientific request")
        if sha(request) != record["request_sha256"] or sha(request) != planned[task_id]["request_sha256"]:
            raise ValueError("Request hash differs from its frozen plan")
        add(request_path)
        add(path)
        records.append(record)
        prefix = summary["blocks"][record["block_id"]]["complete_rounds"]
        disposition = ("excluded_administrative_partial_round" if task_id in excluded else
                       "retained_complete_prefix" if record["round"] <= prefix and record["status"] == "valid" else
                       "retained_audit_only")
        index.append({k: record[k] for k in ("task_id", "block_id", "panel_id", "model_id", "arm", "card_id", "round", "status")} |
                     {"analysis_disposition": disposition, "supersedes_task_id": record.get("supersedes_task_id", ""),
                      "seed": request["seed"], "accounted_cost_usd": record["accounted_cost_usd"],
                      "request_sha256": record["request_sha256"]})
    accounted = sum(r["accounted_cost_usd"] for r in records)
    if abs(accounted-summary["accounted_cost_usd"]) > 1e-7:
        raise ValueError("Archived cost differs from final summary")
    for relative, expected_hash in amendment.get("parent_files_sha256", {}).items():
        path = run_dir/relative if relative.startswith("raw/") else run_dir/"parent_snapshot"/relative
        if sha(path.read_bytes()) != expected_hash:
            raise ValueError("An original paused-run record changed")
    for name in ("summary.json", "frozen_plan.json", "administrative_audit.json", "execution_started.json", "progress.json"):
        path = run_dir/name
        if path.exists():
            add(path)
    for folder in ("looks", "parent_snapshot"):
        for path in sorted((run_dir/folder).glob("*.json")):
            add(path)
    table = io.StringIO(newline="")
    writer = csv.DictWriter(table, fieldnames=list(index[0]) if index else ["task_id"])
    writer.writeheader()
    writer.writerows(index)
    entries["request_index.csv"] = table.getvalue().encode("utf-8")
    readme = """# Final sequential request archive

This archive includes every saved request and result from the original paused run and its explicitly frozen administrative resumption. It does not contain the airport workbook, native source rows, or passenger counts. The model inputs are checked against the public-safe prompt library. The separately reviewed evaluation configuration, when included, contains only public MiD targets and the six airport groups' authorized derived rates/weights/baseline, generic prompts and settings. It is an offline scoring artifact, never an API message.

`raw/` contains exact request bodies and scientific outputs, including invalid outputs and unknown interrupted outcomes. Authentication headers were never saved. Any remaining credential/account metadata in response envelopes or errors is redacted only in these public copies; `MANIFEST.json` records source/export hashes and changed files. Model/provider IDs, generation IDs, seeds, timestamps, usage, retries, scores and numerical predictions are retained.

`request_index.csv` identifies each record's role. `excluded_administrative_partial_round` means it belonged to a whole round interrupted by the explicit user pause; its costs remain counted, but its numerical response does not enter the replacement round. `retained_audit_only` includes terminal failures and any other records outside a complete scoring prefix. `in_progress` on an original record means an unknown outcome at the pause; the preserved record is not evidence of a currently running request.

`frozen_plan.json` preserves the amended plan, parent-plan hash, exact request hashes and source-code hashes. `parent_snapshot/` preserves the original plan and pause/progress documentation. `looks/` preserves scheduled decisions. `summary.json` reports all originally registered blocks, including failed and inconclusive ones. Never combine records solely by logical round/card: use the administrative exclusion map or `request_index.csv` to distinguish original and replacement IDs.

The original three-repeat pilot is separate and absent from this archive. Repeat-level intervals concern model generation under stated stability/independence assumptions, not uncertainty in human survey proportions. Rationale text is a generated hypothesis, not evidence of passengers' motives.
"""
    config_bytes = None
    if evaluation_config:
        config_bytes = Path(evaluation_config).read_bytes()
        config = json.loads(config_bytes)
        validate_evaluation_config(config, frozen, prompts)
        entries["evaluation_config.json"] = config_bytes
        manifest.append({"path": "evaluation_config.json", "source_sha256": sha(config_bytes),
                         "export_sha256": sha(config_bytes), "canonical_config_sha256": sha(config),
                         "bytes": len(config_bytes), "private_metadata_redacted": False,
                         "classification": "public MiD and authorized six-group FMG derived evaluation data; no original rows/counts"})
        readme += """
## Offline replay (no API calls)

From the repository root, extract this ZIP into `outputs/sequential_replay`, then run:

```text
python src/analyse_sequential_results.py --config outputs/sequential_replay/evaluation_config.json --run-dir outputs/sequential_replay --output outputs/sequential_replay_analysis
```

The evaluation JSON retains its exact historical bytes and canonical hash. Its `catalogue_path` records the original machine's path; the offline analyzer does not read it, so no path override is necessary. Do not edit this historical file to run new calls. A new paid experiment needs an explicitly revised configuration with a local catalogue path and its own new freeze. The private airport workbook is not needed to reproduce scoring from the released six-group derivatives; reproducing the upstream derivation still requires authorized source access.
"""
    entries["README.md"] = readme.encode("utf-8")
    audit = {"status": "PASS", "exported_utc": utc(), "plan_sha256": frozen["plan_sha256"],
        "parent_plan_sha256": amendment.get("parent_plan_sha256"), "request_records": len(records),
        "status_counts": dict(Counter(r["status"] for r in records)), "accounted_cost_usd": accounted,
        "analysis_dispositions": dict(Counter(x["analysis_disposition"] for x in index)),
        "approved_derived_evaluation_config_exported": config_bytes is not None, "private_source_rows_or_counts_exported": False,
        "prompt_library_verified": True, "redacted_files": [m["path"] for m in manifest if m["private_metadata_redacted"]],
        "files": manifest}
    entries["MANIFEST.json"] = json_bytes(audit)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir/"request_archive.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(entries.items()):
            z.writestr(name, data)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist()) != set(entries):
            raise RuntimeError("Archive CRC/member validation failed")
        for name, data in entries.items():
            if sha(z.read(name)) != sha(data):
                raise RuntimeError("Archive member hash mismatch")
    expanded = output_dir/"archive"
    existing = {p.relative_to(expanded).as_posix() for p in expanded.rglob("*") if p.is_file()} if expanded.exists() else set()
    if existing-set(entries):
        raise RuntimeError("Expanded archive contains unexpected files; review instead of silently deleting")
    for name, data in sorted(entries.items()):
        path = expanded/name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
        if sha(path.read_bytes()) != sha(data):
            raise RuntimeError("Expanded archive member hash mismatch")
    audit["archive"] = {"filename": archive.name, "sha256": sha(archive.read_bytes()),
                        "bytes": archive.stat().st_size, "members": len(entries),
                        "expanded_directory": "archive", "expanded_bytes": sum(len(b) for b in entries.values())}
    (output_dir/"request_archive_manifest.json").write_bytes(json_bytes(audit))
    (output_dir/"request_archive_README.md").write_text(readme, encoding="utf-8")
    if config_bytes is not None:
        (output_dir/"evaluation_config.json").write_bytes(config_bytes)
    return {k: v for k, v in audit.items() if k != "files"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prompt-library", type=Path)
    parser.add_argument("--evaluation-config", type=Path)
    args = parser.parse_args()
    print(json.dumps(export_archive(args.run_dir, args.output, args.prompt_library, args.evaluation_config), indent=2))


if __name__ == "__main__":
    main()
