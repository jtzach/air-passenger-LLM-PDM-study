"""Analyze a completed sequential run, publishing only authorized derivatives.

The private config is read locally. Public FMG targets are restricted to the six
approved purpose/flight-region aggregates; original source rows/counts, full
private config, and source workbooks are never copied. No API calls are made.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, median, stdev
from sequential_inference import betting_mean_cs

FMG_IDS = {f"fmg_{purpose}_{region}" for purpose in ("business", "private")
           for region in ("domestic", "continental", "intercontinental")}
PREFERRED_MID = ["openai/gpt-4.1", "google/gemma-3-4b-it"]
PREFERRED_FMG = "openai/gpt-4.1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def save_csv(path, rows):
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def model_id(model):
    return model if isinstance(model, str) else model["id"]


def label(card, panel_id):
    if panel_id == "fmg_2025":
        if card["card_id"] not in FMG_IDS:
            raise ValueError("Public FMG output is limited to the six approved derived groups")
        _, purpose, region = card["card_id"].split("_")
        return purpose.title()+" / "+region.title()
    matched = re.search(r"attribute is .*?: (.*?)\. All other", card.get("description", ""))
    return matched[1] if matched else card["card_id"]


def metrics(panel, predictions, subset=None):
    cards = [c for c in panel["cards"] if subset is None or c["feature"] == subset]
    total_weight = sum(c["weight"] for c in cards)
    if total_weight <= 0:
        raise ValueError("Scoring subset has no positive weight")
    ae, se, signed, max_error, jsd = 0.0, 0.0, 0.0, 0.0, 0.0
    for c in cards:
        for mode in panel["modes"]:
            p, q = c["observed"][mode], predictions[c["card_id"]][mode]
            w = c["weight"]/total_weight/len(panel["modes"])
            error = q-p
            ae += w*abs(error)
            se += w*error**2
            signed += w*error
            max_error = max(max_error, abs(error))
            mid = (p+q)/2
            entropy = lambda x: -sum(t*math.log2(t) for t in (x, 1-x) if t > 0)
            jsd += w*max(0, entropy(mid)-(entropy(p)+entropy(q))/2)
    result = {"mae_pp": 100*ae, "rmse_pp": 100*math.sqrt(se), "signed_bias_pp": 100*signed,
              "max_cell_error_pp": 100*max_error, "mean_bernoulli_jsd_bits": jsd}
    if panel["mutually_exclusive"]:
        result["categorical_total_variation_pp"] = 100*sum(c["weight"]/total_weight * .5 *
            sum(abs(predictions[c["card_id"]][m]-c["observed"][m]) for m in panel["modes"]) for c in cards)
    return result


def near(a, b, description, tolerance=1e-8):
    if not math.isclose(a, b, abs_tol=tolerance, rel_tol=1e-10):
        raise ValueError(f"Reconstruction mismatch: {description}")


def verify_primary_checkpoint(checkpoint, gains, config, support):
    primary, n = checkpoint["primary_median"], checkpoint["round"]
    if n not in config["looks"] or primary["n"] != n or n > len(gains):
        raise ValueError("Primary checkpoint is not a registered complete-prefix look")
    alpha = config["primary_family_alpha"]/(config["endpoint_count"]*len(config["looks"]))
    near(primary["alpha"], alpha, "primary alpha")
    near(primary["estimate"], median(gains[:n]), "primary median")
    eligible = [k for k in range(1, n//2+1)
                if sum(math.comb(n, j) for j in range(k))/(1 << n) <= alpha/2]
    if eligible:
        k, ordered = max(eligible), sorted(gains[:n])
        near(primary["lower"], ordered[k-1], "median lower bound")
        near(primary["upper"], ordered[n-k], "median upper bound")
    else:
        near(primary["lower"], support[0], "median full-support lower bound")
        near(primary["upper"], support[1], "median full-support upper bound")
    secondary = checkpoint["secondary_mean"]
    if secondary["n"] != n:
        raise ValueError("Mean CS and median checkpoint use different n")
    near(secondary["estimate"], mean(gains[:n]), "secondary mean")
    near(secondary["alpha"], config["secondary_alpha_per_endpoint"], "secondary alpha")
    recalculated = betting_mean_cs(gains[:n], bounds=support, alpha=config["secondary_alpha_per_endpoint"])
    near(secondary["lower"], recalculated.lower, "secondary mean lower bound")
    near(secondary["upper"], recalculated.upper, "secondary mean upper bound")
    margin, precision = config.get("practical_margin_pp", .5), config.get("precision_half_width_pp", .25)
    lower, upper = primary["lower"], primary["upper"]
    decision = ("meaningful_improvement" if lower > margin else
                "meaningful_degradation" if upper < -margin else
                "practically_equivalent" if lower >= -margin and upper <= margin else
                "precise_but_inconclusive" if upper-lower <= 2*precision else
                "maximum_rounds_inconclusive" if n == config["looks"][-1] else "continue")
    if not primary.get("iid_assumption_acknowledged"):
        decision = "assumption_not_established"
    if primary["decision"] != decision:
        raise ValueError("Primary checkpoint decision differs from its interval")


def analyze(config_path, run_dir, output_dir):
    config_path, run_dir, output_dir = map(Path, (config_path, run_dir, output_dir))
    config = read(config_path)
    summary_path = run_dir/"summary.json"
    if not summary_path.exists():
        raise RuntimeError("The completed run summary is not available; no snapshot was analyzed")
    summary, frozen = read(summary_path), read(run_dir/"frozen_plan.json")
    if not summary.get("completed_utc") or any(not b.get("halt_reason") for b in summary["blocks"].values()):
        raise ValueError("The run is not finalized")
    if frozen["plan"]["config_sha256"] != digest(config) or frozen["plan_sha256"] != digest(frozen["plan"]):
        raise ValueError("Local config or frozen plan hash differs")
    if summary["plan_sha256"] != frozen["plan_sha256"]:
        raise ValueError("Summary belongs to a different experiment plan")
    panels = {p["panel_id"]: p for p in config["panels"]}
    for panel in panels.values():
        if any(set(c["observed"]) != set(panel["modes"]) for c in panel["cards"]):
            raise ValueError("Target dictionary contains unregistered mode fields")
    if "fmg_2025" in panels and {c["card_id"] for c in panels["fmg_2025"]["cards"]} != FMG_IDS:
        raise ValueError("Refusing to publish an unapproved FMG target panel")
    labels = {model_id(m): m.get("label", model_id(m)) if isinstance(m, dict) else m for m in config["models"]}
    expected = {(p["panel_id"], model_id(m), arm) for p in config["panels"] for m in config["models"] for arm in p["arms"]}
    actual = {(b["panel_id"], b["model_id"], b["arm"]) for b in summary["blocks"].values()}
    if actual != expected or len(summary["blocks"]) != len(expected):
        raise ValueError("All registered blocks must be reported, including failures")
    planned = {t["task_id"]: t for t in frozen["plan"]["tasks"]}
    amendment = frozen["plan"].get("administrative_amendment", {})
    excluded_tasks = set(amendment.get("excluded_from_scoring_task_ids", []))
    if not excluded_tasks <= set(planned):
        raise ValueError("Administrative exclusions contain unplanned requests")
    if amendment and summary.get("parent_plan_sha256") != amendment["parent_plan_sha256"]:
        raise ValueError("Administrative parent-plan association differs")
    records, lookup = [], {}
    for path in sorted((run_dir/"raw").glob("*.json")):
        if path.name.endswith(".request.json"):
            continue
        rec = read(path)
        task_id = rec["task_id"]
        if task_id not in planned:
            raise ValueError("Unexpected raw task outside the frozen plan")
        request = read(path.with_name(path.stem+".request.json"))
        if digest(request) != rec["request_sha256"] or rec["request_sha256"] != planned[task_id]["request_sha256"]:
            raise ValueError("Raw request fingerprint differs from plan")
        records.append(rec)  # Includes discarded administrative attempts and all their costs.
        if task_id in excluded_tasks:
            continue
        key = (rec["block_id"], rec["round"], rec["card_id"])
        if key in lookup:
            raise ValueError("Duplicate planned observation")
        lookup[key] = rec
    accounted_cost = sum(r.get("accounted_cost_usd", 0) for r in records)
    near(accounted_cost, summary["accounted_cost_usd"], "total accounted cost", tolerance=1e-7)
    metrics_rows, prediction_rows, control_rows, round_rows, feature_rows = [], [], [], [], []
    block_details, ensembles, controls, used_tasks = {}, {}, {}, set()
    primary_records, secondary_records, availability = [], [], []
    for bid, block in summary["blocks"].items():
        panel = panels[block["panel_id"]]
        modes, cards, n = panel["modes"], panel["cards"], block["complete_rounds"]
        identity = {"block_id": bid, "panel_id": panel["panel_id"], "model_id": block["model_id"],
                    "model_label": labels[block["model_id"]], "arm": block["arm"]}
        baseline_predictions = {c["card_id"]: panel["baseline"] for c in cards}
        baseline = metrics(panel, baseline_predictions)
        near(baseline["mae_pp"], block["baseline_mae_pp"], bid+" baseline")
        if panel["mutually_exclusive"]:
            cap = 100*sum(c["weight"]*max(sum(abs(float(m==vertex)-c["observed"][m]) for m in modes)
                      /len(modes) for vertex in modes) for c in cards)
        else:
            cap = 100*sum(c["weight"]*sum(max(p, 1-p) for p in c["observed"].values())/len(modes) for c in cards)
        near(cap, block["score_support_upper_pp"], bid+" theoretical score cap")
        rr, cp, reconstructed = defaultdict(list), defaultdict(list), []
        if len(block["round_scores"]) != n:
            raise ValueError("Complete-round count does not match the saved score prefix")
        for r in range(1, n+1):
            predictions = {}
            for cid in [c["card_id"] for c in cards]+["no_persona"]:
                rec = lookup.get((bid, r, cid))
                if rec is None or rec["status"] != "valid":
                    raise ValueError("Claimed complete prefix has missing/invalid responses")
                prediction = rec["prediction"]
                if any(isinstance(prediction.get(m), bool) or not isinstance(prediction.get(m), (int, float)) or
                       not math.isfinite(prediction[m]) or not 0 <= prediction[m] <= 1 for m in modes):
                    raise ValueError("Invalid probability in a retained response")
                if panel["mutually_exclusive"]:
                    near(sum(prediction[m] for m in modes), 1.0, "normalized categorical response", 1e-10)
                used_tasks.add(rec["task_id"])
                for mode in modes:
                    (cp[mode] if cid == "no_persona" else rr[cid, mode]).append(prediction[mode])
                predictions[cid] = prediction
            loss = metrics(panel, {c["card_id"]: predictions[c["card_id"]] for c in cards})["mae_pp"]
            no_card_loss = metrics(panel, {c["card_id"]: predictions["no_persona"] for c in cards})["mae_pp"]
            saved = block["round_scores"][r-1]
            if saved["round"] != r:
                raise ValueError("Successful rounds were skipped or reordered")
            for field, value in [("mae_pp", loss), ("no_card_mae_pp", no_card_loss),
                                 ("baseline_gain_pp", baseline["mae_pp"]-loss), ("no_card_gain_pp", no_card_loss-loss)]:
                near(saved[field], value, bid+" "+field)
            row = {**identity, **saved}
            round_rows.append(row)
            reconstructed.append(row)
        raw_block = [r for r in records if r["block_id"] == bid]
        counts = Counter(r["status"] for r in raw_block)
        available = {**identity, "complete_prefix_rounds": n, "attempted_requests": len(raw_block),
            "valid_responses": counts.get("valid", 0), "unsuccessful_requests": sum(v for k, v in counts.items() if k != "valid"),
            "retained_prefix_requests": n*(len(cards)+1),
            "valid_responses_outside_prefix": counts.get("valid", 0)-n*(len(cards)+1),
            "accounted_cost_usd": sum(r.get("accounted_cost_usd", 0) for r in raw_block),
            "halt_reason": block["halt_reason"], "inference_assumptions_ok": block["inference_assumptions_ok"],
            "provider": (block.get("identity") or [None, None])[0],
            "returned_model": (block.get("identity") or [None, None])[1]}
        availability.append(available)
        metric = {**identity, "complete_prefix_rounds": n, "halt_reason": block["halt_reason"],
                  "baseline_mae_pp": baseline["mae_pp"], "inference_assumptions_ok": block["inference_assumptions_ok"],
                  "primary_checkpoint_round": None, "primary_decision": None,
                  "primary_median_gain_pp": None, "primary_lower_pp": None, "primary_upper_pp": None,
                  "mean_cs_lower_pp": None, "mean_cs_upper_pp": None}
        checkpoints = block["looks"]
        gains = [row["baseline_gain_pp"] for row in reconstructed]
        for checkpoint in checkpoints:
            verify_primary_checkpoint(checkpoint, gains, config, (baseline["mae_pp"]-cap, baseline["mae_pp"]))
        latest = checkpoints[-1] if checkpoints and block["inference_assumptions_ok"] else None
        if latest:
            primary, secondary = latest["primary_median"], latest["secondary_mean"]
            if not primary.get("iid_assumption_acknowledged") or not secondary.get("assumptions_acknowledged"):
                raise ValueError("Eligible checkpoint lacks its recorded assumptions")
            metric.update(primary_checkpoint_round=latest["round"], primary_decision=primary["decision"],
                primary_median_gain_pp=primary["estimate"], primary_lower_pp=primary["lower"], primary_upper_pp=primary["upper"],
                mean_cs_lower_pp=secondary["lower"], mean_cs_upper_pp=secondary["upper"])
            primary_records.append({**identity, "checkpoint_round": latest["round"], **primary})
            secondary_records.append({**identity, "checkpoint_round": latest["round"], **secondary})
        if n:
            ensemble = {c["card_id"]: {mode: mean(rr[c["card_id"], mode]) for mode in modes} for c in cards}
            control = {mode: mean(cp[mode]) for mode in modes}
            ensembles[bid], controls[bid] = ensemble, control
            result = metrics(panel, ensemble)
            control_result = metrics(panel, {c["card_id"]: control for c in cards})
            metric.update({"ensemble_"+k: v for k, v in result.items()})
            metric.update(no_card_ensemble_mae_pp=control_result["mae_pp"],
                ensemble_gain_vs_baseline_pp=baseline["mae_pp"]-result["mae_pp"],
                ensemble_gain_vs_no_card_pp=control_result["mae_pp"]-result["mae_pp"],
                mean_single_round_mae_pp=mean(row["mae_pp"] for row in reconstructed),
                median_single_round_mae_pp=median(row["mae_pp"] for row in reconstructed),
                mean_single_round_baseline_gain_pp=mean(gains), median_single_round_baseline_gain_pp=median(gains),
                mean_paired_no_card_gain_pp=mean(row["no_card_gain_pp"] for row in reconstructed),
                median_paired_no_card_gain_pp=median(row["no_card_gain_pp"] for row in reconstructed))
            for c in cards:
                for mode in modes:
                    values = rr[c["card_id"], mode]
                    prediction_rows.append({**identity, "card_id": c["card_id"], "group": label(c, panel["panel_id"]),
                        "feature": c["feature"], "mode": mode, "observed": c["observed"][mode],
                        "predicted_mean": mean(values), "predicted_sd": stdev(values) if n > 1 else None,
                        "predicted_min": min(values), "predicted_max": max(values), "n_rounds": n,
                        "card_weight": c["weight"], "signed_error_pp": 100*(mean(values)-c["observed"][mode])})
            for mode in modes:
                values = cp[mode]
                control_rows.append({**identity, "mode": mode, "predicted_mean": mean(values),
                    "predicted_sd": stdev(values) if n > 1 else None, "n_independent_rounds_assumed": n})
            if panel["panel_id"] == "mid_2023":
                for feature in sorted({c["feature"] for c in cards}):
                    fm, fb = metrics(panel, ensemble, feature), metrics(panel, baseline_predictions, feature)
                    fc = metrics(panel, {c["card_id"]: control for c in cards}, feature)
                    feature_rows.append({**identity, "feature": feature, "n_rounds": n,
                        **{"ensemble_"+k: v for k, v in fm.items()}, "baseline_mae_pp": fb["mae_pp"],
                        "no_card_mae_pp": fc["mae_pp"], "gain_vs_baseline_pp": fb["mae_pp"]-fm["mae_pp"]})
        metrics_rows.append(metric)
        block_details[bid] = {"metrics": metric, "availability": available,
            "latest_primary": latest["primary_median"] if latest else None,
            "latest_secondary": latest["secondary_mean"] if latest else None,
            "last_available_checkpoint_round": checkpoints[-1]["round"] if checkpoints else None,
            "inference_suppression_reason": None if latest else ("service_assumptions_failed" if not block["inference_assumptions_ok"] else "no_registered_checkpoint"),
            "diagnostics": block.get("diagnostics", [])}
    contrasts, paired_arms = [], []
    for bid, block in summary["blocks"].items():
        if block["panel_id"] != "mid_2023" or bid not in ensembles:
            continue
        panel = panels["mid_2023"]
        cars = {label(c, "mid_2023"): c for c in panel["cards"] if c["feature"] == "anzauto_gr1"}
        if "No car" not in cars:
            continue
        reference = cars["No car"]
        for group, c in cars.items():
            if group == "No car": continue
            for mode in panel["modes"]:
                observed = c["observed"][mode]-reference["observed"][mode]
                predicted = ensembles[bid][c["card_id"]][mode]-ensembles[bid][reference["card_id"]][mode]
                contrasts.append({"block_id": bid, "model_id": block["model_id"], "arm": block["arm"],
                    "group": group, "reference_group": "No car", "mode": mode,
                    "observed_difference_pp": 100*observed, "predicted_difference_pp": 100*predicted,
                    "contrast_error_pp": 100*(predicted-observed), "n_rounds": block["complete_rounds"],
                    "interpretation": "descriptive association; no car-ownership causal effect"})
    by_key = {(r["panel_id"], r["model_id"], r["arm"]): r for r in metrics_rows}
    for mid in labels:
        a, b = by_key.get(("mid_2023", mid, "unanchored")), by_key.get(("mid_2023", mid, "overall_rate_anchored"))
        if not a or not b: continue
        n = min(a["complete_prefix_rounds"], b["complete_prefix_rounds"])
        if not n: continue
        ra, rb = summary["blocks"][a["block_id"]]["round_scores"], summary["blocks"][b["block_id"]]["round_scores"]
        diffs = [ra[i]["mae_pp"]-rb[i]["mae_pp"] for i in range(n)]
        paired_arms.append({"model_id": mid, "common_prefix_rounds": n,
            "mean_round_gain_from_hint_pp": mean(diffs), "median_round_gain_from_hint_pp": median(diffs),
            "unanchored_ensemble_rounds": a["complete_prefix_rounds"], "anchored_ensemble_rounds": b["complete_prefix_rounds"],
            "ensemble_mae_difference_pp": a["ensemble_mae_pp"]-b["ensemble_mae_pp"],
            "inference": "descriptive; not an additional allocated confirmatory contrast"})
    derived_fmg = []
    if "fmg_2025" in panels:
        for c in panels["fmg_2025"]["cards"]:
            derived_fmg.append({"group": label(c, "fmg_2025"), "card_id": c["card_id"],
                                "weight": c["weight"], "observed": c["observed"]})
    figures = {"mid_example": [], "fmg": [], "metadata": {
        "mid_models": PREFERRED_MID, "model_labels": labels, "fmg_model": PREFERRED_FMG,
        "mid_condition": "overall_rate_anchored", "fmg_condition": "unanchored",
        "prediction_basis": "mean across each block's complete round prefix",
        "unavailable_blocks": [r["block_id"] for r in metrics_rows if not r["complete_prefix_rounds"]],
        "block_availability": availability}}
    if "mid_2023" in panels:
        for c in panels["mid_2023"]["cards"]:
            group = label(c, "mid_2023")
            if c["feature"] != "anzauto_gr1" or group not in ("No car", "4 or more cars"): continue
            for mode in panels["mid_2023"]["modes"]:
                values = {b["model_id"]: ensembles[bid][c["card_id"]][mode] for bid, b in summary["blocks"].items()
                          if b["panel_id"] == "mid_2023" and b["arm"] == "overall_rate_anchored" and bid in ensembles}
                figures["mid_example"].append({"group": group, "mode": mode, "observed": c["observed"][mode], "predictions": values})
    for c in derived_fmg:
        values = {b["model_id"]: ensembles[bid][c["card_id"]] for bid, b in summary["blocks"].items()
                  if b["panel_id"] == "fmg_2025" and b["arm"] == "unanchored" and bid in ensembles}
        figures["fmg"].append({"group": c["group"], "observed": c["observed"], "predictions": values})
    fmg_preferred = by_key.get(("fmg_2025", PREFERRED_FMG, "unanchored"))
    figures["metadata"]["fmg_model_available"] = bool(fmg_preferred and fmg_preferred["complete_prefix_rounds"])
    cost_summary = {"attempted_requests": len(records), "planned_maximum_requests": len(planned),
        "status_counts": dict(Counter(r["status"] for r in records)),
        "attempt_records": sum(len(r.get("attempts", [])) for r in records),
        "requests_with_retries": sum(len(r.get("attempts", [])) > 1 for r in records),
        "accounted_cost_usd": accounted_cost,
        "cost_basis": "reported charges plus conservative estimates for unverified billing",
        "retained_prefix_requests": len(used_tasks), "responses_outside_complete_prefix": len(records)-len(used_tasks),
        "normalized_exclusive_responses": sum(bool(r.get("normalization", {}).get("normalized")) for r in records),
        "http_status_counts": dict(Counter(str(a["code"]) for r in records for a in r.get("attempts", []) if "code" in a)),
        "global_stop": summary["global_stop"]}
    if amendment:
        cost_summary["administrative_pause"] = {
            "parent_plan_sha256": amendment["parent_plan_sha256"],
            "replaced_logical_round": amendment["interrupted_round"],
            "replacement_blocks": amendment["replacement_blocks"],
            "excluded_partial_requests": sum(r["task_id"] in excluded_tasks for r in records),
            "unknown_outcomes_reserved_usd": amendment["unknown_outcome_reservations_usd"],
            "prior_active_execution_seconds": amendment["prior_active_execution_seconds"],
            "selection_rule": "Whole incomplete round replacement after explicit user pause; no accuracy-based selection"}
    findings = {"statistical_scope": "Conditional model-repeat inference, not survey or human-population uncertainty.",
        "initial_three_repeat_study": "Excluded; this analysis uses only the new frozen run.",
        "car_ownership": "MiD contrasts compare household car groups. They do not identify a causal effect of owning a car, and car use does not require ownership or driving.",
        "mode_scope": "MiD records nonexclusive whole-journey co-use; FMG records a categorical airport-access split. Panel MAEs are not directly comparable across different mode sets.",
        "examples": [x for x in contrasts if x["group"] == "4 or more cars" and x["arm"] == "overall_rate_anchored"],
        "largest_mid_cell_errors": sorted([r for r in prediction_rows if r["panel_id"] == "mid_2023"], key=lambda x: abs(x["signed_error_pp"]), reverse=True)[:12],
        "anchored_regional_rail_cells": [r for r in prediction_rows if r["panel_id"] == "mid_2023" and
            r["arm"] == "overall_rate_anchored" and r["feature"] == "RegioStaR7" and r["mode"] == "long_distance_rail"],
        "anchored_car_household_rail_cells": [r for r in prediction_rows if r["panel_id"] == "mid_2023" and
            r["arm"] == "overall_rate_anchored" and r["feature"] == "anzauto_gr1" and r["mode"] == "long_distance_rail"],
        "anchored_gpt_feature_results": [r for r in feature_rows if r["model_id"] == "openai/gpt-4.1" and
            r["arm"] == "overall_rate_anchored"],
        "hint_comparisons": paired_arms,
        "conditional_claim_counts": dict(Counter(r["primary_decision"] or "no_valid_checkpoint" for r in metrics_rows)),
        "caution": "Examples beyond the frozen endpoints are descriptive; no extra significance claims are assigned to selected contrasts."}
    table_numbers = {"plan_sha256": summary["plan_sha256"], "completed_utc": summary["completed_utc"],
        "registered_endpoint_count": config["endpoint_count"], "looks": config["looks"],
        "primary_family_alpha": config["primary_family_alpha"],
        "secondary_alpha_per_endpoint": config["secondary_alpha_per_endpoint"],
        "practical_margin_pp": config.get("practical_margin_pp", .5),
        "blocks": metrics_rows, "availability": availability, "cost": cost_summary,
        "primary_checkpoints": primary_records, "secondary_checkpoints": secondary_records,
        "hint_comparisons": paired_arms, "fmg_derived_groups": derived_fmg,
        "baseline_mae_by_panel": {pid: metrics(p, {c["card_id"]: p["baseline"] for c in p["cards"]})["mae_pp"] for pid, p in panels.items()}}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in [("block_metrics", metrics_rows), ("availability", availability),
                       ("averaged_predictions", prediction_rows), ("no_card_predictions", control_rows),
                       ("round_scores", round_rows), ("mid_feature_metrics", feature_rows),
                       ("mid_car_ownership_contrasts", contrasts), ("mid_hint_contrasts", paired_arms)]:
        save_csv(output_dir/(name+".csv"), rows)
    for name, obj in [("block_details", block_details), ("cost_and_status", cost_summary),
                      ("derived_fmg_targets", derived_fmg), ("table_numbers", table_numbers),
                      ("figure_data", figures), ("findings", findings)]:
        save_json(output_dir/(name+".json"), obj)
    qa = {"status": "PASS", "registered_blocks": len(expected), "reported_blocks": len(metrics_rows),
          "retained_request_count": len(used_tasks), "reconstructed_complete_rounds": len(round_rows),
          "reconstructed_prediction_cells": len(prediction_rows), "verified_request_count": len(records),
          "invalidated_inference_blocks": [b for b, x in block_details.items() if x["inference_suppression_reason"] == "service_assumptions_failed"],
          "private_source_records_exported": False, "fmg_derived_groups_exported": len(derived_fmg)}
    save_json(output_dir/"analysis_qa.json", qa)
    return qa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.config, args.run_dir, args.output), indent=2))


if __name__ == "__main__":
    main()
