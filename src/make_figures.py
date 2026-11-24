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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
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


def framework():
    fig, ax = plt.subplots(figsize=(7.2, 4.45))
    fig.subplots_adjust(left=.015, right=.985, bottom=.025, top=.985)
    ax.set_axis_off()
    text(ax, .012, .993, "From public evidence to a measured persona benchmark", 12, "bold")
    text(ax, .012, .94, "Aircraft-containing overnight journeys reported in MiD 2023", 8.4, color=MUTED)

    xs, width, bottom, height = [.012, .354, .696], .292, .435, .435
    titles = ["PUBLIC EVIDENCE", "DATA-DRIVEN PERSONAS", "LLM PROBABILITIES"]
    cols = [BLUE, TEAL, PURPLE]
    for i, (x, title, col) in enumerate(zip(xs, titles, cols), 1):
        box(ax, x, bottom, width, height, face="white")
        box(ax, x, .79, width, .08, face=col, edge=col)
        text(ax, x+.015, .828, f"{i:02d}  {title}", 8.1, "bold", "white", va="center")
    arrow(ax, (.309, .655), (.348, .655))
    arrow(ax, (.651, .655), (.69, .655))

    text(ax, .028, .765, "Archive raw responses", 8.1, "bold")
    text(ax, .028, .716, "Record query, source and hash", 7.8, color=MUTED)
    # Schematic table: text labels only, never invented prevalence values.
    box(ax, .029, .555, .258, .115, face=PALE, edge=GRID, radius=.008)
    for j, label in enumerate(["Cohort | mode | weighted share", "Unweighted support | coverage"]):
        text(ax, .041, .644-j*.043, label, 6.9, color=MUTED)
    text(ax, .028, .528, "Compute conditional mode rates", 7.6, "bold")
    text(ax, .028, .485, "Car  /  local PT  /  long-distance rail", 6.95, color=MUTED)

    text(ax, .37, .765, "Rank cohort heterogeneity", 8.1, "bold")
    text(ax, .37, .715, "2 traveller + 2 journey features", 7.7, color=MUTED)
    text(ax, .37, .66, "Retain adequately supported strata", 7.5)
    box(ax, .371, .548, .258, .073, face="#EAF5F1", edge="#BCDCD1", radius=.008)
    text(ax, .5, .584, "ONE ATTRIBUTE PER PERSONA", 7.2, "bold", TEAL, ha="center", va="center")
    text(ax, .37, .527, "No invented combinations of attributes", 7.0, color=MUTED)
    text(ax, .37, .481, "Withhold cohort rates from prompts", 6.9, color=MUTED)

    text(ax, .712, .765, "Three co-use probabilities", 8.1, "bold")
    text(ax, .712, .716, "Small + large LLMs / OpenRouter", 7.1, color=MUTED)
    for y, title, desc in [(.61, "Unanchored", "Persona + task definition"),
                           (.505, "Overall-rate anchored", "Same task + national mode rates")]:
        box(ax, .713, y, .258, .084, face="#F5F0F7", edge="#DDCCE3", radius=.008)
        text(ax, .725, y+.066, title, 7.4, "bold", PURPLE)
        text(ax, .725, y+.032, desc, 6.7, color=MUTED)
    text(ax, .841, .474, "3 repeats per model and condition", 7, ha="center", color=MUTED)

    # Both evidence and generated outputs enter the same quantitative evaluation.
    arrow(ax, (.158, .43), (.158, .295), color=BLUE)
    arrow(ax, (.842, .43), (.842, .295), color=PURPLE)
    text(ax, .175, .37, "Observed weighted rates", 7.2, color=BLUE, va="center")
    text(ax, .825, .37, "Predicted probabilities", 7.2, color=PURPLE, ha="right", va="center")
    box(ax, .012, .08, .976, .21, face=PALE, edge=GRID)
    text(ax, .031, .258, "04  QUANTITATIVE VALIDATION", 8.2, "bold")
    text(ax, .031, .207, "Compare persona predictions\nwith a cohort-blind national baseline", 7.7, linespacing=1.45)
    ax.plot([.495, .495], [.115, .225], color=GRID, lw=.8, transform=ax.transAxes)
    text(ax, .525, .207, "Absolute error  /  calibration  /  repeat variation\nAgreement with published cohort marginals", 7.7, linespacing=1.45)
    text(ax, .5, .037, "Scope: aggregate validation; no individual reconstruction or identification of airport-access legs.",
         7.1, color=MUTED, ha="center", va="center")
    save(fig, "01_framework", "Study design. Public MiD 2023 aggregate evidence; no synthetic results plotted.")


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
    fig.text(.025, .98, "Data-driven cohort selection and observed heterogeneity", fontsize=11.5,
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
    save(fig, "02_persona_selection", "Observed public MiD 2023 conditional rates and fixed feature-selection scores; "
         f"sources: {share_path.name}, {selection_path.name}. Not individual or airport-access records.")


def results_figure(calibration_model="openai/gpt-4.1"):
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
    fig.text(.025, .98, "How closely do model probabilities match the data?", fontsize=11.5,
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
    save(fig, "03_model_results", f"Evaluated model outputs from {metrics_path.name} and {summary_path.name}; "
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
        elif args.only == "cohorts":
            raise FileNotFoundError("Public cohort inputs have not been prepared.")
        else:
            print("Skipped cohort figure: no processed public-data input yet.")
    if args.only in {"results", "all"}:
        if (ROOT / "results" / "processed" / "model_metrics.csv").exists():
            results_figure(args.calibration_model)
        elif args.only == "results":
            raise FileNotFoundError("Evaluated model outputs have not been prepared.")
        else:
            print("Skipped results figure: quantitative outputs not yet available.")


if __name__ == "__main__":
    main()
