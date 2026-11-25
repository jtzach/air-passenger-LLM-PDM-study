"""Generic, frozen, resumable sequential experiment runner.

Only the preconstructed strings in panel['prompts'] enter API messages.
Local targets, weights, baselines, card descriptions, and source files are NEVER
used by the request builder. The private configuration must stay outside the
public repository. This program makes no call unless --execute is specified.
"""
from __future__ import annotations
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import threading
import time
import urllib.error
import urllib.request

from run_experiment import ROOT, read_json, redact, sanitize, sha, utc
from sequential_inference import betting_mean_cs, scheduled_median_analysis

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(sanitize(value), ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def model_id(model):
    return model if isinstance(model, str) else model["id"]


def validate_config(config):
    if config.get("endpoint", ENDPOINT) != ENDPOINT:
        raise ValueError("Only the authorized OpenRouter endpoint is allowed")
    looks = config["looks"]
    if not looks or looks != sorted(set(looks)) or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in looks):
        raise ValueError("Registered looks must be increasing positive integers")
    models = [model_id(m) for m in config["models"]]
    if not models or len(set(models)) != len(models):
        raise ValueError("Model IDs must be nonempty and unique")
    for model in config["models"]:
        if isinstance(model, dict) and "provider_only" in model:
            pins = model["provider_only"]
            if not isinstance(pins, list) or not pins or any(not isinstance(p, str) or not p.strip() for p in pins):
                raise ValueError("provider_only must be a nonempty list of provider IDs")
    panel_ids = [p["panel_id"] for p in config["panels"]]
    if not panel_ids or len(set(panel_ids)) != len(panel_ids):
        raise ValueError("Panel IDs must be nonempty and unique")
    endpoints = 0
    for panel in config["panels"]:
        modes, cards, arms = panel["modes"], panel["cards"], panel["arms"]
        ids = [c["card_id"] for c in cards]
        if not modes or len(set(modes)) != len(modes) or "rationale" in modes:
            raise ValueError("Invalid mode keys")
        if not cards or len(set(ids)) != len(ids) or "no_persona" in ids:
            raise ValueError("Invalid card IDs")
        if not arms or len(set(arms)) != len(arms) or any(a not in ("unanchored", "overall_rate_anchored") for a in arms):
            raise ValueError("Invalid prompt conditions")
        weights = [c["weight"] for c in cards]
        if any(isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0 for w in weights) or not math.isclose(sum(weights), 1, abs_tol=1e-10, rel_tol=0):
            raise ValueError("Card weights must be nonnegative and sum to one")
        for values in [panel["baseline"], *[c["observed"] for c in cards]]:
            if set(values) != set(modes) or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1 for x in values.values()):
                raise ValueError("Invalid local comparison probabilities")
            if panel["mutually_exclusive"] and not math.isclose(sum(values.values()), 1, abs_tol=.005, rel_tol=0):
                raise ValueError("Exclusive local targets must form complete distributions")
        if set(panel["prompts"]) != set(arms):
            raise ValueError("Prompt arms must match the registered panel")
        for arm in arms:
            prompts = panel["prompts"][arm]
            if set(prompts) != set(ids) | {"no_persona"} or any(not isinstance(v, str) or not v.strip() for v in prompts.values()):
                raise ValueError("Every card/control needs a preconstructed approved prompt")
        endpoints += len(models) * len(arms)
    if endpoints != config["endpoint_count"]:
        raise ValueError("Primary multiplicity divisor differs from full registered endpoint count")
    for key in ("max_cost_usd", "max_runtime_seconds", "request_timeout_seconds"):
        if not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"Invalid {key}")
    for key in ("max_workers", "transport_attempts", "max_tokens"):
        if not isinstance(config[key], int) or isinstance(config[key], bool) or config[key] < 1:
            raise ValueError(f"Invalid {key}")
    primary = config["primary_family_alpha"]
    secondary = config["secondary_alpha_per_endpoint"]
    if not 0 < primary < 1 or not 0 < secondary < 1 or primary + endpoints*secondary > .05 + 1e-12:
        raise ValueError("Combined registered error allowance exceeds .05")


def block_id(pi, mi, ai):
    return f"p{pi+1:02d}__m{mi+1:02d}__a{ai+1:02d}"


def request_tasks(config, round_number, active_blocks=None):
    """Pure allowlist builder: deliberately does not access local target fields."""
    tasks = []
    for pi, panel in enumerate(config["panels"]):
        for mi, model in enumerate(config["models"]):
            for ai, arm in enumerate(panel["arms"]):
                block = block_id(pi, mi, ai)
                if active_blocks is not None and block not in active_blocks:
                    continue
                card_ids = [c["card_id"] for c in panel["cards"]] + ["no_persona"]
                for ci, card in enumerate(card_ids):
                    request = {
                        "model": model_id(model),
                        "messages": [{"role": "user", "content": panel["prompts"][arm][card]}],
                        "temperature": config["temperature"], "max_tokens": config["max_tokens"],
                        "seed": config["seed_base"] + round_number - 1,
                        "response_format": {"type": "json_object"},
                        "provider": {"allow_fallbacks": False, "require_parameters": True},
                    }
                    if isinstance(model, dict) and model.get("provider_only"):
                        request["provider"]["only"] = list(model["provider_only"])
                    tasks.append({"task_id": f"{block}__c{ci+1:03d}__r{round_number:03d}",
                        "block_id": block, "panel_id": panel["panel_id"],
                        "panel_index": pi, "model_id": model_id(model), "arm": arm,
                        "card_id": card, "round": round_number, "request": request,
                        "modes": list(panel["modes"]),
                        "mutually_exclusive": panel["mutually_exclusive"]})
    random.Random(config.get("shuffle_seed", config["seed_base"]) + round_number).shuffle(tasks)
    return tasks


def freeze_plan(config, output):
    """Save or verify the immutable request plan before network authentication."""
    validate_config(config)
    source_files = [Path(__file__), ROOT/"src/run_experiment.py", ROOT/"src/sequential_inference.py"]
    task_manifest = []
    for r in range(1, config["looks"][-1]+1):
        for t in request_tasks(config, r):
            task_manifest.append({k: t[k] for k in ("task_id", "block_id", "panel_id", "model_id", "arm", "card_id", "round")} |
                                 {"request_sha256": sha(t["request"]),
                                  "prompt_sha256": sha(t["request"]["messages"][0]["content"].encode())})
    catalogue_path = Path(config.get("catalogue_path", ROOT/"config/openrouter_catalogue_20261124.json"))
    core = {"config_sha256": sha(config), "source_sha256": {p.name: sha(p.read_bytes()) for p in source_files},
            "catalogue_sha256": sha(catalogue_path.read_bytes()), "tasks": task_manifest,
            "primary_endpoint_count": config["endpoint_count"], "looks": config["looks"],
            "failure_policy": "halt affected block at first incomplete round, retaining complete prefix",
            "transmission_policy": "only allowlisted preconstructed public-safe prompt strings"}
    fingerprint = sha(core)
    path = Path(output)/"frozen_plan.json"
    if path.exists():
        saved = read_json(path)
        if saved.get("plan_sha256") != fingerprint or saved.get("plan") != core:
            raise RuntimeError("Frozen config, prompts, code, or catalogue changed; use a new version")
    else:
        atomic_json(path, {"created_utc": utc(), "plan_sha256": fingerprint, "plan": core})
    return fingerprint, len(task_manifest)


def parse_prediction(response, modes, mutually_exclusive):
    content = response["choices"][0]["message"].get("content", "")
    if not isinstance(content, str):
        raise ValueError("Content is not text")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped).strip()
    raw = json.loads(stripped)
    if not isinstance(raw, dict) or set(raw) != set(modes) | {"rationale"}:
        raise ValueError("Unexpected output keys")
    if not isinstance(raw["rationale"], str):
        raise ValueError("Rationale must be text")
    for mode in modes:
        x = raw[mode]
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1:
            raise ValueError(f"Invalid probability for {mode}")
    total = sum(raw[m] for m in modes)
    normalized = dict(raw)
    factor = 1.0
    if mutually_exclusive:
        if abs(total-1) > .005 + 1e-12:
            raise ValueError("Exclusive probabilities do not sum to one within .005")
        factor = 1/total
        normalized.update({m: raw[m]*factor for m in modes})
    return raw, normalized, {"sum_before": total, "normalization_factor": factor,
                              "normalized": mutually_exclusive and total != 1}


class SafeTransport:
    """One result per planned request; fixed transport retries, never accuracy repair."""
    def __init__(self, config, output, deadline, *, opener=None):
        self.config, self.output, self.deadline = config, Path(output), deadline
        self.key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY must be in the process environment")
        self.opener = opener or urllib.request.urlopen
        self.lock = threading.Lock()
        self.reserved = 0.0
        self.spent = 0.0
        path = Path(config.get("catalogue_path", ROOT/"config/openrouter_catalogue_20261124.json"))
        self.catalogue = {m["id"]: m for m in read_json(path)["data"]}
        for f in self.output.glob("*.json"):
            if not f.name.endswith(".request.json"):
                self.spent += float(read_json(f).get("accounted_cost_usd", 0))

    def run(self, task):
        dest = self.output/(task["task_id"]+".json")
        request_hash = sha(task["request"])
        if dest.exists():
            old = read_json(dest)
            if old.get("request_sha256") != request_hash:
                raise RuntimeError("A cached result has a different request")
            if old.get("status") == "in_progress":
                old["status"] = "interrupted_unknown_outcome"
                old["validation_error"] = "Previous process stopped during request; not resubmitted"
                atomic_json(dest, old)
            return old
        payload = json.dumps(task["request"], ensure_ascii=False).encode()
        pricing = self.catalogue[task["model_id"]]["pricing"]
        if "prompt" not in pricing or "completion" not in pricing:
            raise ValueError("Frozen catalogue must include both token prices")
        rates = [float(pricing.get(k, 0) or 0) for k in ("prompt", "completion", "request")]
        if any(not math.isfinite(v) or v < 0 for v in rates):
            raise ValueError("Missing/invalid frozen catalogue prices")
        worst = len(payload)*rates[0] + self.config["max_tokens"]*rates[1] + rates[2]
        reservation = worst*self.config["transport_attempts"]
        with self.lock:
            if time.monotonic() >= self.deadline:
                return {"status": "runtime_stop", "task_id": task["task_id"]}
            if self.spent+self.reserved+reservation > self.config["max_cost_usd"]:
                return {"status": "budget_stop", "task_id": task["task_id"]}
            self.reserved += reservation
        record = {k: v for k, v in task.items() if k != "request"}
        record.update({"request_sha256": request_hash, "started_utc": utc(), "attempts": [],
                       "status": "in_progress", "accounted_cost_usd": reservation,
                       "reservation_upper_bound_usd": reservation})
        atomic_json(self.output/(task["task_id"]+".request.json"), task["request"])
        atomic_json(dest, record)
        cost = 0.0
        try:
            for attempt in range(self.config["transport_attempts"]):
                if time.monotonic() >= self.deadline:
                    record["status"] = "runtime_stop"
                    break
                request = urllib.request.Request(ENDPOINT, data=payload,
                    headers={"Authorization": "Bearer "+self.key, "Content-Type": "application/json",
                             "HTTP-Referer": "https://github.com/jtzach/air-passenger-LLM-PDM-study",
                             "X-Title": "Air-passenger sequential public-prompt benchmark"})
                try:
                    timeout = max(.1, min(self.config["request_timeout_seconds"], self.deadline-time.monotonic()))
                    with self.opener(request, timeout=timeout) as reply:
                        raw_bytes = reply.read()
                    record["response_sha256"] = sha(raw_bytes)
                    try:
                        response = json.loads(raw_bytes)
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        cost += worst
                        record["status"] = "invalid_output"
                        record["response_text"] = redact(raw_bytes.decode(errors="replace"))
                        record["validation_error"] = redact(exc)
                        record["attempts"].append({"number": attempt+1, "status": "invalid_envelope", "utc": utc(), "cost_upper_bound_usd": worst})
                        break
                    record["response"] = response
                    usage = response.get("usage") or {}
                    actual = usage.get("cost")
                    if isinstance(actual, (int, float)) and math.isfinite(actual) and actual >= 0:
                        charge, basis = float(actual), "OpenRouter usage.cost"
                    elif all(not isinstance(usage.get(k), bool) and isinstance(usage.get(k), (int, float)) and math.isfinite(usage[k]) and usage[k] >= 0 for k in ("prompt_tokens", "completion_tokens")):
                        charge = usage["prompt_tokens"]*rates[0]+usage["completion_tokens"]*rates[1]+rates[2]
                        basis = "frozen catalogue estimate"
                    else:
                        charge, basis = worst, "uncertain cost upper bound"
                    cost += charge
                    record["attempts"].append({"number": attempt+1, "status": "response", "utc": utc(), "cost_usd": charge, "cost_basis": basis})
                    record["returned_provider"] = response.get("provider")
                    record["returned_model"] = response.get("model")
                    record["generation_id"] = response.get("id")
                    try:
                        original, normalized, detail = parse_prediction(response, task["modes"], task["mutually_exclusive"])
                        record.update({"raw_prediction": original, "prediction": normalized,
                                       "normalization": detail, "status": "valid"})
                    except (KeyError, TypeError, ValueError) as exc:
                        record.update({"status": "invalid_output", "validation_error": redact(exc)})
                    break  # Invalid answers are retained, not repaired/retried.
                except urllib.error.HTTPError as exc:
                    cost += worst  # Billing is unverified even when no answer arrives.
                    record["attempts"].append({"number": attempt+1, "status": "http_error", "code": exc.code,
                        "detail": redact(exc.read().decode(errors="replace"))[:3000], "utc": utc(), "cost_upper_bound_usd": worst})
                    record["status"] = "failed"
                    if exc.code not in (408, 429, 500, 502, 503, 504):
                        break
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    cost += worst
                    record["status"] = "failed"
                    record["attempts"].append({"number": attempt+1, "status": "transport_error",
                        "detail": redact(exc), "utc": utc(), "cost_upper_bound_usd": worst})
                if attempt+1 < self.config["transport_attempts"]:
                    time.sleep(max(0, min(2**(attempt+1), self.deadline-time.monotonic())))
        except Exception as exc:
            # Preserve the attempt and reserve conservatively if an unexpected
            # client error makes its network/billing outcome uncertain.
            record.update({"status": "client_error", "validation_error": redact(exc)})
            cost = max(cost, reservation)
        finally:
            record.update({"finished_utc": utc(), "accounted_cost_usd": cost,
                           "cost_exceeded_reservation": cost > reservation+1e-12})
            atomic_json(dest, record)
            with self.lock:
                self.reserved -= reservation
                self.spent += cost
        return record


def panel_loss(panel, predictions):
    modes = panel["modes"]
    return 100*sum(c["weight"]*sum(abs(predictions[c["card_id"]][m]-c["observed"][m])
                      for m in modes)/len(modes) for c in panel["cards"])


def baseline_and_cap(panel):
    baseline = panel_loss(panel, {c["card_id"]: panel["baseline"] for c in panel["cards"]})
    if panel["mutually_exclusive"]:
        # A convex L1 loss over the probability simplex reaches its maximum
        # at a vertex: place all predicted mass on the smallest target mode.
        # Retain sum(p) explicitly so this also covers source rounding.
        cap = 100*sum(c["weight"]*(1+sum(c["observed"].values())-2*min(c["observed"].values()))
                      /len(panel["modes"]) for c in panel["cards"])
    else:
        cap = 100*sum(c["weight"]*sum(max(c["observed"][m], 1-c["observed"][m]) for m in panel["modes"])
                      /len(panel["modes"]) for c in panel["cards"])
    return baseline, cap


def record_identity(block, record):
    """Stop on observed service drift or reused generation IDs, not numeric ties."""
    identity = (record.get("returned_provider"), record.get("returned_model"))
    if not all(identity):
        block["diagnostics"].add("missing_provider_or_model_metadata")
        block["inference_assumptions_ok"] = False
        return "missing_service_identity"
    if block["identity"] is None:
        block["identity"] = identity
    elif tuple(block["identity"]) != identity:
        block["diagnostics"].add("provider_or_model_changed")
        block["inference_assumptions_ok"] = False
        return "provider_or_model_changed"
    gid = record.get("generation_id")
    if gid:
        if gid in block["generation_ids"]:
            block["diagnostics"].add("generation_id_reused")
            block["inference_assumptions_ok"] = False
            return "generation_id_reused"
        block["generation_ids"].add(gid)
    else:
        block["diagnostics"].add("generation_id_missing")
    return None


def public_block_state(block):
    return {k: sorted(v) if isinstance(v, set) else v for k, v in block.items()
            if k not in ("panel", "generation_ids")}


def execute(config, output, *, prepare_only=True, transport=None):
    output = Path(output)
    plan_hash, task_count = freeze_plan(config, output)
    if prepare_only:
        return {"status": "prepared_only_no_calls", "plan_sha256": plan_hash,
                "maximum_planned_requests": task_count}
    started_path = output/"execution_started.json"
    if started_path.exists():
        started = read_json(started_path)["started_utc"]
    else:
        started = utc()
        atomic_json(started_path, {"started_utc": started, "plan_sha256": plan_hash})
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds()
    deadline = time.monotonic()+max(0, config["max_runtime_seconds"]-elapsed)
    transport = transport or SafeTransport(config, output/"raw", deadline)
    blocks = {}
    for pi, panel in enumerate(config["panels"]):
        base, cap = baseline_and_cap(panel)
        for mi, model in enumerate(config["models"]):
            for ai, arm in enumerate(panel["arms"]):
                key = block_id(pi, mi, ai)
                blocks[key] = {"block_id": key, "panel_id": panel["panel_id"], "panel": panel,
                    "model_id": model_id(model), "arm": arm, "baseline_mae_pp": base,
                    "score_support_upper_pp": cap, "complete_rounds": 0, "round_scores": [],
                    "looks": [], "halt_reason": None, "identity": None,
                    "generation_ids": set(), "diagnostics": set(),
                    "inference_assumptions_ok": bool(config.get("iid_assumption_acknowledged", False))}
    global_stop = None
    with ThreadPoolExecutor(max_workers=config["max_workers"]) as pool:
        for r in range(1, config["looks"][-1]+1):
            active = {k for k, b in blocks.items() if b["halt_reason"] is None}
            if not active or global_stop:
                break
            if time.monotonic() >= deadline:
                global_stop = "runtime_cap"
                break
            pending = request_tasks(config, r, active)
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
                    b = blocks[task["block_id"]]
                    if record["status"] in ("budget_stop", "runtime_stop"):
                        global_stop = "cost_cap" if record["status"] == "budget_stop" else "runtime_cap"
                        continue
                    records[task["block_id"]][task["card_id"]] = record
                    if record["status"] != "valid":
                        b["halt_reason"] = b["halt_reason"] or "incomplete_round_"+record["status"]
                        b["incomplete_round"] = r
                    else:
                        drift = record_identity(b, record)
                        if drift:
                            b["halt_reason"] = b["halt_reason"] or drift
                            b["incomplete_round"] = r
                    if record.get("cost_exceeded_reservation") or transport.spent > config["max_cost_usd"]:
                        global_stop = "cost_cap_or_pricing_discrepancy"
            for key in active:
                b, rr = blocks[key], records[key]
                expected = {c["card_id"] for c in b["panel"]["cards"]} | {"no_persona"}
                if b["halt_reason"] or set(rr) != expected or any(x["status"] != "valid" for x in rr.values()):
                    continue
                loss = panel_loss(b["panel"], {c: rr[c]["prediction"] for c in expected if c != "no_persona"})
                control = panel_loss(b["panel"], {c["card_id"]: rr["no_persona"]["prediction"] for c in b["panel"]["cards"]})
                b["round_scores"].append({"round": r, "mae_pp": loss, "no_card_mae_pp": control,
                    "baseline_gain_pp": b["baseline_mae_pp"]-loss,
                    "no_card_gain_pp": control-loss})
                b["complete_rounds"] += 1
                if r in config["looks"]:
                    gains = [s["baseline_gain_pp"] for s in b["round_scores"]]
                    support = (b["baseline_mae_pp"]-b["score_support_upper_pp"], b["baseline_mae_pp"])
                    primary = scheduled_median_analysis(gains, endpoint_count=config["endpoint_count"],
                        looks=tuple(config["looks"]), family_alpha=config["primary_family_alpha"], bounds=support,
                        margin=config.get("practical_margin_pp", .5), precision=config.get("precision_half_width_pp", .25),
                        iid_assumption_acknowledged=b["inference_assumptions_ok"])
                    secondary = betting_mean_cs(gains, bounds=support, alpha=config["secondary_alpha_per_endpoint"]).as_dict()
                    secondary["assumptions_acknowledged"] = b["inference_assumptions_ok"]
                    if primary["identical_observations"]:
                        b["diagnostics"].add("identical_round_gains_do_not_prove_independence")
                    b["looks"].append({"round": r, "primary_median": primary, "secondary_mean": secondary})
                    atomic_json(output/"looks"/f"{key}__r{r:03d}.json", public_block_state(b))
                    if primary["decision"] != "continue":
                        b["halt_reason"] = primary["decision"]
            atomic_json(output/"progress.json", {"updated_utc": utc(), "round": r,
                "accounted_cost_usd": transport.spent, "global_stop": global_stop,
                "blocks": {k: public_block_state(b) for k, b in blocks.items()}})
            print(f"Round {r}: complete blocks {sum(b['complete_rounds']==r for b in blocks.values())}; cost ${transport.spent:.4f}", flush=True)
    for b in blocks.values():
        if b["halt_reason"] is None:
            b["halt_reason"] = global_stop or "maximum_rounds"
    summary = {"completed_utc": utc(), "plan_sha256": plan_hash,
        "accounted_cost_usd": transport.spent, "global_stop": global_stop,
        "inference_scope": "model-repeat median/mean under stated assumptions; no survey-sampling uncertainty",
        "blocks": {k: public_block_state(b) for k, b in blocks.items()}}
    atomic_json(output/"summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = execute(read_json(args.config), args.output, prepare_only=not args.execute)
    print(json.dumps({k: v for k, v in result.items() if k != "blocks"}, indent=2))


if __name__ == "__main__":
    main()
