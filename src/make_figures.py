"""Publication figures from public MiD aggregates and saved model outputs.

Reproduction dependencies: matplotlib==3.11.2, numpy>=1.25 (tested 2.5.5).
Run from any directory: python src/make_figures.py --only framework
The script never calls an API, infers individual records, or fills missing results.
All PDF/SVG plots are vector; 300 dpi PNGs support inspection and reuse.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import textwrap

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, Circle, Polygon, Arc
from matplotlib.transforms import Affine2D
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter, MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
DATA = ROOT / "data" / "processed"
INK = "#183142"
MUTED = "#566A77"
BLUE = "#0072B2"
TEAL = "#008D80"
ORANGE = "#D55E00"
PURPLE = "#8F5B9F"
GRID = "#DCE4E8"
PALE = "#F3F7F9"
MODE_NAMES = {"car": "Car", "local_pt": "Local public\ntransport", "long_distance_rail": "Long-distance\nrail"}
MODE_COLOURS = {"car": BLUE, "local_pt": ORANGE, "long_distance_rail": TEAL}


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8,
        "axes.titlesize": 9, "axes.titleweight": "bold",
        "axes.labelsize": 8, "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": GRID, "axes.spines.top": False,
        "axes.spines.right": False, "axes.linewidth": .6,
        "xtick.labelsize": 7.2, "ytick.labelsize": 7.2,
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "svg.fonttype": "none", "svg.hashsalt": "mid2023-air-cohorts-v1",
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def save(fig, name, provenance):
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = {"Title": name.replace("_", " "), "Author": "Air-passenger LLM-PDM study",
                "Subject": provenance, "CreationDate": None, "ModDate": None}
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=.04, metadata=metadata)
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=.04,
                metadata={"Title": metadata["Title"], "Description": provenance, "Date": None})
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", pad_inches=.04, dpi=300)
    manifest_path = OUT / "figure_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest[name] = {
        "canvas_inches": list(fig.get_size_inches()), "provenance": provenance,
        "formats": {ext: {"file": f"{name}.{ext}",
                           "sha256": hashlib.sha256((OUT / f"{name}.{ext}").read_bytes()).hexdigest()}
                    for ext in ["pdf", "svg", "png"]},
        "matplotlib_version": matplotlib.__version__, "png_dpi": 300,
        "pdf_svg_vector": True,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    plt.close(fig)
    print(f"Wrote {name}: PDF, SVG, PNG")


def text(ax, x, y, s, size=8, weight="normal", color=INK, ha="left", va="top", **kwargs):
    return ax.text(x, y, s, transform=ax.transAxes, fontsize=size, weight=weight,
                   color=color, ha=ha, va=va, **kwargs)


def box(ax, x, y, w, h, face="white", edge=GRID, radius=.018, lw=.8):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                      transform=ax.transAxes, facecolor=face, edgecolor=edge,
                      linewidth=lw, clip_on=False)
    ax.add_patch(p)
    return p


def arrow(ax, start, end, color=MUTED, lw=1.2, style="-|>", **kwargs):
    p = FancyArrowPatch(start, end, transform=ax.transAxes, arrowstyle=style,
                        mutation_scale=9, color=color, lw=lw, clip_on=False, **kwargs)
    ax.add_patch(p)


def icon(ax, kind, cx, cy, size=.07, color=BLUE):
    """Small, original line icons in native vector coordinates."""
    sy = size * ax.figure.get_figwidth() / ax.figure.get_figheight()
    trans = Affine2D().scale(size, sy).translate(cx-size/2, cy-sy/2) + ax.transAxes
    def patch(p):
        p.set_transform(trans)
        p.set_edgecolor(color)
        p.set_linewidth(1.7)
        p.set_clip_on(False)
        ax.add_patch(p)
    def line(xs, ys, lw=1.7):
        ax.plot(xs, ys, transform=trans, color=color, lw=lw, solid_capstyle="round", clip_on=False)
    def rect(x, y, w, h, r=.06):
        patch(FancyBboxPatch((x,y),w,h,boxstyle=f"round,pad=0,rounding_size={r}",facecolor="white"))
    def circ(x,y,r,fill=False):
        patch(Circle((x,y),r,facecolor=color if fill else "white"))
    if kind == "plane":
        patch(Polygon([[.47,.04],[.55,.04],[.59,.27],[.83,.17],[.87,.25],
                       [.59,.44],[.58,.68],[.95,.53],[.98,.64],[.57,.88],
                       [.54,.99],[.47,.99],[.44,.88],[.03,.64],[.06,.53],
                       [.43,.68],[.43,.44],[.15,.25],[.19,.17],[.44,.27]],
                      closed=True,facecolor=color))
    elif kind == "card":
        rect(.06,.13,.88,.72)
        line([.22,.78],[.68,.68])
        line([.52,.78],[.48,.48])
        line([.52,.78],[.30,.30])
        ax.text(.30,.38,"1",transform=trans,ha="center",va="center",weight="bold",fontsize=20,color=color)
    elif kind == "robot":
        rect(.12,.17,.76,.61,.12)
        line([.5,.5],[.78,.93]); circ(.5,.96,.045,True)
        circ(.32,.54,.055,True); circ(.68,.54,.055,True)
        line([.33,.67],[.33,.33]); line([.02,.1],[.44,.44]); line([.9,.98],[.44,.44])
    elif kind == "compare":
        rect(.08,.06,.7,.87)
        for x,h in [(.22,.25),(.39,.46),(.56,.34)]:
            patch(Rectangle((x,.22),.09,h,facecolor=color))
        circ(.78,.30,.20); line([.92,1.08],[.15,-.02])
    elif kind == "lock":
        patch(Arc((.5,.6),.52,.65,theta1=0,theta2=180))
        rect(.16,.04,.68,.56); circ(.5,.36,.04,True); line([.5,.5],[.33,.22])
    elif kind == "car":
        patch(Polygon([[.14,.36],[.26,.66],[.71,.66],[.86,.36]],facecolor="white",closed=True))
        rect(.06,.22,.89,.22,.04)
        circ(.25,.21,.1); circ(.76,.21,.1)
        line([.48,.48],[.44,.64])
    elif kind == "bus":
        rect(.08,.19,.84,.61,.07)
        for x in [.19,.40,.61]: rect(x,.49,.15,.20,.015)
        circ(.27,.19,.09); circ(.74,.19,.09)
    elif kind == "train":
        rect(.10,.25,.80,.43,.05)
        for x in [.21,.43,.65]: rect(x,.44,.13,.15,.01)
        for x in [.25,.75]: circ(x,.24,.07)
        line([.05,.96],[.11,.11]); line([.23,.15],[.13,.03]); line([.76,.84],[.13,.03])
    elif kind == "area":
        for x,y,w,h in [(.05,.1,.23,.47),(.35,.1,.27,.79),(.69,.1,.24,.59)]:
            rect(x,y,w,h,.01)
            for yy in np.arange(y+.13,y+h-.05,.19): line([x+.07,x+w-.07],[yy,yy],1.3)
    elif kind == "companions":
        for x,y in [(.28,.70),(.72,.62)]:
            circ(x,y,.11)
            patch(Arc((x,y-.35),.38,.42,theta1=0,theta2=180))
            line([x-.19,x-.19],[y-.35,y-.53]); line([x+.19,x+.19],[y-.35,y-.53])
    elif kind == "nights":
        line([.08,.08],[.12,.63]); line([.08,.92],[.24,.24]); line([.92,.92],[.12,.48])
        rect(.15,.28,.76,.20,.03); circ(.25,.53,.10)
        patch(Arc((.74,.79),.28,.28,theta1=65,theta2=330))
        line([.80,.86],[.91,.87])
    else:
        raise ValueError(kind)


def worked_example():
    rows = read_csv(ROOT / "results" / "processed" / "prediction_summary.csv")
    example = [r for r in rows if r["model_id"] == "openai/gpt-4.1"
               and r["arm"] == "overall_rate_anchored" and r["feature"] == "anzauto_gr1"
               and r["category_label"] == "No car"]
    if len(example) != 3:
        raise ValueError("Expected one no-car worked example with three modes.")
    return {r["mode_id"]: r for r in example}


def framework():
    fig, ax = plt.subplots(figsize=(7.2, 5.15))
    fig.subplots_adjust(left=.015, right=.985, bottom=.02, top=.985)
    ax.set_axis_off()
    text(ax,.015,.99,"The study, in four steps",15,"bold")
    text(ax,.015,.93,"Can AI guess which other transport people use when they fly?",10,color=MUTED)

    xs = [.015,.265,.515,.765]
    labels = ["Real survey trips","ONE group clue","Ask the AI","Check the answers"]
    details = ["9,475 air trips\nwith nights away","e.g. no car\nin the household","Out of 100 trips,\nhow many used each?","AI guesses beside\nthe survey answers"]
    colours = [BLUE,TEAL,PURPLE,ORANGE]
    for i,(x,label,detail,col,kind) in enumerate(zip(xs,labels,details,colours,["plane","card","robot","compare"]),1):
        box(ax,x,.575,.22,.295,face=PALE,edge=GRID)
        text(ax,x+.015,.851,str(i),9,"bold",col)
        icon(ax,kind,x+.11,.785,.066,col)
        text(ax,x+.11,.707,label,9.5,"bold",ha="center")
        text(ax,x+.11,.661,detail,9,color=MUTED,ha="center",linespacing=1.35)
    for x in [.242,.492,.742]: arrow(ax,(x,.74),(x+.019,.74),lw=1.4)

    icon(ax,"lock",.042,.505,.035,MUTED)
    text(ax,.075,.527,"The group's real answers\nare hidden from the AI.",9,color=MUTED,linespacing=1.3)
    text(ax,.525,.527,"Try with and without a hint:\noverall survey numbers.",9,color=MUTED,linespacing=1.3)
    ax.plot([.015,.985],[.445,.445],transform=ax.transAxes,lw=.8,color=GRID)

    example = worked_example()
    r0 = next(iter(example.values()))
    text(ax,.015,.417,f"One example: households with no car ({int(float(r0['unweighted_n'])):,} surveyed journeys)",10,"bold")
    text(ax,.015,.374,"GPT-4.1 with the overall hint · mean of 3 runs · rates shown out of 100",8.6,color=MUTED)
    cards = [("car","Car","car"),("local_pt","Local bus or train","bus"),
             ("long_distance_rail","Long-distance train","train")]
    audit = {"description":"No-household-car cohort; GPT-4.1, overall-rate anchored, mean of three repeats.",
             "source":"results/processed/prediction_summary.csv","display":"Probability multiplied by 100; one decimal; no 100-person sample.","values":[]}
    for x,(mode,label,kind) in zip([.015,.345,.675],cards):
        box(ax,x,.115,.31,.21,face="white",edge=GRID)
        icon(ax,kind,x+.038,.285,.045,MUTED)
        text(ax,x+.075,.297,label,9,"bold")
        row = example[mode]
        ai,real = float(row["predicted_mean"])*100,float(row["observed_share"])*100
        text(ax,x+.082,.239,f"{ai:.1f}",19,"bold",PURPLE,ha="center")
        text(ax,x+.231,.239,f"{real:.1f}",19,"bold",BLUE,ha="center")
        text(ax,x+.082,.159,"AI guess",8.4,color=PURPLE,ha="center")
        text(ax,x+.231,.159,"Survey answer",8.4,color=BLUE,ha="center")
        audit["values"].append({"mode_id":mode,"predicted_mean":float(row["predicted_mean"]),
                                 "observed_share":float(row["observed_share"]),
                                 "unweighted_n":int(float(row["unweighted_n"])),"n_repeats":int(row["n_repeats"])})
    text(ax,.015,.082,"A journey can use several modes. The three rates need not add up to 100.",8.5,color=MUTED)
    text(ax,.015,.040,"AI returns probabilities (0–1); ×100 only changes the display. No people are simulated; no airport is identified.",7.7,color=MUTED)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"worked_example_values.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    save(fig,"01_framework","Four-step study explanation and an observed GPT-4.1 anchored example, read from canonical prediction_summary.csv; all group rates withheld from model prompts.")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def yes(x):
    return str(x).strip().lower() in {"true", "1", "yes"}


def number(x):
    if x is None or x == "":
        return float("nan")
    return float(x)


def cohort_figure():
    rows = read_csv(DATA / "cohort_mode_shares.csv")
    ranking = read_csv(DATA / "feature_selection.csv")
    selected = {r["feature_id"]: r for r in ranking if yes(r["selected"])}
    features = ["anzauto_gr1","RegioStaR7","anzbegl_gr","anzueb_gr"]
    if set(selected) != set(features):
        raise ValueError("The simplified figure requires the frozen four-feature design.")
    counts = [int(float(selected[f]["eligible_strata"])) for f in features]
    fig, ax = plt.subplots(figsize=(7.2,5.45))
    fig.subplots_adjust(left=.015,right=.985,bottom=.02,top=.985)
    ax.set_axis_off()
    text(ax,.015,.99,f"Four clues make {sum(counts)} groups",15,"bold")
    text(ax,.015,.934,"Each group uses ONE clue. A journey can belong to more than one group.",9.8,color=MUTED)
    text(ax,.255,.872,"2 traveller clues",9.4,"bold",TEAL,ha="center")
    text(ax,.755,.872,"2 journey clues",9.4,"bold",PURPLE,ha="center")
    labels = ["Cars at home","Home area","People from the same\nhome coming along","Nights away"]
    kinds = ["car","area","companions","nights"]
    for x,label,kind,count,col in zip([.015,.265,.515,.765],labels,kinds,counts,[TEAL,TEAL,PURPLE,PURPLE]):
        box(ax,x,.530,.22,.303,face=PALE,edge=GRID)
        icon(ax,kind,x+.11,.776,.062,col)
        text(ax,x+.11,.714,label,8.6 if kind == "companions" else 9.2,"bold",ha="center",linespacing=1.12)
        text(ax,x+.11,.624,str(count),22,"bold",col,ha="center")
        text(ax,x+.11,.569,"groups",8.7,color=MUTED,ha="center")
    text(ax,.015,.502,f"{len(ranking)} clues checked → 2 traveller clues + 2 journey clues selected",10,"bold")
    text(ax,.015,.462,"Age ranked 3rd among traveller clues; the design allowed only 2 traveller slots.",8.6,color=MUTED)
    ax.plot([.015,.985],[.422,.422],transform=ax.transAxes,lw=.8,color=GRID)
    text(ax,.015,.397,"Why the clue matters: a survey example",10.5,"bold")
    text(ax,.015,.355,"These groups reported different ways of travelling.",8.6,color=MUTED)
    contrast = []
    for i,(mode,label,kind) in enumerate([("car","Car also used","car"),("local_pt","Local bus or train also used","bus")]):
        x = .015+i*.50
        box(ax,x,.105,.47,.212,face="white",edge=GRID)
        icon(ax,kind,x+.034,.284,.035,MUTED)
        text(ax,x+.064,.298,label,9,"bold")
        for y,category,short in [(.224,"No car","No car at home"),(.156,"4 or more cars","4+ cars at home")]:
            row = next(r for r in rows if r["feature_id"] == "anzauto_gr1" and r["mode_id"] == mode and r["stratum_label_en"] == category)
            share = float(row["observed_share"])
            text(ax,x+.015,y,short,8.7,va="center")
            ax.add_patch(Rectangle((x+.205,y-.019),.205*share/.60,.038,transform=ax.transAxes,
                                   facecolor=TEAL,edgecolor="none"))
            text(ax,x+.205+.205*share/.60+.008,y,f"{share:.0%}",10,"bold",TEAL,va="center")
            contrast.append({"mode_id":mode,"category":category,"observed_share":share,
                             "unweighted_n":int(float(row["unweighted_base"]))})
    text(ax,.015,.072,"Rounded weighted survey rates. No-car group: 936 journeys; 4+ car group: 279 journeys.",8.3,color=MUTED)
    text(ax,.015,.033,"Groups overlap; they are not combined into fictional people. A journey may use several modes.",8.3,color=MUTED)
    (OUT/"cohort_example_values.json").write_text(json.dumps({"source":"data/processed/cohort_mode_shares.csv",
        "selected_features":[{"feature_id":f,"groups":n} for f,n in zip(features,counts)],"contrasts":contrast},indent=2)+"\n",encoding="utf-8")
    save(fig,"02_persona_selection","Plain-language overview of the frozen 2-traveller/2-journey feature selection and 23 overlapping single-attribute groups. Rounded survey contrasts read from cohort_mode_shares.csv; complete profiles in S01_technical_cohort_profiles.")


def results_figure(calibration_model="openai/gpt-4.1"):
    metrics = read_csv(ROOT / "results" / "processed" / "model_metrics.csv")
    config = json.loads((ROOT/"config"/"experiment.json").read_text(encoding="utf-8-sig"))
    numbers = json.loads((ROOT/"results"/"processed"/"paper_numbers.json").read_text(encoding="utf-8-sig"))
    active = set(numbers["active_model_ids"])
    models = [m for m in config["models"] if m["id"] in active]
    lookup = {(r["model_id"],r["arm"]):r for r in metrics}
    baseline = float(lookup[("overall_baseline","baseline")]["mae"])
    fig = plt.figure(figsize=(7.2,5.15))
    fig.text(.025,.98,"Which AI gets closest to the survey?",fontsize=15,weight="bold",va="top",color=INK)
    fig.text(.025,.916,"Smaller gaps are better. Giving the overall rates helps all four models.",fontsize=9.8,va="top",color=MUTED)
    handles = [Rectangle((0,0),1,1,facecolor=ORANGE,label="No overall hint"),
               Rectangle((0,0),1,1,facecolor=BLUE,label="With overall hint")]
    fig.legend(handles=handles,loc="upper left",bbox_to_anchor=(.53,.877),ncol=2,
               frameon=False,fontsize=9.5,handlelength=1.25,columnspacing=1.5)
    ax = fig.add_axes([.27,.315,.69,.49])
    ypos = np.arange(len(models))*1.4
    plot_values=[]
    for model,y in zip(models,ypos):
        for arm,offset,col in [("unanchored",-.19,ORANGE),("overall_rate_anchored",.19,BLUE)]:
            val = float(lookup[(model["id"],arm)]["mae"])
            ax.barh(y+offset,val,height=.30,color=col,zorder=3)
            ax.text(val+.27,y+offset,f"{val:.2f}",fontsize=9,color=col,weight="bold",va="center",
                    bbox=dict(facecolor="white",edgecolor="none",pad=.5),zorder=5)
            plot_values.append({"model_id":model["id"],"arm":arm,"mae_pp":val})
    ax.axvline(baseline,color=MUTED,ls=(0,(3,3)),lw=1.15,zorder=2)
    ax.text(baseline,-.65,f"Same guess for each group:\n{baseline:.2f}",fontsize=8.3,color=MUTED,ha="center",va="bottom",
            bbox=dict(facecolor="white",edgecolor="none",pad=1))
    ax.set_xlim(0,max(v["mae_pp"] for v in plot_values)+3.1)
    ax.set_ylim(ypos[-1]+.58,-.87)
    ax.set_yticks(ypos)
    display_labels = {"google/gemma-3-4b-it:free":"Gemma 3 4B","openai/gpt-4.1-mini":"GPT-4.1 mini",
                      "qwen/qwen3-235b-a22b":"Qwen3 235B A22B","openai/gpt-4.1":"GPT-4.1"}
    ax.set_yticklabels([display_labels.get(m["id"],m["label"]) for m in models],fontsize=9.5,weight="bold")
    ax.tick_params(axis="y",length=0,pad=8)
    ax.tick_params(axis="x",labelsize=8.5)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x",color=GRID,lw=.6,zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("Average gap from the survey (percentage points)",fontsize=9.5,labelpad=6)
    ax.xaxis.set_major_locator(MaxNLocator(6))
    # The no-persona control keeps the task and overall-rate hint but removes the group clue.
    full = float(lookup[("openai/gpt-4.1","overall_rate_anchored")]["mae"])
    control = float(lookup[("openai/gpt-4.1::no_persona","overall_rate_anchored")]["mae"])
    note = fig.add_axes([.025,.101,.95,.13]); note.set_axis_off()
    box(note,0,0,1,1,face=PALE,edge=GRID,radius=.07)
    text(note,.02,.78,"Does the group clue help?",9.2,"bold")
    text(note,.02,.36,"GPT-4.1 with the overall hint",8.3,color=MUTED)
    text(note,.55,.78,f"{control:.2f} → {full:.2f}",16,"bold",BLUE,ha="center")
    text(note,.55,.28,"Without clue → with clue",8.3,color=MUTED,ha="center")
    text(note,.83,.72,"Lowest error:\nGPT-4.1 + hint",8.6,"bold",ha="center",linespacing=1.35)
    fig.text(.025,.069,f"Baseline: use the overall survey rates for every group (gap {baseline:.2f}). Mean of 3 runs; 23 overlapping groups.",fontsize=7.8,color=MUTED,va="top")
    fig.text(.025,.031,"Gemma 3 12B was incomplete (11/144 valid calls) and excluded. Detailed checks appear in the supplement.",fontsize=7.8,color=MUTED,va="top")
    (OUT/"model_comparison_values.json").write_text(json.dumps({"source":"results/processed/model_metrics.csv",
        "baseline_mae_pp":baseline,"values":plot_values,"gpt41_anchored_control_mae_pp":control},indent=2)+"\n",encoding="utf-8")
    save(fig,"03_model_results","Simplified comparison of frozen primary model mean absolute errors (percentage points) and the overall-rate baseline. GPT-4.1 control retains the overall hint but removes the group clue; complete diagnostics in S02_technical_model_diagnostics.")


def technical_cohort_figure():
    share_path, selection_path = DATA / "cohort_mode_shares.csv", DATA / "feature_selection.csv"
    rows, ranking = read_csv(share_path), read_csv(selection_path)
    selected = [r for r in ranking if yes(r.get("selected"))]
    selected.sort(key=lambda r: ({"traveller": 0, "journey": 1}.get(r.get("feature_family", r.get("family", "")), 2),
                                number(r.get("rank", "999"))))
    features = [r["feature_id"] for r in selected]
    cohort_rows = [r for r in rows if yes(r.get("selected")) and r["feature_id"] in features]
    if not cohort_rows:
        raise ValueError("No selected public-data cohort rates; figure not produced.")
    modes = list(MODE_NAMES)
    baseline = {}
    for r in rows:
        if r.get("feature_id") == "__all__" and r["mode_id"] in modes:
            baseline[r["mode_id"]] = number(r["observed_share"])
    if len(baseline) != 3:
        p = DATA / "overall_baseline.json"
        raise ValueError(f"Baseline must be supplied as __all__ rows before plotting (also inspect {p}).")

    positions, entries, headings = [], [], []
    y = 0
    for feature in features:
        feature_rows = [r for r in cohort_rows if r["feature_id"] == feature]
        seen, strata = set(), []
        for row in feature_rows:
            sid = row["stratum_id"]
            if sid not in seen:
                seen.add(sid)
                strata.append(sid)
        headings.append((y, feature_rows[0]["feature_label_en"]))
        y += 1.15
        for sid in strata:
            subset = {r["mode_id"]: r for r in feature_rows if r["stratum_id"] == sid}
            if not all(mode in subset for mode in modes):
                raise ValueError(f"Incomplete cohort {feature}/{sid}")
            r0 = subset[modes[0]]
            label = r0["stratum_label_en"]
            if feature == "RegioStaR7":
                label = label.replace("Urban region - ", "Urban: ").replace("Rural region - ", "Rural: ")
                label = label.replace("medium-sized town, urban area", "medium towns / urban areas")
                label = label.replace("small-town and village area", "small towns / villages")
                label = label.replace("regiopolis and large city", "regiopolis / large city")
            label = textwrap.fill(label, width=39)
            rowh = max(1.12, .8*len(label.splitlines())+.15)
            y += rowh/2
            positions.append(y)
            entries.append((label, [number(subset[m]["observed_share"]) for m in modes],
                            int(number(r0["unweighted_base"]))))
            y += rowh/2
        y += .75
    height = max(5.4, 1.8 + y*.155)
    fig = plt.figure(figsize=(7.2, height))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.15, 4.8], left=.025, right=.99,
                         bottom=.13, top=.86, wspace=.14)
    ax_rank, ax_heat = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    fig.text(.025, .98, "Technical appendix: observed cohort profiles", fontsize=11.5,
             weight="bold", va="top", color=INK)
    source_n = int(number(next(r["unweighted_base"] for r in rows if r["feature_id"] == "__all__")))
    fig.text(.025, .94, f"Public MiD 2023 | {source_n:,} aircraft-containing overnight journeys | {len(entries)} overlapping cohorts", fontsize=8,
             va="top", color=MUTED)
    # Ranking remains independent of any LLM output.
    ranking.sort(key=lambda r: number(r.get("rank", "999")))
    vals = [number(r["score_mean_normalized_ig"]) for r in ranking]
    yrank = np.arange(len(ranking))*2
    ax_rank.barh(yrank+.7, vals, height=.52,
                 color=[TEAL if yes(r.get("selected")) else "#C6D3DB" for r in ranking])
    ax_rank.set_yticks([])
    for yy, r in zip(yrank, ranking):
        label = r.get("feature_label_en", r.get("label", r["feature_id"]))
        ax_rank.text(0, yy, label, va="center", fontsize=7.0,
                     weight="bold" if yes(r.get("selected")) else "normal",
                     color=TEAL if yes(r.get("selected")) else INK)
    ax_rank.set_ylim(len(ranking)*2-.45, -1.1)
    ax_rank.set_xlim(0, max(vals)*1.04)
    ax_rank.set_xlabel("Normalised information gain", fontsize=7.1, labelpad=8)
    ax_rank.xaxis.set_major_locator(MaxNLocator(3))
    ax_rank.set_title("A  Rank candidate features", loc="left", pad=15, fontsize=8.6)
    ax_rank.grid(axis="x", color=GRID, lw=.5)
    ax_rank.set_axisbelow(True)
    ax_rank.tick_params(axis="y", length=0)
    ax_rank.spines["left"].set_visible(False)
    ax_rank.legend(handles=[Rectangle((0, 0), 1, 1, color=TEAL, label="Selected"),
                             Rectangle((0, 0), 1, 1, color="#C6D3DB", label="Other candidates")],
                    loc="lower left", bbox_to_anchor=(-.02, -.15), frameon=False, fontsize=6.8)

    ax_heat.set_title("B  Selected cohorts: observed mode use", loc="left", pad=15, fontsize=8.6)
    ax_heat.set_xlim(-3.75, 3.15)
    ax_heat.set_ylim(y-.15, -1.05)
    ax_heat.set_axis_off()
    for j, mode in enumerate(modes):
        mode_label = "Local PT" if mode == "local_pt" else MODE_NAMES[mode]
        ax_heat.text(j+.5, -.95, mode_label, ha="center", va="bottom", fontsize=6.7, weight="bold")
        ax_heat.text(j+.5, -.22, f"All: {baseline[mode]:.1%}", ha="center", va="bottom", fontsize=6.5, color=MUTED)
    cmap = colors.LinearSegmentedColormap.from_list("cohort_difference", ["#D06432", "#F8FAFA", "#087BA9"])
    max_dev = max(abs(v-baseline[m]) for _, values, _ in entries for m, v in zip(modes, values))
    limit = max(.10, math.ceil(max_dev*10)/10)
    norm = colors.TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit)
    for yy, label in headings:
        ax_heat.add_patch(Rectangle((-3.75, yy-.35), 6.8, .8, facecolor=PALE, edgecolor="none"))
        ax_heat.text(-3.65, yy+.05, label, fontsize=7.6, weight="bold", va="center")
    for yy, (label, values, n) in zip(positions, entries):
        ax_heat.text(-3.65, yy, label, fontsize=7.1, va="center", linespacing=1.1)
        for j, (mode, val) in enumerate(zip(modes, values)):
            dev = val-baseline[mode]
            ax_heat.add_patch(Rectangle((j+.035, yy-.42), .93, .84, facecolor=cmap(norm(dev)),
                                       edgecolor="white", lw=.5))
            ax_heat.text(j+.5, yy, f"{val:.0%}", ha="center", va="center", fontsize=7.5,
                         color="white" if abs(dev)>.85*limit else INK)
    cax = fig.add_axes([.59, .078, .35, .012])
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    if cbar.solids is not None:
        cbar.solids.set_rasterized(False)
        cbar.solids.set_edgecolor("face")  # Suppress PDF-viewer seams between vector colour strips.
    cbar.set_ticks([-limit, 0, limit])
    cbar.set_ticklabels([f"{int(-limit*100):+d}", "0", f"{int(limit*100):+d}"])
    cbar.ax.tick_params(labelsize=6.5, length=2)
    cbar.outline.set_visible(False)
    fig.text(.765, .045, "Difference from the overall aircraft-journey rate (pp)", fontsize=6.5,
             ha="center", color=MUTED)
    fig.text(.025, .012, "Observed weighted prevalence; cohorts overlap and modes may co-occur. RegioStaR labels are abbreviated.",
             fontsize=6.6, color=MUTED, va="bottom")
    save(fig, "S01_technical_cohort_profiles", "Technical appendix. Observed public MiD 2023 conditional rates and fixed feature-selection scores; "
         f"sources: {share_path.name}, {selection_path.name}. Not individual or airport-access records.")


def technical_results_figure(calibration_model="openai/gpt-4.1"):
    """Read evaluated means; keep single-run ranges distinct from confidence limits."""
    result_dir = ROOT / "results" / "processed"
    metrics_path = result_dir / "model_metrics.csv"
    summary_path = result_dir / "prediction_summary.csv"
    metrics, predictions = read_csv(metrics_path), read_csv(summary_path)
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8-sig"))
    planned_models = config["models"]
    numbers_path = result_dir / "paper_numbers.json"
    paper_numbers = json.loads(numbers_path.read_text(encoding="utf-8-sig")) if numbers_path.exists() else {}
    active_ids = set(paper_numbers.get("active_model_ids", [m["id"] for m in planned_models]))
    models = [m for m in planned_models if m["id"] in active_ids]
    excluded_models = [m for m in planned_models if m["id"] not in active_ids]
    if not models:
        raise ValueError("No models meet the declared analysis availability criterion.")
    arms = ["unanchored", "overall_rate_anchored"]
    arm_colours = {"unanchored": ORANGE, "overall_rate_anchored": BLUE}
    arm_labels = {"unanchored": "Unanchored", "overall_rate_anchored": "Overall-rate anchored"}
    lookup = {(r["model_id"], r["arm"]): r for r in metrics}
    if not all((m["id"], a) in lookup for m in models for a in arms):
        raise ValueError("The main model metric panel is incomplete; figure not produced.")
    baseline = next(r for r in metrics if r["model_id"] == "overall_baseline")
    baseline_mae = number(baseline["mae"])  # Analysis exports percentage points, not proportions.
    diagnostic = [r for r in predictions if r["model_id"] == calibration_model and r["arm"] in arms]
    if not diagnostic:
        raise ValueError(f"Predesignated calibration model {calibration_model} is missing.")
    diagnostic_label = diagnostic[0]["model_label"]
    fig = plt.figure(figsize=(7.2, 6.25))
    fig.text(.025, .98, "Technical appendix: error and calibration", fontsize=11.5,
             weight="bold", va="top", color=INK)
    fig.text(.025, .94, f"Aggregate error for {len(models)} completed models; calibration shown for predesignated {diagnostic_label}",
             fontsize=7.8, va="top", color=MUTED)
    ax = fig.add_axes([.23, .615, .74, .25])
    fig.text(.025, .885, "A  Error against observed cohort rates", fontsize=8.7, weight="bold")
    ypos = []
    yy, prior = 0.0, None
    for m in models:
        tier = m.get("tier", "")
        if prior is not None and prior != tier:
            yy += .55
        ypos.append(yy)
        yy += 1.0
        prior = tier
    xmax = baseline_mae
    for model, yy in zip(models, ypos):
        for arm, offset in zip(arms, [-.15, .15]):
            row = lookup[(model["id"], arm)]
            val = number(row["mae"])
            lo, hi = number(row.get("repeat_mae_min_pp")), number(row.get("repeat_mae_max_pp"))
            # A mean-probability score can lie below every single-run score.
            # Therefore these are independent line segments, never asymmetric error bars.
            if math.isfinite(lo) and math.isfinite(hi):
                ax.plot([lo, hi], [yy+offset, yy+offset], color=arm_colours[arm], lw=2.7, alpha=.38,
                        solid_capstyle="round", zorder=2)
                xmax = max(xmax, hi)
            ax.scatter([val], [yy+offset], color=arm_colours[arm], edgecolor="white", linewidth=.6,
                       s=30, marker="o" if arm == "unanchored" else "s", zorder=3)
            ax.text(val+.38, yy+offset, f"{val:.1f}", fontsize=6.7, va="center", color=arm_colours[arm])
            xmax = max(xmax, val)
    ax.axvline(baseline_mae, color=MUTED, lw=1.0, ls=(0, (3, 3)), zorder=1)
    ax.set_xlim(0, math.ceil((xmax+3)/5)*5)
    ax.set_ylim(max(ypos)+.6, -.6)
    ax.set_yticks(ypos)
    ax.set_yticklabels([m["label"] for m in models], fontsize=7.6)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=.5)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(MaxNLocator(6))
    ax.set_xlabel("Mean absolute error (percentage points; lower is better)", labelpad=5, fontsize=7.4)
    handles = [Line2D([0], [0], marker="o", color=ORANGE, linestyle="", markersize=4.5, label="Unanchored"),
               Line2D([0], [0], marker="s", color=BLUE, linestyle="", markersize=4.5, label="Overall-rate anchored"),
               Line2D([0], [0], color=MUTED, lw=1, ls="--", label=f"National-rate baseline: {baseline_mae:.1f} pp")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(.99, .916), ncol=3,
               frameon=False, fontsize=6.7, columnspacing=1.15, handletextpad=.5)

    maxprob = max(max(number(r["observed_share"]), number(r["predicted_mean"])) for r in diagnostic)
    limit = min(1.0, max(.6, math.ceil((maxprob+.02)*10)/10))
    marker_by_mode = {"car": "o", "local_pt": "^", "long_distance_rail": "s"}
    for idx, arm in enumerate(arms):
        axc = fig.add_axes([.10+idx*.49, .145, .35, .32])
        axc.plot([0, limit], [0, limit], color=MUTED, ls=(0, (3, 3)), lw=.85, zorder=1)
        for mode in MODE_NAMES:
            group = [r for r in diagnostic if r["arm"] == arm and r["mode_id"] == mode]
            axc.scatter([number(r["observed_share"]) for r in group],
                        [number(r["predicted_mean"]) for r in group],
                        color=MODE_COLOURS[mode], marker=marker_by_mode[mode], s=22,
                        edgecolors="white", linewidths=.35, alpha=.85, zorder=3)
        axc.set_xlim(0, limit)
        axc.set_ylim(0, limit)
        axc.set_aspect("equal", adjustable="box")
        axc.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axc.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axc.xaxis.set_major_locator(MaxNLocator(4))
        axc.yaxis.set_major_locator(MaxNLocator(4))
        axc.grid(color=GRID, lw=.5, zorder=0)
        axc.set_axisbelow(True)
        axc.set_xlabel("Observed weighted prevalence", fontsize=7.2)
        axc.set_ylabel("Mean predicted probability", fontsize=7.2)
        axc.set_title(f"{'B' if idx == 0 else 'C'}  {diagnostic_label}: {arm_labels[arm].lower()}",
                      loc="left", fontsize=8.0, pad=8)
    mode_handles = [Line2D([0], [0], marker=marker_by_mode[m], color=MODE_COLOURS[m], linestyle="",
                            markersize=4.5, label={"car":"Car", "local_pt":"Local public transport", "long_distance_rail":"Long-distance rail"}[m])
                    for m in MODE_NAMES]
    fig.legend(handles=mode_handles, loc="center", bbox_to_anchor=(.515, .515), ncol=3,
               frameon=False, fontsize=7.1, columnspacing=2)
    if excluded_models:
        counts = {m["id"]: {"valid": 0, "total": 0} for m in excluded_models}
        for path in (ROOT / "results" / "raw").glob("*.json"):
            if path.name.endswith(".request.json"):
                continue
            rec = json.loads(path.read_text(encoding="utf-8-sig"))
            if rec.get("model_id") in counts:
                counts[rec["model_id"]]["total"] += 1
                counts[rec["model_id"]]["valid"] += int(rec.get("status") == "valid")
        excluded_text = "; ".join(f"{m['label']}: {counts[m['id']]['valid']}/{counts[m['id']]['total']} valid calls"
                                  for m in excluded_models)
        fig.text(.025, .063, f"Availability exclusion: {excluded_text}.", fontsize=6.6, color=MUTED)
    fig.text(.025, .04, "Points: error of the three-run mean probability. Segments: range of single-run errors, not confidence intervals.",
             fontsize=6.6, color=MUTED)
    fig.text(.025, .017, "Calibration points represent cohort-mode cells; the dashed diagonal is exact agreement. Cohorts overlap.",
             fontsize=6.6, color=MUTED)
    save(fig, "S02_technical_model_diagnostics", f"Technical appendix. Evaluated model outputs from {metrics_path.name} and {summary_path.name}; "
         f"calibration model fixed before outcomes: {calibration_model}. Main panel excludes no-persona control IDs. "
         f"Active models: {sorted(active_ids)}; availability exclusions: {[m['id'] for m in excluded_models]}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["framework", "cohorts", "results", "all"], default="all")
    parser.add_argument("--calibration-model", default="openai/gpt-4.1",
                        help="Fixed diagnostic model, chosen before viewing outcomes.")
    args = parser.parse_args()
    style()
    if args.only in {"framework", "all"}:
        framework()
    if args.only in {"cohorts", "all"}:
        if (DATA / "cohort_mode_shares.csv").exists():
            cohort_figure()
            technical_cohort_figure()
        elif args.only == "cohorts":
            raise FileNotFoundError("Public cohort inputs have not been prepared.")
        else:
            print("Skipped cohort figure: no processed public-data input yet.")
    if args.only in {"results", "all"}:
        if (ROOT / "results" / "processed" / "model_metrics.csv").exists():
            results_figure(args.calibration_model)
            technical_results_figure(args.calibration_model)
        elif args.only == "results":
            raise FileNotFoundError("Evaluated model outputs have not been prepared.")
        else:
            print("Skipped results figure: quantitative outputs not yet available.")


if __name__ == "__main__":
    main()
