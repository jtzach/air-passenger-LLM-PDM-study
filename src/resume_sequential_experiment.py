"""Explicit administrative-pause amendment; the original frozen runner is unchanged.

Preparation audits and snapshots the paused run. Execution needs --execute and
can start only once per prepared directory. All old records remain byte-identical.
An administratively incomplete round is replaced in full with new IDs/seeds;
known invalid answers and service-identity failures are never rescued.
"""
from __future__ import annotations
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

import run_sequential_experiment as original
from run_experiment import ROOT, read_json, sha, utc
from sequential_inference import betting_mean_cs, scheduled_median_analysis


def initial_blocks(config):
    blocks = {}
    for pi, panel in enumerate(config["panels"]):
        base, cap = original.baseline_and_cap(panel)
        for mi, model in enumerate(config["models"]):
            for ai, arm in enumerate(panel["arms"]):
                key = original.block_id(pi, mi, ai)
                blocks[key] = {"block_id": key, "panel_id": panel["panel_id"], "panel": panel,
                    "model_id": original.model_id(model), "arm": arm, "baseline_mae_pp": base,
                    "score_support_upper_pp": cap, "complete_rounds": 0, "round_scores": [],
                    "looks": [], "halt_reason": None, "identity": None, "generation_ids": set(),
                    "diagnostics": set(), "inference_assumptions_ok": bool(config.get("iid_assumption_acknowledged", False))}
    return blocks


def append_score(block, records, round_number):
    panel = block["panel"]
    loss = original.panel_loss(panel, {c["card_id"]: records[c["card_id"]]["prediction"] for c in panel["cards"]})
    control = original.panel_loss(panel, {c["card_id"]: records["no_persona"]["prediction"] for c in panel["cards"]})
    block["round_scores"].append({"round": round_number, "mae_pp": loss, "no_card_mae_pp": control,
        "baseline_gain_pp": block["baseline_mae_pp"]-loss, "no_card_gain_pp": control-loss})
    block["complete_rounds"] += 1


def audit_parent(config, parent, replacement_seed_offset=1000000):
    """Read-only audit; return a score-independent administrative disposition."""
    parent = Path(parent)
    if not (parent/"frozen_plan.json").exists() or (parent/"summary.json").exists():
        raise ValueError("Parent must be an existing frozen, paused, unfinished run")
    original.freeze_plan(config, parent)  # verifies an existing plan, does not rewrite it
    frozen, progress = read_json(parent/"frozen_plan.json"), read_json(parent/"progress.json")
    pause, started = read_json(parent/"pause_state.json"), read_json(parent/"execution_started.json")
    if pause.get("status") != "PAUSED_BY_USER":
        raise ValueError("Only the explicitly documented user pause permits this amendment")
    if progress.get("global_stop") or progress["round"] != pause["last_completed_global_round"]:
        raise ValueError("Pause/progress mismatch or original global cap already reached")
    if progress["round"] >= min(config["looks"]):
        raise ValueError("This amendment is limited to a pause before the first registered look")
    if not isinstance(replacement_seed_offset, int) or replacement_seed_offset <= max(config["looks"]):
        raise ValueError("Replacement seeds must be disjoint from all original planned seeds")
    prior_seconds = (datetime.fromisoformat(pause["paused_utc"])-datetime.fromisoformat(started["started_utc"])).total_seconds()
    if prior_seconds < 0:
        raise ValueError("Invalid pause timestamps")
    planned = {t["task_id"]: t for t in frozen["plan"]["tasks"]}
    files, records, by_round = {}, [], {}
    for path in sorted((parent/"raw").glob("*.json")):
        files[path.relative_to(parent).as_posix()] = sha(path.read_bytes())
        if path.name.endswith(".request.json"):
            continue
        record = read_json(path)
        task = planned.get(record["task_id"])
        if task is None or record["task_id"] != path.stem:
            raise ValueError("Unexpected raw task")
        request_path = path.with_name(path.stem+".request.json")
        if sha(read_json(request_path)) != task["request_sha256"] or record["request_sha256"] != task["request_sha256"]:
            raise ValueError("Request fingerprint mismatch")
        for key in ("block_id", "panel_id", "model_id", "arm", "card_id", "round"):
            if record[key] != task[key]:
                raise ValueError("Raw task metadata differs from original plan")
        if record["round"] > progress["round"]+1:
            raise ValueError("Raw calls extend beyond the administratively interrupted round")
        if record["status"] == "valid":
            _, normalized, _ = original.parse_prediction(record["response"], record["modes"], record["mutually_exclusive"])
            if sha(normalized) != sha(record["prediction"]):
                raise ValueError("Stored prediction differs from the raw response")
        key = (record["block_id"], record["round"])
        by_round.setdefault(key, {})[record["card_id"]] = record
        records.append(record)
    blocks = initial_blocks(config)
    if set(blocks) != set(progress["blocks"]):
        raise ValueError("The registered block inventory changed")
    dispositions, excluded, replacement_blocks = {}, [], []
    interrupted_round = progress["round"]+1
    for key, block in blocks.items():
        saved = progress["blocks"][key]
        expected = {c["card_id"] for c in block["panel"]["cards"]} | {"no_persona"}
        for r in range(1, saved["complete_rounds"]+1):
            rr = by_round.get((key, r), {})
            if set(rr) != expected or any(x["status"] != "valid" for x in rr.values()):
                raise ValueError("Saved complete prefix is not supported by raw records")
            append_score(block, rr, r)
        if sha(block["round_scores"]) != sha(saved["round_scores"]):
            raise ValueError("Saved scores differ from independently reconstructed prefix")
        for field in ("baseline_mae_pp", "score_support_upper_pp"):
            if abs(block[field]-saved[field]) > 1e-9:
                raise ValueError("Saved score definition changed")
        # Check all known valid records, including administratively discarded
        # partial answers. Selection never depends on prediction accuracy.
        for record in sorted((x for x in records if x["block_id"] == key), key=lambda x: (x["round"], x["started_utc"], x["task_id"])):
            if record["status"] == "valid":
                drift = original.record_identity(block, record)
                if drift:
                    block["halt_reason"] = block["halt_reason"] or drift
                    block["incomplete_round"] = record["round"]
        block["diagnostics"].update(saved.get("diagnostics", []))
        block["inference_assumptions_ok"] &= saved["inference_assumptions_ok"]
        if saved["looks"]:
            raise ValueError("A registered look already occurred")
        if saved["halt_reason"]:
            block["halt_reason"] = saved["halt_reason"]
            block["incomplete_round"] = saved.get("incomplete_round")
            dispositions[key] = "retain_original_halt"
            continue
        if saved["complete_rounds"] != progress["round"]:
            raise ValueError("Active block lacks the saved global prefix")
        rr = by_round.get((key, interrupted_round), {})
        failures = sorted({x["status"] for x in rr.values() if x["status"] not in ("valid", "in_progress")})
        if failures:
            block["halt_reason"] = "incomplete_round_"+failures[0]
            block["incomplete_round"] = interrupted_round
        if block["halt_reason"]:
            dispositions[key] = "honor_known_failure_or_drift_before_pause"
        elif set(rr) == expected and all(x["status"] == "valid" for x in rr.values()):
            append_score(block, rr, interrupted_round)
            dispositions[key] = "retain_fully_completed_cached_round"
        else:
            dispositions[key] = "replace_entire_administratively_interrupted_round"
            replacement_blocks.append(key)
            excluded.extend(t["task_id"] for t in original.request_tasks(config, interrupted_round, {key}))
    unknown = [r["task_id"] for r in records if r["status"] == "in_progress"]
    if sorted(unknown) != sorted(pause["in_progress_unknown_outcomes"]):
        raise ValueError("Unknown request inventory differs from the documented pause")
    counted = sum(float(r.get("accounted_cost_usd", 0)) for r in records)
    unknown_reserved = sum(float(r.get("accounted_cost_usd", 0)) for r in records if r["status"] == "in_progress")
    for path in (parent/"frozen_plan.json", parent/"progress.json", parent/"pause_state.json", parent/"execution_started.json"):
        files[path.name] = sha(path.read_bytes())
    audit = {"parent_plan_sha256": frozen["plan_sha256"], "parent_files_sha256": files,
        "pause_utc": pause["paused_utc"], "prior_active_execution_seconds": prior_seconds,
        "accounted_prior_cost_usd": counted, "unknown_outcome_reservations_usd": unknown_reserved,
        "unknown_outcome_tasks": sorted(unknown), "original_record_count": len(records),
        "interrupted_round": interrupted_round, "replacement_seed_offset": replacement_seed_offset,
        "replacement_blocks": sorted(replacement_blocks), "excluded_from_scoring_task_ids": sorted(excluded),
        "dispositions": dispositions,
        "policy": "Retain failures; replace whole administratively incomplete rounds regardless of values; retain all partial records and conservative unknown costs; exclude only documented pause from runtime."}
    return audit, blocks


def amended_tasks(config, round_number, audit, active_blocks=None):
    tasks = original.request_tasks(config, round_number, active_blocks)
    for task in tasks:
        if round_number == audit["interrupted_round"] and task["block_id"] in audit["replacement_blocks"]:
            task["supersedes_task_id"] = task["task_id"]
            task["task_id"] += "__administrative_replacement1"
            task["request"]["seed"] += audit["replacement_seed_offset"]
    return tasks


def prepare(config, parent, output, replacement_seed_offset=1000000):
    parent, output = Path(parent), Path(output)
    if parent.resolve() == output.resolve():
        raise ValueError("Original run directory must remain untouched")
    audit, blocks = audit_parent(config, parent, replacement_seed_offset)
    parent_plan = read_json(parent/"frozen_plan.json")["plan"]
    tasks = deepcopy(parent_plan["tasks"])
    for t in amended_tasks(config, audit["interrupted_round"], audit, set(audit["replacement_blocks"])):
        tasks.append({k: t[k] for k in ("task_id", "block_id", "panel_id", "model_id", "arm", "card_id", "round")} |
                     {"request_sha256": sha(t["request"]), "prompt_sha256": sha(t["request"]["messages"][0]["content"].encode()),
                      "supersedes_task_id": t["supersedes_task_id"]})
    source_files = [Path(__file__), Path(original.__file__), ROOT/"src/run_experiment.py", ROOT/"src/sequential_inference.py"]
    plan = {**parent_plan, "tasks": tasks, "source_sha256": {p.name: sha(p.read_bytes()) for p in source_files},
            "administrative_amendment": audit,
            "failure_policy": "Original policy retained; only the pre-look user-interrupted partial rounds are replaced in full with frozen disjoint seeds/IDs",
            "runtime_policy": "Original total active-execution cap, counting execution before the documented pause; explicit user pause excluded"}
    fingerprint = sha(plan)
    freeze_path = output/"frozen_plan.json"
    if freeze_path.exists():
        saved = read_json(freeze_path)
        if saved["plan_sha256"] != fingerprint or saved["plan"] != plan:
            raise RuntimeError("Prepared amendment or source snapshot changed")
    else:
        if output.exists() and any(output.iterdir()):
            raise RuntimeError("New amendment output must be empty")
        for relative, expected_hash in audit["parent_files_sha256"].items():
            source = parent/relative
            target = output/relative if relative.startswith("raw/") else output/"parent_snapshot"/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha(target.read_bytes()) != expected_hash:
                raise RuntimeError("Snapshot copy verification failed")
        original.atomic_json(output/"administrative_audit.json", audit)
        original.atomic_json(output/"frozen_plan.json", {"created_utc": utc(), "plan_sha256": fingerprint, "plan": plan})
    for relative, expected_hash in audit["parent_files_sha256"].items():
        target = output/relative if relative.startswith("raw/") else output/"parent_snapshot"/relative
        if sha(target.read_bytes()) != expected_hash:
            raise RuntimeError("Preserved original record changed")
    return fingerprint, audit, blocks


def execute(config, parent, output, *, prepare_only=True, transport=None, replacement_seed_offset=1000000):
    output = Path(output)
    fingerprint, audit, blocks = prepare(config, parent, output, replacement_seed_offset)
    if prepare_only:
        return {"status": "prepared_only_no_calls", "plan_sha256": fingerprint,
                "audit": {k: v for k, v in audit.items() if k not in ("parent_files_sha256", "excluded_from_scoring_task_ids")}}
    started_path = output/"execution_started.json"
    if started_path.exists():
        raise RuntimeError("This amendment execution already started; audit any interruption before a new explicit amendment")
    started = utc()
    original.atomic_json(started_path, {"started_utc": started, "plan_sha256": fingerprint,
        "prior_active_execution_seconds": audit["prior_active_execution_seconds"]})
    remaining = max(0, config["max_runtime_seconds"]-audit["prior_active_execution_seconds"])
    deadline = time.monotonic()+remaining
    transport = transport or original.SafeTransport(config, output/"raw", deadline)
    if abs(transport.spent-audit["accounted_prior_cost_usd"]) > 1e-9:
        raise RuntimeError("Transport budget must include every prior charge and unknown reservation")
    global_stop = None
    with ThreadPoolExecutor(max_workers=config["max_workers"]) as pool:
        for r in range(audit["interrupted_round"], config["looks"][-1]+1):
            active = {k for k, b in blocks.items() if b["halt_reason"] is None and b["complete_rounds"] < r}
            if global_stop or not any(b["halt_reason"] is None for b in blocks.values()):
                break
            if time.monotonic() >= deadline:
                global_stop = "runtime_cap"
                break
            pending = amended_tasks(config, r, audit, active)
            futures, records = {}, {k: {} for k in active}
            while pending or futures:
                pending = [t for t in pending if blocks[t["block_id"]]["halt_reason"] is None]
                if global_stop:
                    pending = []
                while pending and len(futures) < config["max_workers"] and not global_stop:
                    task = pending.pop(0)
                    futures[pool.submit(transport.run, task)] = task
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    task = futures.pop(future)
                    record = future.result()
                    block = blocks[task["block_id"]]
                    if record["status"] in ("budget_stop", "runtime_stop"):
                        global_stop = "cost_cap" if record["status"] == "budget_stop" else "runtime_cap"
                        continue
                    records[task["block_id"]][task["card_id"]] = record
                    if record["status"] != "valid":
                        block["halt_reason"] = block["halt_reason"] or "incomplete_round_"+record["status"]
                        block["incomplete_round"] = r
                    else:
                        drift = original.record_identity(block, record)
                        if drift:
                            block["halt_reason"] = block["halt_reason"] or drift
                            block["incomplete_round"] = r
                    if record.get("cost_exceeded_reservation") or transport.spent > config["max_cost_usd"]:
                        global_stop = "cost_cap_or_pricing_discrepancy"
            for key in active:
                block, rr = blocks[key], records[key]
                expected = {c["card_id"] for c in block["panel"]["cards"]} | {"no_persona"}
                if block["halt_reason"] or set(rr) != expected or any(x["status"] != "valid" for x in rr.values()):
                    continue
                if block["complete_rounds"] != r-1:
                    raise RuntimeError("A logical observation round was skipped")
                append_score(block, rr, r)
                if r in config["looks"]:
                    gains = [s["baseline_gain_pp"] for s in block["round_scores"]]
                    support = (block["baseline_mae_pp"]-block["score_support_upper_pp"], block["baseline_mae_pp"])
                    primary = scheduled_median_analysis(gains, endpoint_count=config["endpoint_count"],
                        looks=tuple(config["looks"]), family_alpha=config["primary_family_alpha"], bounds=support,
                        margin=config.get("practical_margin_pp", .5), precision=config.get("precision_half_width_pp", .25),
                        iid_assumption_acknowledged=block["inference_assumptions_ok"])
                    secondary = betting_mean_cs(gains, bounds=support, alpha=config["secondary_alpha_per_endpoint"]).as_dict()
                    secondary["assumptions_acknowledged"] = block["inference_assumptions_ok"]
                    if primary["identical_observations"]:
                        block["diagnostics"].add("identical_round_gains_do_not_prove_independence")
                    block["looks"].append({"round": r, "primary_median": primary, "secondary_mean": secondary})
                    original.atomic_json(output/"looks"/f"{key}__r{r:03d}.json", original.public_block_state(block))
                    if primary["decision"] != "continue":
                        block["halt_reason"] = primary["decision"]
            original.atomic_json(output/"progress.json", {"updated_utc": utc(), "round": r,
                "accounted_cost_usd": transport.spent, "global_stop": global_stop,
                "blocks": {k: original.public_block_state(b) for k, b in blocks.items()}})
            print(f"Round {r}: complete blocks {sum(b['complete_rounds']==r for b in blocks.values())}; total accounted cost ${transport.spent:.4f}", flush=True)
    for block in blocks.values():
        if block["halt_reason"] is None:
            block["halt_reason"] = global_stop or "maximum_rounds"
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds()
    summary = {"completed_utc": utc(), "plan_sha256": fingerprint,
        "parent_plan_sha256": audit["parent_plan_sha256"], "accounted_cost_usd": transport.spent,
        "global_stop": global_stop, "active_execution_seconds": audit["prior_active_execution_seconds"]+elapsed,
        "administrative_amendment": {k: v for k, v in audit.items() if k != "parent_files_sha256"},
        "inference_scope": "model-repeat median/mean under stated assumptions; no survey-sampling uncertainty; user pause and administrative replacement disclosed",
        "blocks": {k: original.public_block_state(b) for k, b in blocks.items()}}
    original.atomic_json(output/"summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--parent-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replacement-seed-offset", type=int, default=1000000)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = execute(read_json(args.config), args.parent_run, args.output,
        prepare_only=not args.execute, replacement_seed_offset=args.replacement_seed_offset)
    print(json.dumps({k: v for k, v in result.items() if k != "blocks"}, indent=2))


if __name__ == "__main__":
    main()
