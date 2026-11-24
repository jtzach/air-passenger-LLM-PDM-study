"""Run a bounded, resumable public-aggregate LLM benchmark through OpenRouter.

Only OPENROUTER_API_KEY is read for authentication. Credentials are never written
to requests, results, or logs. No respondent records are read or transmitted.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODES = ("car", "local_pt", "long_distance_rail")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(obj):
    b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(b).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    text = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", str(text))
    text = re.sub(r'"(?:user_id|account_id)"\s*:\s*"[^"]+"', '"user_id":"[REDACTED_ACCOUNT_ID]"', text)
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return text.replace(key, "[REDACTED]") if key else text


def sanitize(obj):
    if isinstance(obj, dict):
        return {k:("[REDACTED_ACCOUNT_ID]" if k in ("user_id","account_id") else sanitize(v)) for k,v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return redact(obj) if isinstance(obj,str) else obj


def make_prompt(persona, arm, baseline):
    # Whitelist: conditional observed rates are deliberately NEVER read here.
    description = persona.get("description_en", "No further traveller or journey attribute is specified.")
    prompt = (
        "You are participating in a travel-behaviour research benchmark. Apply persona-based reasoning "
        "to estimate reported transport use. Do not browse or look up a survey table.\n\n"
        "Population: residents of Germany aged 14 or older, self-reporting an overnight journey "
        "in the preceding three months during the MiD 2023 survey (fieldwork 2023-2024). "
        "Aircraft is the recorded main mode of the journey. Consider a randomly drawn journey within "
        "the cohort profile below. This is a group-level marginal profile; do not invent a joint "
        "age, income, household, origin, destination, or airport when it is unspecified.\n\n"
        f"Cohort profile: {description}\n\n"
        "Survey task: Which transport modes were used for the outward AND return journey? "
        "All modes used in combinations could be selected. For each of the following, estimate "
        "the probability that it was also reported alongside aircraft: (1) car; (2) local bus "
        "or rail, including urban/suburban/regional public transport; (3) long-distance train. "
        "These are three separate, nonexclusive yes/no mentions; they "
        "need not add to one. Ground modes can be reported on either direction and either side "
        "of the flight. The question does not isolate access to a named airport.\n"
        "Car use does not require owning a car or being its driver. If household companions "
        "are specified, these count accompanying household members only; zero does not establish "
        "that the traveller was alone.\n"
    )
    if arm == "overall_rate_anchored":
        prompt += (
            "\nPopulation-level reference (all eligible overnight journeys with aircraft as main mode, "
            "NOT this specific cohort): car={:.6f}, local bus/rail={:.6f}, long-distance train={:.6f}. "
            "Use these overall rates as reference and estimate whether the supplied cohort differs.\n"
        ).format(*(baseline[m] for m in MODES))
    prompt += (
        "\nReturn only one JSON object with exactly four keys: car, local_pt, long_distance_rail, rationale. "
        "The first three must be numbers from 0 to 1 (not percentages). rationale must be at most "
        "40 words and describe a plausible hypothesis, not claim to know respondents' actual motives."
    )
    return prompt


def parse_prediction(response):
    content = response["choices"][0]["message"].get("content", "")
    if not isinstance(content, str):
        raise ValueError("Content is not text")
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped).strip()
    value = json.loads(stripped)
    if set(value) != set(MODES) | {"rationale"}:
        raise ValueError("Unexpected output keys")
    for m in MODES:
        if isinstance(value[m], bool) or not isinstance(value[m], (float, int)) or not 0 <= value[m] <= 1:
            raise ValueError(f"Invalid probability for {m}")
    if not isinstance(value["rationale"], str):
        raise ValueError("Rationale must be text")
    return value


class Runner:
    def __init__(self, config, output):
        self.config = config
        self.output = output
        self.key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self.key:
            raise RuntimeError("Set OPENROUTER_API_KEY in the process environment; never place it in source files.")
        self.lock = threading.Lock()
        self.catalogue = {m["id"]: m for m in read_json(ROOT / "config/openrouter_catalogue_20261124.json")["data"]}
        self.spent = 0.0
        self.reserved = 0.0
        self.finished = 0
        for f in output.glob("*.json"):
            if f.name.endswith(".request.json"):
                continue
            old = read_json(f)
            self.spent += float(old.get("accounted_cost_usd", 0) or 0)

    def run(self, task):
        dest = self.output / (task["task_id"] + ".json")
        if dest.exists():
            previous = read_json(dest)
            if previous.get("request_sha256") != sha(task["request"]):
                raise RuntimeError("Refusing to reuse cached result with different request")
            return "cached", previous.get("status")
        payload = json.dumps(task["request"]).encode()
        pricing = self.catalogue[task["model_id"]]["pricing"]
        # One UTF-8 byte per input token is deliberately conservative for these English prompts.
        worst_attempt = len(payload) * float(pricing["prompt"]) + self.config["max_tokens"] * float(pricing["completion"])
        reservation = worst_attempt * self.config["transport_attempts"]
        with self.lock:
            if self.spent + self.reserved + reservation > self.config["max_cost_usd"]:
                return "budget_stop", "not_run"
            self.reserved += reservation
        started = time.monotonic()
        record = {k: v for k, v in task.items() if k != "request"}
        record.update({"request_sha256": sha(task["request"]), "started_utc": utc(), "attempts": [], "status": "failed", "accounted_cost_usd": 0.0})
        write_json(self.output / (task["task_id"] + ".request.json"), task["request"])
        try:
            for attempt in range(self.config["transport_attempts"]):
                req = urllib.request.Request(
                    self.config["endpoint"], data=payload,
                    headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                             "HTTP-Referer": "https://github.com/jtzach/air-passenger-LLM-PDM-study",
                             "X-Title": "MiD air-passenger LLM-PDM aggregate research"})
                try:
                    with urllib.request.urlopen(req, timeout=self.config["request_timeout_seconds"]) as reply:
                        raw = reply.read()
                    response = json.loads(raw)
                    record["response"] = response
                    record["response_sha256"] = sha(raw)
                    usage = response.get("usage", {})
                    estimated = usage.get("prompt_tokens", 0) * float(pricing["prompt"]) + usage.get("completion_tokens", 0) * float(pricing["completion"])
                    actual = usage.get("cost")
                    record["accounted_cost_usd"] += float(actual if actual is not None else estimated)
                    record["cost_basis"] = "OpenRouter usage.cost" if actual is not None else "catalogue token-price estimate"
                    record["attempts"].append({"number": attempt + 1, "status": "response", "utc": utc()})
                    try:
                        record["prediction"] = parse_prediction(response)
                        record["status"] = "valid"
                    except (ValueError, KeyError, TypeError) as exc:
                        record["status"] = "invalid_output"
                        record["validation_error"] = redact(exc)
                    break
                except urllib.error.HTTPError as exc:
                    detail = redact(exc.read().decode(errors="replace"))[:3000]
                    record["attempts"].append({"number": attempt + 1, "status": "http_error", "code": exc.code, "detail": detail, "utc": utc()})
                    if exc.code not in (408, 429, 500, 502, 503, 504):
                        break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                    # A timeout may still have been billed: retain a conservative upper-bound cost.
                    record["accounted_cost_usd"] += worst_attempt
                    record["attempts"].append({"number": attempt + 1, "status": "transport_error", "detail": redact(exc), "utc": utc(), "uncertain_cost_upper_bound_usd": worst_attempt})
                if attempt + 1 < self.config["transport_attempts"]:
                    time.sleep(2 ** (attempt + 1))
        finally:
            record["finished_utc"] = utc()
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            write_json(dest, sanitize(record))
            with self.lock:
                self.reserved -= reservation
                self.spent += record["accounted_cost_usd"]
                self.finished += 1
                if self.finished % 10 == 0:
                    print(f"Completed {self.finished} new calls; accounted cost ${self.spent:.4f}", flush=True)
        return task["task_id"], record["status"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    config = read_json(ROOT / "config/experiment.json")
    if args.smoke:
        personas = [{"persona_id": "smoke_generic", "feature": "none", "description_en": "No further traveller or journey attribute is specified."}]
        baseline = {m: 0.0 for m in MODES}  # Unused: smoke calls are unanchored.
        arms, replicates = ["unanchored"], 1
        output = ROOT / "results/smoke"
    else:
        personas = read_json(ROOT / "data/processed/personas.json")
        if isinstance(personas, dict):
            personas = personas["personas"]
        baseline = read_json(ROOT / "data/processed/overall_baseline.json")
        baseline = baseline.get("observed", baseline)
        arms, replicates = config["arms"], config["replicates"]
        output = ROOT / "results/raw"
        if config["include_no_persona_control"]:
            personas.append({"persona_id": "no_persona", "feature": "none", "description_en": "No further traveller or journey attribute is specified."})
    output.mkdir(parents=True, exist_ok=True)
    tasks = []
    for mi, model in enumerate(config["models"]):
        for persona in personas:
            for arm in arms:
                for rep in range(replicates):
                    tid = f"m{mi+1:02d}__{persona['persona_id']}__{arm}__r{rep+1:02d}"
                    request = {"model": model["id"], "messages": [{"role": "user", "content": make_prompt(persona, arm, baseline)}],
                               "temperature": config["temperature"], "max_tokens": config["max_tokens"],
                               "seed": config["seed_base"] + rep, "response_format": {"type": "json_object"},
                               "provider": {"allow_fallbacks": False, "require_parameters": True}}
                    tasks.append({"task_id": tid, "model_id": model["id"], "model_label": model["label"],
                                  "persona_id": persona["persona_id"], "feature": persona["feature"], "arm": arm,
                                  "replicate": rep + 1, "request": request})
    random.Random(config["shuffle_seed"]).shuffle(tasks)
    plan = {"created_utc": utc(), "config_sha256": sha(config), "task_count": len(tasks),
            "persona_file_sha256": None if args.smoke else sha((ROOT / "data/processed/personas.json").read_bytes()),
            "tasks": [{k:v for k,v in t.items() if k != "request"} | {"request_sha256": sha(t["request"])} for t in tasks]}
    plan_path = output.parent / ("smoke_plan.json" if args.smoke else "experiment_plan.json")
    if plan_path.exists():
        old = read_json(plan_path)
        if old["config_sha256"] != plan["config_sha256"] or old["tasks"] != plan["tasks"]:
            raise RuntimeError("Experiment plan changed; archive old results before a new version")
    else:
        write_json(plan_path, plan)
    print(f"Prepared {len(tasks)} calls across {len(config['models'])} models; cap ${config['max_cost_usd']:.2f}", flush=True)
    if args.prepare_only:
        return
    runner = Runner(config, output)
    statuses = {}
    with ThreadPoolExecutor(max_workers=config["max_workers"]) as pool:
        for future in as_completed([pool.submit(runner.run, task) for task in tasks]):
            tid, status = future.result()
            statuses[status] = statuses.get(status, 0) + 1
            if args.smoke:
                print(tid, status, flush=True)
    summary = {"completed_utc": utc(), "status_counts": statuses, "accounted_cost_usd": runner.spent, "task_count": len(tasks)}
    write_json(output.parent / ("smoke_summary.json" if args.smoke else "run_summary.json"), summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
