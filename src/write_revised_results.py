"""Write publication tables from finalized, audited sequential results.

No model calls, private-source access, or invented fallback results.  The two
tables are tabular content only: the manuscript owns their floats and captions.
Run after analyse_sequential_results.py.  Python >=3.10; standard library only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_LABELS = {
    "google/gemma-3-4b-it": "Gemma 3 4B",
    "openai/gpt-4.1-mini": "GPT-4.1 mini",
    "qwen/qwen3-235b-a22b-2507": "Qwen3 235B A22B",
    "openai/gpt-4.1": "GPT-4.1",
}
PANELS = {"mid_2023": "MiD 2023", "fmg_2025": "Munich Airport 2025"}
ARMS = {"mid_2023": ("unanchored", "overall_rate_anchored"), "fmg_2025": ("unanchored",)}
FMG_IDS = {f"fmg_{p}_{r}" for p in ("business", "private")
           for r in ("domestic", "continental", "intercontinental")}
FMG_MODES = {"car_dropoff", "car_airport_parking", "car_offairport_parking",
             "car_other_parking", "taxi_ridehail", "rental_carsharing",
             "bus_transfer", "s_bahn", "uefex", "other"}
MID_MODES = {"car", "local_pt", "long_distance_rail"}
CAR_MODES = ("car_dropoff", "car_airport_parking", "car_offairport_parking", "car_other_parking")
FILES = ("table_numbers.json", "findings.json", "averaged_predictions.csv", "block_details.json")
DECISIONS = {
    "meaningful_improvement": "Improvement",
    "meaningful_degradation": "Degradation",
    "practically_equivalent": "Equivalent",
    "precise_but_inconclusive": "Inconclusive (precise)",
    "maximum_rounds_inconclusive": "Inconclusive at cap",
    "continue": "Unresolved at last look",
    "assumption_not_established": "Inference suppressed",
}
HALTS = {
    "incomplete_round_invalid_output": "invalid output",
    "incomplete_round_failed": "request failure",
    "incomplete_round_rate_limited": "rate limit",
    "missing_service_identity": "missing service identity",
    "provider_or_model_changed": "service changed",
    "generation_id_reused": "reused generation ID",
    "runtime_cap": "time cap",
    "cost_cap": "cost cap",
    "cost_cap_or_pricing_discrepancy": "cost safeguard",
    "maximum_rounds": "round cap",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tex(value: Any) -> str:
    escapes = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
               "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(escapes.get(c, c) for c in str(value))


def number(value: float | None, digits: int = 2, signed: bool = False) -> str:
    if value is None:
        return "---"
    if not math.isfinite(float(value)):
        raise ValueError("Non-finite number cannot enter the paper")
    value = float(value)
    if abs(value) < .5*10**-digits:
        value = 0.0
    return f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"


def integer(value: int) -> str:
    return f"{int(value):,}"


def near(a: float, b: float, label: str) -> None:
    if not math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-8):
        raise ValueError(f"Inconsistent {label}")


def block_key(row: dict) -> tuple[str, str, str]:
    return row["panel_id"], row["model_id"], row["arm"]


def ordered_blocks(numbers: dict) -> list[dict]:
    lookup = {block_key(r): r for r in numbers["blocks"]}
    return [lookup[(panel, model, arm)] for panel in PANELS for model in MODEL_LABELS
            for arm in ARMS[panel]]


def load_inputs(source: Path) -> tuple[dict, dict, list[dict], dict]:
    missing = [name for name in FILES if not (source/name).is_file()]
    if missing:
        raise FileNotFoundError("Final analysis is not available; no publication files written. Missing: "
                                + ", ".join(missing))
    numbers, findings, details = (read_json(source/name) for name in
                                ("table_numbers.json", "findings.json", "block_details.json"))
    with (source/"averaged_predictions.csv").open(encoding="utf-8-sig", newline="") as stream:
        predictions = list(csv.DictReader(stream))
    float_fields = ("observed", "predicted_mean", "predicted_sd", "predicted_min",
                    "predicted_max", "card_weight", "signed_error_pp")
    for row in predictions:
        for key in float_fields:
            row[key] = float(row[key]) if row.get(key) not in (None, "") else None
        row["n_rounds"] = int(row["n_rounds"])
    validate(numbers, findings, predictions, details)
    return numbers, findings, predictions, details


def validate(numbers: dict, findings: dict, predictions: list[dict], details: dict) -> None:
    """Reject partial, cross-run, inconsistent, or improperly scoped inputs."""
    if not numbers.get("completed_utc") or len(numbers.get("plan_sha256", "")) != 64:
        raise ValueError("Results must identify a finalized frozen run")
    if numbers.get("registered_endpoint_count") != 12 or numbers.get("looks") != [16, 32, 64]:
        raise ValueError("Unexpected endpoint family or scheduled looks")
    near(numbers["primary_family_alpha"], .04, "primary family allowance")
    near(numbers["secondary_alpha_per_endpoint"], .01/12, "secondary allowance")
    near(numbers["practical_margin_pp"], .5, "practical margin")
    expected = {(p, m, a) for p in PANELS for m in MODEL_LABELS for a in ARMS[p]}
    rows = numbers["blocks"]
    if len(rows) != 12 or {block_key(r) for r in rows} != expected:
        raise ValueError("All twelve registered endpoints, including failures, are required")
    by_id = {r["block_id"]: r for r in rows}
    if len(by_id) != 12 or set(details) != set(by_id):
        raise ValueError("Block-detail coverage differs from the endpoint table")
    availability = {r["block_id"]: r for r in numbers["availability"]}
    if set(availability) != set(by_id) or len(numbers["availability"]) != 12:
        raise ValueError("Availability must retain all twelve blocks")
    for row in rows:
        bid, n = row["block_id"], row["complete_prefix_rounds"]
        detail = details[bid]
        if detail["metrics"] != row or detail["availability"] != availability[bid]:
            raise ValueError("Input files disagree about block metrics or availability")
        if not isinstance(n, int) or not 0 <= n <= 64 or not row.get("halt_reason"):
            raise ValueError("Every finalized block needs a valid prefix and stopping reason")
        near(row["baseline_mae_pp"], numbers["baseline_mae_by_panel"][row["panel_id"]], "baseline")
        if n == 0 and any(row.get(k) is not None for k in ("ensemble_mae_pp", "no_card_ensemble_mae_pp")):
            raise ValueError("A zero-prefix block cannot receive an ensemble score")
        if n:
            for key in ("ensemble_mae_pp", "no_card_ensemble_mae_pp"):
                if not math.isfinite(row[key]) or not 0 <= row[key] <= 100:
                    raise ValueError("Invalid ensemble error")
        look = row["primary_checkpoint_round"]
        if look is not None:
            if look not in numbers["looks"] or look > n or not row["inference_assumptions_ok"]:
                raise ValueError("Inference must use an eligible complete-prefix checkpoint")
            if detail["latest_primary"] is None or detail["latest_primary"]["n"] != look:
                raise ValueError("Primary interval and checkpoint differ")
            for a, b in (("primary_median_gain_pp", "estimate"), ("primary_lower_pp", "lower"),
                         ("primary_upper_pp", "upper")):
                near(row[a], detail["latest_primary"][b], "primary interval")
            if row["primary_decision"] not in DECISIONS:
                raise ValueError("Unknown primary decision; review publication wording")
        elif any(row.get(k) is not None for k in ("primary_median_gain_pp", "primary_lower_pp", "primary_upper_pp")):
            raise ValueError("A block without a checkpoint cannot receive an inferential estimate")
    seen, targets, grouped = set(), {}, Counter()
    for row in predictions:
        bid = row["block_id"]
        if bid not in by_id or block_key(row) != block_key(by_id[bid]):
            raise ValueError("Prediction row has an unexpected block identity")
        if row["n_rounds"] != by_id[bid]["complete_prefix_rounds"] or row["n_rounds"] < 1:
            raise ValueError("Prediction average uses the wrong prefix length")
        key = bid, row["card_id"], row["mode"]
        if key in seen:
            raise ValueError("Duplicate prediction cell")
        seen.add(key)
        grouped[bid] += 1
        for field in ("observed", "predicted_mean"):
            if not math.isfinite(row[field]) or not 0 <= row[field] <= 1:
                raise ValueError("Prediction and target must be finite probabilities")
        near(row["signed_error_pp"], 100*(row["predicted_mean"]-row["observed"]), "cell error")
        tkey = row["panel_id"], row["card_id"], row["mode"]
        if tkey in targets:
            near(row["observed"], targets[tkey], "shared target")
        targets[tkey] = row["observed"]
        modes = MID_MODES if row["panel_id"] == "mid_2023" else FMG_MODES
        if row["mode"] not in modes or (row["panel_id"] == "fmg_2025" and row["card_id"] not in FMG_IDS):
            raise ValueError("Unexpected target category or unapproved airport group")
    for bid, row in by_id.items():
        expected_cells = (69 if row["panel_id"] == "mid_2023" else 60) if row["complete_prefix_rounds"] else 0
        if grouped[bid] != expected_cells:
            raise ValueError("A scored block must retain every group/mode cell")
    fmg = numbers["fmg_derived_groups"]
    if len(fmg) != 6 or {r["card_id"] for r in fmg} != FMG_IDS:
        raise ValueError("Only the six authorized airport aggregates may be published")
    for group in fmg:
        if set(group["observed"]) != FMG_MODES or group["weight"] <= 0:
            raise ValueError("Airport aggregate has invalid categories or weight")
        near(sum(group["observed"].values()), 1, "airport composition")
        for mode, value in group["observed"].items():
            key = "fmg_2025", group["card_id"], mode
            if key in targets:
                near(value, targets[key], "approved airport target")
    cost = numbers["cost"]
    if sum(cost["status_counts"].values()) != cost["attempted_requests"]:
        raise ValueError("Request status accounting does not balance")
    if sum(r["attempted_requests"] for r in availability.values()) != cost["attempted_requests"]:
        raise ValueError("Block request totals do not reconcile")
    expected_counts = dict(Counter(r["primary_decision"] or "no_valid_checkpoint" for r in rows))
    if findings["conditional_claim_counts"] != expected_counts:
        raise ValueError("Findings decision counts differ from metrics")


def status_text(row: dict) -> str:
    decision = row["primary_decision"]
    if not row["inference_assumptions_ok"]:
        base = "Inference suppressed"
    elif decision:
        base = DECISIONS[decision]
    else:
        base = "No valid look"
    halt = row["halt_reason"]
    if halt == decision or (halt == "maximum_rounds" and decision == "maximum_rounds_inconclusive"):
        return tex(base)
    return tex(base) + r"\newline " + tex(HALTS.get(halt, halt.replace("_", " ")))


def metrics_table(numbers: dict, details: dict) -> str:
    lines = [r"% Generated from finalized sequential results; do not edit numbers by hand.",
             r"\begingroup\footnotesize\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.16}",
             r"\noindent\begin{tabular}{@{}>{\raggedright\arraybackslash}p{.13\linewidth}>{\centering\arraybackslash}p{.045\linewidth}>{\centering\arraybackslash}p{.065\linewidth}>{\centering\arraybackslash}p{.07\linewidth}>{\centering\arraybackslash}p{.08\linewidth}>{\raggedright\arraybackslash}p{.22\linewidth}>{\raggedright\arraybackslash}p{.23\linewidth}@{}}",
             r"\toprule Model & Hint & $N$ & Group MAE & No-group MAE & Median gain [adjusted interval] & Decision / stop \\ \midrule"]
    last_panel = None
    for row in ordered_blocks(numbers):
        panel = row["panel_id"]
        if panel != last_panel:
            if last_panel is not None:
                lines.append(r"\midrule")
            lines.append(r"\multicolumn{7}{@{}l}{\textbf{" + tex(PANELS[panel]) +
                         " --- constant-baseline MAE " + number(numbers["baseline_mae_by_panel"][panel]) + r" pp}}\\[2pt]")
            last_panel = panel
        n, look = row["complete_prefix_rounds"], row["primary_checkpoint_round"]
        count = str(n) + (f" ({look})" if look is not None and look != n else "")
        interval = "---" if look is None else (number(row["primary_median_gain_pp"], signed=True) +
            r"\newline ["+number(row["primary_lower_pp"], signed=True)+", "+number(row["primary_upper_pp"], signed=True)+"]")
        cells = [tex(MODEL_LABELS[row["model_id"]]), "Yes" if row["arm"] == "overall_rate_anchored" else "No",
                 count, number(row.get("ensemble_mae_pp")), number(row.get("no_card_ensemble_mae_pp")),
                 interval, status_text(row)]
        lines.append(" & ".join(cells)+r" \\")
    notes = (r"All errors and gains are percentage points (pp). Smaller MAE is better; positive gain favors the model. "
             r"$N$ is the complete-round prefix used for averaged predictions; parentheses give the last inferential look when earlier. "
             r"Group and no-group MAEs score probabilities averaged across that prefix. The primary interval instead concerns "
             r"the median of individual-round baseline gains, with $\alpha=0.04/(12\times3)$ per scheduled look. "
             r"No-group comparisons are descriptive. A dash means unavailable, not zero. Incomplete rounds are excluded; "
             r"their valid individual responses are not selectively scored. No inference is made before 16 complete rounds "
             r"or after a service-assumption failure. Improvement/degradation require the full interval to exceed $+0.5$/fall below $-0.5$ pp.")
    lines += [r"\bottomrule", r"\multicolumn{7}{@{}p{.98\linewidth}@{}}{\scriptsize "+notes+r"}",
              r"\end{tabular}", r"\endgroup", ""]
    return "\n".join(lines)


def decision_summary(rows: list[dict]) -> str:
    counts = Counter(r["primary_decision"] or "no_valid_checkpoint" for r in rows)
    phrases = {
        "meaningful_improvement": "meaningful improvement", "meaningful_degradation": "meaningful degradation",
        "practically_equivalent": "practical equivalence", "precise_but_inconclusive": "a precise but inconclusive interval",
        "maximum_rounds_inconclusive": "an inconclusive interval at the round cap",
        "continue": "an unresolved interval at the last registered look",
        "assumption_not_established": "suppressed inference", "no_valid_checkpoint": "no valid inferential checkpoint",
    }
    return "; ".join(f"{counts[k]} with {phrases[k]}" for k in phrases if counts[k])


def results_text(numbers: dict) -> str:
    rows, cost = ordered_blocks(numbers), numbers["cost"]
    available = [r for r in rows if r["complete_prefix_rounds"]]
    infer = [r for r in rows if r["primary_checkpoint_round"] is not None]
    lines = [r"% Generated from finalized sequential results; descriptive scores and primary inference differ.",
             r"\paragraph{Completion and primary decisions.} " +
             f"All 12 registered conditions are reported in Table~\\ref{{tab:newmetrics}}, including operational failures. "
             f"{len(available)} produced at least one complete round and {len(infer)} reached a usable registered checkpoint. "
             "The primary classification was: "+tex(decision_summary(rows))+". "
             "These decisions concern the median round-level gain over the constant baseline, conditional on identically distributed, "
             "independent model outputs under the frozen protocol. They do not quantify survey uncertainty.", ""]
    for panel in PANELS:
        selected = [r for r in available if r["panel_id"] == panel]
        name = PANELS[panel]
        baseline = numbers["baseline_mae_by_panel"][panel]
        if not selected:
            sentence = f"{name} had no complete model panel; no model error or behavioral accuracy is inferred."
        else:
            chunks = []
            for arm in ARMS[panel]:
                values = [r["ensemble_mae_pp"] for r in selected if r["arm"] == arm]
                arm_name = "without the overall hint" if arm == "unanchored" else "with the overall hint"
                if values:
                    span = number(min(values)) if len(values) == 1 else number(min(values))+"--"+number(max(values))
                    chunks.append(f"{span} pp {arm_name} ({len(values)} available models)")
                else:
                    chunks.append(f"no complete panels {arm_name}")
            better = sum(r["ensemble_mae_pp"] < baseline for r in selected)
            sentence = (f"For {name}, the constant baseline had an MAE of {number(baseline)} pp. "
                        "Errors of averaged group predictions were "+"; ".join(chunks)+". "
                        f"{better} of {len(selected)} available conditions had a lower ensemble MAE than the baseline. "
                        "This is a descriptive score comparison, distinct from the median-gain decision.")
        lines += [r"\paragraph{"+tex(name)+r" scores.} "+sentence, ""]
    controls_better = sum(r["ensemble_mae_pp"] < r["no_card_ensemble_mae_pp"] for r in available)
    controls_equal = sum(math.isclose(r["ensemble_mae_pp"], r["no_card_ensemble_mae_pp"], abs_tol=1e-12, rel_tol=0) for r in available)
    controls_worse = len(available)-controls_better-controls_equal
    control_sentence = (f"Relative to its matched no-group model control, the group ensemble had a lower MAE in {controls_better} "
                        f"conditions, a higher MAE in {controls_worse}, and an equal MAE in {controls_equal}. "
                        "These paired-control comparisons carry no additional confirmatory significance claim.")
    paired = numbers.get("hint_comparisons", [])
    if paired:
        summary = "; ".join(tex(MODEL_LABELS[r["model_id"]])+" "+
            number(r["median_round_gain_from_hint_pp"], signed=True)+f" pp ($N={r['common_prefix_rounds']}$)"
            for r in sorted(paired, key=lambda r: list(MODEL_LABELS).index(r["model_id"])))
        control_sentence += (" Using each model's common complete-round prefix, the descriptive median change in error "
                             "from supplying the overall hint was: "+summary+". Positive values mean lower error with the hint. "
                             "This comparison is not a separately allocated confirmatory endpoint.")
    else:
        control_sentence += " No model had complete rounds in both MiD conditions for a paired hint comparison."
    lines += [r"\paragraph{What the card and the hint add.} "+control_sentence, ""]
    if infer:
        margin = numbers["practical_margin_pp"]
        secondary = Counter()
        for row in infer:
            lower, upper = row["mean_cs_lower_pp"], row["mean_cs_upper_pp"]
            key = ("improvement" if lower > margin else "degradation" if upper < -margin else
                   "equivalence" if lower >= -margin and upper <= margin else "inconclusive")
            secondary[key] += 1
        if secondary["inconclusive"] == len(infer):
            sentence = f"All {len(infer)} secondary mean confidence sequences remained inconclusive relative to the 0.5-pp decision margin. "
        else:
            sentence = "The secondary mean confidence sequences classified "+", ".join(
                f"{secondary[k]} as {k}" for k in ("improvement", "degradation", "equivalence", "inconclusive") if secondary[k])+". "
        sentence += ("They concern a different estimand under a stable conditional-mean assumption and do not override the primary median rule. "
                     "The two tasks' MAEs should not be compared as a common difficulty scale: they use different populations, weights, and mode sets.")
        lines += [r"\paragraph{Secondary uncertainty.} "+sentence, ""]
    lines += [r"\paragraph{Operational accounting.} " +
        f"The accounted cost was US\\${number(cost['accounted_cost_usd'])}, combining reported charges with conservative estimates "
        "for unverified billing. " +
        (f"The {integer(cost['status_counts']['in_progress'])} unknown outcomes are archived requests interrupted by the administrative pause, not calls still running. " if cost["status_counts"].get("in_progress") else "")+
        "The supplement provides full request and failure accounting. "
        "Table~\\ref{tab:observations} provides fixed descriptive checks of where averaged predictions agree with group differences. "
        "They are associations, not estimates of what would happen if a person's car ownership, residence, or travel purpose changed.", ""]
    return "\n".join(lines)


def accounting_text(numbers: dict) -> str:
    cost = numbers["cost"]
    labels = {"in_progress": "interrupted with unknown outcome", "invalid_output": "invalid outputs",
              "failed": "failed", "valid": "valid"}
    statuses = ", ".join(f"{integer(v)} {tex(labels.get(k, k.replace('_', ' ')))}"
                         for k, v in sorted(cost["status_counts"].items()))
    unretained = sum(r["valid_responses_outside_prefix"] for r in numbers["availability"])
    return ("% Generated final operational accounting.\n"
        f"The finalized run contains {integer(cost['attempted_requests'])} task-request records ({statuses}). "
        f"There are {integer(cost['attempt_records'])} transport-attempt records, with retries on {integer(cost['requests_with_retries'])} requests. "
        f"The {integer(cost['retained_prefix_requests'])} requests in complete prefixes support the reported scores; "
        f"{integer(unretained)} otherwise valid responses outside those prefixes are excluded. "
        "Unknown outcomes are archived administrative-pause interruptions, not currently running calls. "
        f"Accounted cost is US\\${number(cost['accounted_cost_usd'], 6)}, combining reported charges and conservative estimates "
        "for unverified billing; this is not an independently audited billed total. "
        f"{integer(cost['normalized_exclusive_responses'])} airport outputs required the permitted small composition normalization. " +
        ("The global stopping reason was "+tex(str(cost["global_stop"]).replace("_", " "))+". " if cost.get("global_stop") else "")+
        "Request statuses, excluded partial rounds, and original/replacement identifiers remain in the reproduction archive.\n")


def observations(numbers: dict, predictions: list[dict]) -> list[dict]:
    """Four declared illustrations; never rank/select examples by realized error."""
    model = "openai/gpt-4.1"
    blocks = {block_key(r): r for r in numbers["blocks"]}
    fmg = {r["card_id"]: r for r in numbers["fmg_derived_groups"]}
    result = []

    def contrast_reading(data: float, llm: float | None) -> str:
        if llm is None:
            return "No complete model prediction is available."
        if data*llm < 0:
            return "The model reverses the observed group ordering."
        if number(100*data, 1) == number(100*llm, 1):
            return "The contrast matches at the displayed precision."
        return ("The model predicts a larger contrast." if abs(llm) > abs(data)
                else "The model predicts a smaller contrast.")

    def mid_cell(group: str, feature: str) -> dict | None:
        matches = [r for r in predictions if r["panel_id"] == "mid_2023" and r["group"] == group
                   and r["feature"] == feature and r["mode"] == "long_distance_rail"]
        if not matches:
            return None
        answer = dict(matches[0])
        chosen = [r for r in matches if r["model_id"] == model and r["arm"] == "overall_rate_anchored"]
        answer["model_value"] = chosen[0]["predicted_mean"] if chosen else None
        return answer

    def append(key: str, panel: str, title: str, data: float | None, llm: float | None,
               ids: list[str], modes: list[str], definition: str, meaning: str, weights: dict | None = None) -> None:
        arm = "overall_rate_anchored" if panel == "mid_2023" else "unanchored"
        block = blocks[(panel, model, arm)]
        result.append({"observation_id": key, "panel_id": panel, "model_id": model, "arm": arm,
            "block_id": block["block_id"], "complete_prefix_rounds": block["complete_prefix_rounds"],
            "title": title, "data_pp": None if data is None else 100*data,
            "llm_pp": None if llm is None else 100*llm,
            "signed_error_pp": None if data is None or llm is None else 100*(llm-data),
            "card_ids": ids, "modes": modes, "definition": definition,
            "normalized_weights": weights, "meaning": meaning, "inferential_status": "descriptive, no allocated contrast test"})

    low, high = mid_cell("No car", "anzauto_gr1"), mid_cell("4 or more cars", "anzauto_gr1")
    data = high["observed"]-low["observed"] if low and high else None
    llm = high["model_value"]-low["model_value"] if low and high and low["model_value"] is not None and high["model_value"] is not None else None
    if data is None:
        meaning = "No complete MiD panel; comparison unavailable."
    else:
        meaning = contrast_reading(data, llm)+" Both household groups still report rail co-use."
    append("mid_car_ownership_rail_difference", "mid_2023", "Rail co-use: 4+ cars minus no car", data, llm,
           [r["card_id"] for r in (high, low) if r], ["long_distance_rail"],
           "Long-distance-rail probability in households with at least four cars minus households with no car.", meaning)
    regional = mid_cell("Urban region - small-town and village area", "RegioStaR7")
    regional_reading = "No complete model prediction is available."
    if regional and regional["model_value"] is not None:
        error = regional["model_value"]-regional["observed"]
        regional_reading = ("The model underpredicts" if error < 0 else "The model overpredicts" if error > 0 else "The model matches")+" this group's rail use."
    append("mid_small_town_rail_level", "mid_2023", "Rail co-use: small towns/villages in urban regions",
           regional["observed"] if regional else None, regional["model_value"] if regional else None,
           [regional["card_id"]] if regional else [], ["long_distance_rail"],
           "Absolute long-distance-rail probability for the stated residential-area group, not a difference.",
           regional_reading+" The rail leg need not be airport access.")

    fmg_prediction = {(r["card_id"], r["mode"]): r["predicted_mean"] for r in predictions
        if r["panel_id"] == "fmg_2025" and r["model_id"] == model and r["arm"] == "unanchored"}
    weights = {}
    values = {}
    for purpose in ("business", "private"):
        ids = [f"fmg_{purpose}_{region}" for region in ("domestic", "continental", "intercontinental")]
        total = sum(fmg[c]["weight"] for c in ids)
        weights.update({c: fmg[c]["weight"]/total for c in ids})
        observed = sum(weights[c]*fmg[c]["observed"]["taxi_ridehail"] for c in ids)
        predicted = sum(weights[c]*fmg_prediction[c, "taxi_ridehail"] for c in ids) if all((c, "taxi_ridehail") in fmg_prediction for c in ids) else None
        values[purpose] = observed, predicted
    data = values["business"][0]-values["private"][0]
    llm = values["business"][1]-values["private"][1] if all(v[1] is not None for v in values.values()) else None
    append("fmg_purpose_taxi_difference", "fmg_2025", "Taxi/ride-hail: business minus private", data, llm,
           sorted(fmg), ["taxi_ridehail"],
           "Aggregate each purpose over the three departing-flight regions using observed source-group weights normalized within that purpose, then subtract private from business.",
           contrast_reading(data, llm)+" Flight-region composition also differs by purpose.", weights)

    high_id, low_id = "fmg_private_intercontinental", "fmg_private_domestic"
    data = sum(fmg[high_id]["observed"][m]-fmg[low_id]["observed"][m] for m in CAR_MODES)
    llm = sum(fmg_prediction[high_id, m]-fmg_prediction[low_id, m] for m in CAR_MODES) if all((c, m) in fmg_prediction for c in (high_id, low_id) for m in CAR_MODES) else None
    append("fmg_private_region_car_difference", "fmg_2025", "Private-car access: intercontinental minus domestic, private trips", data, llm,
           [high_id, low_id], list(CAR_MODES),
           "Sum drop-off and the three parking categories within private travel, then subtract domestic from intercontinental departing flights.",
           contrast_reading(data, llm)+" Car categories include parking with a shuttle.")
    return result


def observations_table(rows: list[dict]) -> str:
    lines = [r"% Fixed descriptive illustrations; exact calculation inputs are archived in publication_observations.json.",
             r"\begingroup\footnotesize\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.2}",
             r"\noindent\begin{tabular}{@{}>{\raggedright\arraybackslash}p{.27\linewidth}>{\centering\arraybackslash}p{.075\linewidth}>{\centering\arraybackslash}p{.075\linewidth}>{\centering\arraybackslash}p{.075\linewidth}>{\raggedright\arraybackslash}p{.38\linewidth}@{}}",
             r"\toprule Comparison & Data & LLM & Error & What it means / limit \\ \midrule"]
    for row in rows:
        contrast = not row["observation_id"].endswith("_level")
        cells = [tex(row["title"]), number(row["data_pp"], digits=1, signed=contrast),
                 number(row["llm_pp"], digits=1, signed=contrast), number(row["signed_error_pp"], digits=1, signed=True), tex(row["meaning"])]
        lines.append(" & ".join(cells)+r" \\")
    mid_n = next(r["complete_prefix_rounds"] for r in rows if r["panel_id"] == "mid_2023")
    fmg_n = next(r["complete_prefix_rounds"] for r in rows if r["panel_id"] == "fmg_2025")
    note = (f"Fixed illustrations, using GPT-4.1 with the overall hint for MiD ($N={mid_n}$ complete rounds) "
            f"and without a hint for the airport ($N={fmg_n}$). Data/LLM entries are percentage-point differences, "
            "except the residential-area row, which gives percentages. Error is LLM minus data in percentage points. "
            "Errors use unrounded values. "
            "Model values average the complete prefix; no unavailable output is substituted. Purpose aggregates use "
            "the observed mix of flight regions within each purpose, for both data and predictions. These descriptive "
            "examples were fixed before the final results and carry no separate significance claim.")
    lines += [r"\bottomrule", r"\multicolumn{5}{@{}p{.98\linewidth}@{}}{\scriptsize "+note+r"}",
              r"\end{tabular}", r"\endgroup", ""]
    return "\n".join(lines)


def write(source: Path, destination: Path) -> dict:
    numbers, findings, predictions, details = load_inputs(source)
    selected = observations(numbers, predictions)
    products = {
        "revised_metrics_table.tex": metrics_table(numbers, details),
        "revised_results_text.tex": results_text(numbers),
        "revised_observations_table.tex": observations_table(selected),
        "revised_accounting_text.tex": accounting_text(numbers),
    }
    # Generate and validate everything before writing; absence never makes placeholders.
    if any("nan" in text.lower().split() for text in products.values()):
        raise ValueError("Non-finite value in generated prose")
    destination.mkdir(parents=True, exist_ok=True)
    for name, text in products.items():
        (destination/name).write_text(text, encoding="utf-8", newline="\n")
    (source/"publication_observations.json").write_text(json.dumps({
        "plan_sha256": numbers["plan_sha256"], "model_selection": "GPT-4.1 fixed before final outputs; no replacement for unavailable predictions",
        "rows": selected}, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")
    qa = {"status": "PASS", "plan_sha256": numbers["plan_sha256"], "completed_utc": numbers["completed_utc"],
          "reported_endpoints": len(numbers["blocks"]), "observation_rows": len(selected),
          "no_model_calls": True, "private_source_access": False,
          "input_sha256": {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in FILES},
          "output_sha256": {name: hashlib.sha256((destination/name).read_bytes()).hexdigest() for name in products}}
    (source/"publication_writer_qa.json").write_text(json.dumps(qa, indent=2)+"\n", encoding="utf-8")
    return qa


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT/"results/sequential_20261125")
    parser.add_argument("--output", type=Path, default=ROOT/"manuscript/generated")
    args = parser.parse_args()
    print(json.dumps(write(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
