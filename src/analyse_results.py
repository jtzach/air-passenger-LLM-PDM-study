"""Evaluate aggregate probabilities, preserving overlapping cohort denominators.

No hypothesis tests or respondent-level confidence intervals can be recovered
from these published marginal tables. Repetition ranges concern model outputs.
"""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]
MODES = ("car", "local_pt", "long_distance_rail")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def entropy(p):
    return -sum(x * math.log2(x) for x in (p, 1-p) if x > 0)


def bernoulli_jsd(p, q):
    return max(0.0, entropy((p+q)/2) - (entropy(p)+entropy(q))/2)


def metrics(rows, equal_strata=False):
    by_feature_mode = defaultdict(list)
    for r in rows:
        by_feature_mode[(r["feature"], r["mode_id"])].append(r)
    summaries = []
    for key, group in by_feature_mode.items():
        weights = [1.0 if equal_strata else r["weighted_base"] for r in group]
        total = sum(weights)
        observed_mean = sum(w*r["observed_share"] for w,r in zip(weights,group))/total
        predicted_mean = sum(w*r["predicted_mean"] for w,r in zip(weights,group))/total
        summaries.append({
            "ae": sum(w*abs(r["predicted_mean"]-r["observed_share"]) for w,r in zip(weights,group))/total,
            "se": sum(w*(r["predicted_mean"]-r["observed_share"])**2 for w,r in zip(weights,group))/total,
            "bias": sum(w*(r["predicted_mean"]-r["observed_share"]) for w,r in zip(weights,group))/total,
            "jsd": sum(w*bernoulli_jsd(r["predicted_mean"],r["observed_share"]) for w,r in zip(weights,group))/total,
            "shape_ae": sum(w*abs((r["predicted_mean"]-predicted_mean)-(r["observed_share"]-observed_mean)) for w,r in zip(weights,group))/total,
        })
    return {"mae":100*mean(x["ae"] for x in summaries),
            "rmse":100*math.sqrt(mean(x["se"] for x in summaries)),
            "bias_pp":100*mean(x["bias"] for x in summaries),
            "bernoulli_jsd_bits":mean(x["jsd"] for x in summaries),
            "centred_mae_pp":100*mean(x["shape_ae"] for x in summaries),
            "max_absolute_error_pp":100*max(abs(r["predicted_mean"]-r["observed_share"]) for r in rows),
            "n_cohort_mode_cells":len(rows), "n_features":len({r["feature"] for r in rows})}


def main():
    config = read_json(ROOT / "config/experiment.json")
    personas = read_json(ROOT / "data/processed/personas.json")
    if isinstance(personas, dict):
        personas = personas["personas"]
    by_persona = {p["persona_id"]: p for p in personas}
    baseline = read_json(ROOT / "data/processed/overall_baseline.json")
    baseline = baseline.get("observed", baseline)
    planned_models = {m["id"]:m for m in config["models"]}
    records = []
    for path in sorted((ROOT / "results/raw").glob("*.json")):
        if not path.name.endswith(".request.json"):
            records.append(read_json(path))
    valid = [r for r in records if r["status"] == "valid"]
    lookup = {(r["model_id"],r["arm"],r["persona_id"],r["replicate"]):r for r in valid}
    # Documented post hoc availability decision, made before comparative errors
    # were computed. The original all-five-model common panel was empty because
    # Gemma3 12B had upstream429 errors and malformed output. Keep its records.
    expected_personas = list(by_persona) + (["no_persona"] if config["include_no_persona_control"] else [])
    availability = []
    models = {}
    for model_id, model in planned_models.items():
        rr = [r for r in records if r["model_id"] == model_id]
        complete_model = all((model_id,arm,pid,rep) in lookup for arm in config["arms"]
                             for pid in expected_personas for rep in range(1,config["replicates"]+1))
        availability.append({"model_id":model_id,"model_label":model["label"],"model_group":model["tier"],
            "planned_calls":len(expected_personas)*len(config["arms"])*config["replicates"],
            "valid_calls":sum(r["status"]=="valid" for r in rr),"invalid_output_calls":sum(r["status"]=="invalid_output" for r in rr),
            "failed_calls":sum(r["status"]=="failed" for r in rr),"primary_panel":complete_model})
        if complete_model:
            models[model_id]=model
    if not models:
        raise RuntimeError("No complete models; report availability rather than computing misleading errors")
    # Common panel across complete models, both arms and all three repetitions.
    complete = [p for p in personas if all((m,a,p["persona_id"],rep) in lookup
                for m in models for a in config["arms"] for rep in range(1,config["replicates"]+1))]
    if not complete:
        raise RuntimeError("No complete common cohort panel; inspect missing responses before interpretation")
    excluded = sorted(set(by_persona)-{p["persona_id"] for p in complete})
    prediction_rows = []
    repetition_rows = []
    for model_id,model in models.items():
        for arm in config["arms"]:
            for p in complete:
                for mode in MODES:
                    ps = [lookup[(model_id,arm,p["persona_id"],rep)]["prediction"][mode] for rep in range(1,config["replicates"]+1)]
                    row = {"model_id":model_id,"model_label":model["label"],"model_group":model["tier"],"arm":arm,
                           "persona_id":p["persona_id"],"feature":p["feature"],"category_label":p["category_label"],
                           "mode_id":mode,"observed_share":p["observed"][mode],"predicted_mean":mean(ps),
                           "predicted_sd":stdev(ps) if len(ps)>1 else 0.0,"predicted_min":min(ps),"predicted_max":max(ps),
                           "weighted_base":p["weighted_base"],"unweighted_n":p["unweighted_n"],"n_repeats":len(ps)}
                    prediction_rows.append(row)
                    for rep,value in enumerate(ps,1):
                        repetition_rows.append({**row,"replicate":rep,"predicted_mean":value})
            # No-persona model calls are constant predictions applied to the same common panel.
            control_keys = [(model_id,arm,"no_persona",rep) for rep in range(1,config["replicates"]+1)]
            if all(k in lookup for k in control_keys):
                for p in complete:
                    for mode in MODES:
                        ps = [lookup[k]["prediction"][mode] for k in control_keys]
                        prediction_rows.append({"model_id":model_id+"::no_persona","model_label":model["label"]+" (no persona)",
                            "model_group":"no_persona_control","arm":arm,"persona_id":p["persona_id"],"feature":p["feature"],
                            "category_label":p["category_label"],"mode_id":mode,"observed_share":p["observed"][mode],
                            "predicted_mean":mean(ps),"predicted_sd":stdev(ps),"predicted_min":min(ps),"predicted_max":max(ps),
                            "weighted_base":p["weighted_base"],"unweighted_n":p["unweighted_n"],"n_repeats":len(ps)})
    for p in complete:
        for mode in MODES:
            prediction_rows.append({"model_id":"overall_baseline","model_label":"Observed overall rate","model_group":"baseline",
                "arm":"baseline","persona_id":p["persona_id"],"feature":p["feature"],"category_label":p["category_label"],
                "mode_id":mode,"observed_share":p["observed"][mode],"predicted_mean":baseline[mode],"predicted_sd":0.0,
                "predicted_min":baseline[mode],"predicted_max":baseline[mode],"weighted_base":p["weighted_base"],
                "unweighted_n":p["unweighted_n"],"n_repeats":0})
    groups = defaultdict(list)
    for r in prediction_rows:
        groups[(r["model_id"],r["arm"])].append(r)
    metric_rows = []
    feature_rows = []
    for (model_id,arm),rows in groups.items():
        identity = {k:rows[0][k] for k in ("model_id","model_label","model_group","arm")}
        score = metrics(rows)
        rep_scores = [metrics([r for r in repetition_rows if r["model_id"]==model_id and r["arm"]==arm and r["replicate"]==rep])["mae"]
                      for rep in range(1,config["replicates"]+1)] if model_id in models else []
        metric_rows.append({**identity,**score,"equal_stratum_mae_pp":metrics(rows,True)["mae"],
                            "repeat_mae_min_pp":min(rep_scores) if rep_scores else None,
                            "repeat_mae_max_pp":max(rep_scores) if rep_scores else None})
        for feature in sorted({r["feature"] for r in rows}):
            feature_rows.append({**identity,"feature":feature,**metrics([r for r in rows if r["feature"]==feature])})
    out = ROOT / "results/processed"
    save_csv(out/"model_availability.csv",availability)
    save_csv(out/"prediction_summary.csv",prediction_rows)
    save_csv(out/"prediction_repetitions.csv",repetition_rows)
    save_csv(out/"model_metrics.csv",metric_rows)
    save_csv(out/"feature_metrics.csv",feature_rows)
    failures = [{k:r.get(k) for k in ("task_id","model_id","persona_id","arm","replicate","status","validation_error")} for r in records if r["status"]!="valid"]
    save_csv(out/"failed_calls.csv",failures)
    model_scores = [m for m in metric_rows if m["model_id"] in models]
    numbers = {"n_personas_planned":len(personas),"n_personas_common_panel":len(complete),"excluded_personas":excluded,
        "n_unique_features":len({p["feature"] for p in complete}),"n_models":len(models),"n_attempted_models":len(planned_models),
        "active_model_ids":list(models),"model_availability":availability,"n_arms":len(config["arms"]),
        "n_repeats":config["replicates"],"completed_calls":len(records),"valid_calls":len(valid),"invalid_or_failed_calls":len(records)-len(valid),
        "accounted_cost_usd":sum(float(r.get("accounted_cost_usd",0) or 0) for r in records),
        "overall_rates":baseline,"selected_features":sorted({p["feature"] for p in personas}),
        "baseline_metrics":next(m for m in metric_rows if m["model_id"]=="overall_baseline"),
        "best_per_arm":{arm:min((m for m in model_scores if m["arm"]==arm),key=lambda r:r["mae"]) for arm in config["arms"]},
        "models_beating_overall_baseline":sum(m["mae"]<next(x["mae"] for x in metric_rows if x["model_id"]=="overall_baseline") for m in model_scores),
        "model_metrics":metric_rows,
        "metric_definition":"Within each feature and mode, weight absolute probability errors by the published rounded weighted stratum base; average equally over three modes and four features, multiply by100. Primary scores use mean of3modelruns. Repeated groups overlap acrossfeatures; countsneverpooled.",
        "availability_policy":"Post hoc endpoint-completeness decision before error scoring: compare all23cohorts acrossmodelswithall144validresponses; retainincompleteGemma3 12B recordsandreport11valid,35invalid,98rate-limitedcalls.",
        "uncertainty":"Repeated-prompt variation only; no respondent-level confidence intervals, p-values, or out-of-sample estimates."}
    (out/"paper_numbers.json").write_text(json.dumps(numbers,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:numbers[k] for k in ("n_personas_common_panel","completed_calls","valid_calls","accounted_cost_usd","models_beating_overall_baseline")},indent=2))
    for m in model_scores:
        print(f"{m['model_label']:20s} {m['arm']:24s} MAE {m['mae']:.2f} pp")


if __name__ == "__main__":
    main()
