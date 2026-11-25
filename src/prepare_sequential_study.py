"""Prepare a public prompt library and a PRIVATE local-scoring configuration.

No model is called here. FMG targets, volumes, weights and baseline never enter
the prompt builder. The six generic profiles implement the author's previously
specified purpose x flight-region question. The source workbook remains private.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from run_experiment import make_prompt, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
FMG_MODES = ["car_dropoff", "car_airport_parking", "car_offairport_parking",
             "car_other_parking", "taxi_ridehail", "rental_carsharing",
             "bus_transfer", "s_bahn", "uefex", "other"]
FMG_DESCRIPTIONS = {
    "car_dropoff": "A private car brings the passenger and leaves; the driver may stop or park briefly.",
    "car_airport_parking": "A private car is left in airport parking for the passenger's trip.",
    "car_offairport_parking": "A private car is left at an off-airport parking provider with a transfer to the terminal.",
    "car_other_parking": "A private car is left at another parking location not covered by the two parking options above.",
    "taxi_ridehail": "Taxi or app-booked ride-hailing.",
    "rental_carsharing": "A rental car or car-sharing vehicle.",
    "bus_transfer": "Public bus, coach, airport transfer or hotel shuttle, excluding transfers already counted as part of a parking option.",
    "s_bahn": "Munich suburban rail (S-Bahn S1 or S8).",
    "uefex": "The direct regional airport train serving Landshut and Regensburg (UEFEX).",
    "other": "Any remaining access option."
}


def fmg_profile(purpose=None, flight_type=None):
    if purpose is None:
        return "No trip-purpose or flight-region characteristic is supplied. All other passenger characteristics are unspecified."
    descriptions = {
        "Domestic": "a domestic flight within Germany",
        "Continental": "a continental international flight within Europe",
        "Intercontinental": "an intercontinental flight beyond Europe"
    }
    return (f"The passenger travels for {'business' if purpose == 'Business' else 'a private purpose (for example a holiday or visiting friends or relatives)'}. "
            f"The flight departing Munich is {descriptions[flight_type]}. "
            "Age, income, household cars, residence, starting location, trip duration, luggage and travel party are unspecified. "
            "Do not invent a specific value for any of these characteristics.")


def fmg_prompt(profile):
    # This function accepts only a generic description, never a source record.
    modes = "\n".join(f"- {key}: {value}" for key, value in FMG_DESCRIPTIONS.items())
    return (
        "You are participating in a travel-behaviour research benchmark. Estimate group-level airport-access choices. "
        "Do not browse or look up a survey table.\n\n"
        "Population: passengers who reach Munich Airport (MUC), Germany, by ground transport to start a departing flight in calendar year 2025. "
        "Exclude passengers who only change aircraft at Munich without a ground-access trip. "
        "Do not predict how arriving passengers leave the airport, and do not predict ground travel at the other end of the flight.\n\n"
        f"Group description: {profile}\n\n"
        "Task: out of similar passengers in this group, estimate the share in each of the following mutually exclusive access categories. "
        "The flight region describes the flight departing Munich, not necessarily the final destination of a connecting itinerary. "
        "Predict the reported airport-access category, not every vehicle used along the way. "
        "A rail journey followed by S-Bahn to the airport belongs to S-Bahn. "
        "For the specified parking options, a terminal shuttle included in parking is part of that parking category; do not count it again as bus.\n"
        f"{modes}\n\n"
        "Give one complete distribution: the ten probabilities must add to 1. "
        "No observed airport percentages or passenger counts are supplied.\n\n"
        "Return only one JSON object with exactly these keys: " + ", ".join(FMG_MODES) + ", rationale. "
        "The ten mode values must be numbers from 0 to 1 (not percentages). "
        "rationale must be at most 40 words and state a plausible hypothesis, not claim to know passengers' actual motives."
    )


def build(fmg_targets):
    original = read_json(ROOT / "config/experiment.json")
    personas = read_json(ROOT / "data/processed/personas.json")
    baseline = read_json(ROOT / "data/processed/overall_baseline.json")
    baseline = baseline.get("observed", baseline)
    feature_bases = defaultdict(float)
    for p in personas:
        feature_bases[p["feature"]] += p["weighted_base"]
    cards = [{"card_id":p["persona_id"], "feature":p["feature"],
              "description":p["description_en"], "label":p["category_label"],
              "weight":p["weighted_base"]/feature_bases[p["feature"]]/len(feature_bases),
              "observed":p["observed"]} for p in personas]
    mid = {"panel_id":"mid_2023", "modes":["car","local_pt","long_distance_rail"],
           "arms":original["arms"], "mutually_exclusive":False,
           "baseline":baseline, "cards":cards,
           "prompts":{arm:{**{p["persona_id"]:make_prompt(p,arm,baseline) for p in personas},
                           "no_persona":make_prompt({},arm,baseline)} for arm in original["arms"]}}
    fmg_cards = []
    for p in fmg_targets["by_purpose_and_flight_type_from_30"]:
        card_id = "fmg_" + p["purpose"].lower() + "_" + p["flight_type"].lower()
        fmg_cards.append({"card_id":card_id,"feature":"purpose_x_flight_region",
                          "label":p["purpose"]+" / "+p["flight_type"],
                          "description":fmg_profile(p["purpose"],p["flight_type"]),
                          "weight":p["passenger_volume"]/fmg_targets["overall_from_30"]["passenger_volume"],
                          "observed":p["observed"]})
    fmg = {"panel_id":"fmg_2025", "modes":FMG_MODES,"arms":["unanchored"],
           "mutually_exclusive":True,"baseline":fmg_targets["overall_from_30"]["observed"],
           "cards":fmg_cards, "prompts":{"unanchored":{
               **{p["card_id"]:fmg_prompt(p["description"]) for p in fmg_cards},
               "no_persona":fmg_prompt(fmg_profile())}}}
    config = {"version":"2.0", "study_date":"2026-11-25",
        "endpoint":original["endpoint"],
        "models":[{**m,"provider_only":[{
            "google/gemma-3-4b-it":"parasail/bf16",
            "openai/gpt-4.1-mini":"openai",
            "qwen/qwen3-235b-a22b-2507":"deepinfra/fp8",
            "openai/gpt-4.1":"openai"}[m["id"]]]}
            for m in original["models"] if m["id"] != "google/gemma-3-12b-it"],
        "panels":[mid,fmg], "temperature":0.7,"max_tokens":450,
        "seed_base":25112026,"shuffle_seed":25112026,
        "looks":[16,32,64],"endpoint_count":12,
        "primary_family_alpha":0.04,"secondary_alpha_per_endpoint":0.01/12,
        "precision_half_width_pp":0.25,"practical_margin_pp":0.5,
        "iid_assumption_acknowledged":True,
        "max_cost_usd":10.0,"max_runtime_seconds":7200,"max_workers":8,
        "transport_attempts":3,"request_timeout_seconds":100,
        "failure_policy":"halt affected model/panel/arm block at first unresolved incomplete round; no skipped rounds",
        "catalogue_path":str(ROOT / "config/openrouter_catalogue_20261125.json"),
        "provider_policy":"pin a specific provider endpoint; no fallback; require parameters; record provider/model; halt and withhold inference on within-block identity drift",
        "fmg_external_processing":"Only generic study questions. No FMG target, numerical baseline, volume, weight, raw row or workbook is sent.",
        "fmg_publication":"User confirmed FMG permits publishing derived results only on 2026-11-25. Raw source and row extracts remain private.",
        "fmg_target_caveat":"Co-author English summary; original question, boundary-country classification, parking/shuttle coding and interview sample sizes unverified.",
        "public_access_context_sources":[
            "https://www.munich-airport.com/transport-directions-260334",
            "https://www.munich-airport.com/public-transport-260822",
            "https://www.munich-airport.com/car-sharing-at-the-airport-799743",
            "https://www.munich-airport.com/frequently-asked-questions-376207"]}
    return config


def public_library(config):
    return {"description":"Exact planned prompt text. FMG records/weights/targets omitted; MiD overall hints are public.",
            "panels":[{k:p[k] for k in ("panel_id","modes","arms","mutually_exclusive","prompts")} for p in config["panels"]]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fmg-targets",required=True)
    parser.add_argument("--private-output",required=True)
    parser.add_argument("--public-prompts",required=True)
    args=parser.parse_args()
    private_output=Path(args.private_output).resolve()
    if private_output.is_relative_to(ROOT):
        raise ValueError("Private scoring configuration must be outside the public repository")
    config=build(read_json(args.fmg_targets))
    config["source_hashes"]={
        "private_fmg_derived_targets_sha256":hashlib.sha256(Path(args.fmg_targets).read_bytes()).hexdigest(),
        "mid_personas_sha256":hashlib.sha256((ROOT/"data/processed/personas.json").read_bytes()).hexdigest()}
    for panel in config["panels"]:
        assert abs(sum(c["weight"] for c in panel["cards"])-1)<1e-10
    write_json(private_output,config)
    write_json(args.public_prompts,public_library(config))
    print(json.dumps({"private_config":str(private_output),"panels":[{"id":p["panel_id"],"cards":len(p["cards"]),"arms":len(p["arms"])} for p in config["panels"]],"primary_endpoints":12}))


if __name__ == "__main__":
    main()
