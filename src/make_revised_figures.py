"""Render the revised three-figure paper from saved, locally evaluated results.

Framework only (no quantitative inputs needed):
    python src/make_revised_figures.py --only framework
All figures, after the fresh run has been scored locally:
    python src/make_revised_figures.py --data results/sequential_20261125/figure_data.json

No API calls, guessed values, old-run fallback, or silent category renormalisation.
All outputs use the revised_* prefix; the original release figures are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.ticker import MultipleLocator

from make_figures import icon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figures'
DEFAULT_DATA = ROOT / 'results/sequential_20261125/figure_data.json'
INK = '#1C3343'
MUTED = '#536773'
OBSERVED = '#006FA6'
AI = '#7A4094'
AI_LIGHT = '#B595C8'
GRID = '#DEE6EA'
PALE_BLUE = '#EDF5FA'
PALE_PURPLE = '#F4EFF8'
MID_MODES = {'car': 'Car', 'local_pt': 'Local public transport', 'long_distance_rail': 'Long-distance rail'}
FMG_MODES = ('car_dropoff','car_airport_parking','car_offairport_parking','car_other_parking',
             'taxi_ridehail','rental_carsharing','bus_transfer','s_bahn','uefex','other')
FAMILIES = (
    ('private_car', 'Private car', ('car_dropoff','car_airport_parking','car_offairport_parking','car_other_parking'), '#99BDD2'),
    ('taxi', 'Taxi / ride-hailing', ('taxi_ridehail',), '#F1BE67'),
    ('rental', 'Rental / carsharing', ('rental_carsharing',), '#C4A8D1'),
    ('bus', 'Bus / transfer', ('bus_transfer',), '#80C5B3'),
    ('rail', 'Rail', ('s_bahn','uefex'), '#386F92'),
    ('other', 'Other', ('other',), '#C9CFD4'),
)


def style():
    plt.rcParams.update({
        'font.family':'DejaVu Sans','font.size':8.4,'text.color':INK,
        'axes.labelcolor':INK,'axes.titlesize':9,'axes.titleweight':'bold',
        'axes.edgecolor':GRID,'axes.linewidth':.6,
        'axes.spines.top':False,'axes.spines.right':False,
        'xtick.labelsize':7.5,'ytick.labelsize':8,'xtick.color':MUTED,'ytick.color':MUTED,
        'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
        'svg.hashsalt':'air-passenger-revision-20261125',
        'savefig.facecolor':'white','figure.facecolor':'white',
        'hatch.linewidth':.35,
    })


def save(fig, name: str, values: dict, source: Path | None = None):
    if not name.startswith('revised_'):
        raise ValueError('This script only owns revised_* figure paths.')
    OUT.mkdir(parents=True,exist_ok=True)
    fig.canvas.draw()
    # Final visual inspection remains necessary; this catches text outside the page.
    renderer=fig.canvas.get_renderer()
    bounds=fig.bbox
    outside=[]
    for item in fig.findobj(matplotlib.text.Text):
        if not item.get_visible() or not item.get_text().strip(): continue
        bb=item.get_window_extent(renderer)
        if bb.x0 < bounds.x0-2 or bb.y0 < bounds.y0-2 or bb.x1 > bounds.x1+2 or bb.y1 > bounds.y1+2:
            outside.append(item.get_text())
    if outside:
        raise ValueError(f'Text extends outside figure canvas: {outside}')
    title=name.replace('_',' ')
    fig.savefig(OUT/f'{name}.pdf', metadata={'Title':title,'Author':'Air-passenger LLM-PDM study','CreationDate':None,'ModDate':None})
    fig.savefig(OUT/f'{name}.svg', metadata={'Title':title,'Date':None})
    fig.savefig(OUT/f'{name}.png', dpi=300)
    manifest={
        'figure':name,'canvas_inches':list(fig.get_size_inches()),
        'matplotlib_version':matplotlib.__version__,'png_dpi':300,
        'pdf_svg_vector':True,'text_within_canvas':True,
        'input_file':str(source.relative_to(ROOT)) if source and source.is_relative_to(ROOT) else (str(source) if source else None),
        'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest() if source else None,
        'values':values,
        'files':{ext:{'file':f'{name}.{ext}','sha256':hashlib.sha256((OUT/f'{name}.{ext}').read_bytes()).hexdigest()} for ext in ('pdf','svg','png')},
    }
    (OUT/f'{name}_values.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    plt.close(fig)
    print(f'Wrote {name}: PDF, SVG, PNG and exact-value audit.')


def txt(ax,x,y,label,*,size=8.3,bold=False,color=INK,ha='left',va='top',**kw):
    return ax.text(x,y,label,transform=ax.transAxes,fontsize=size,fontweight='bold' if bold else 'normal',color=color,ha=ha,va=va,**kw)


def box(ax,x,y,width,height,face,edge):
    p=FancyBboxPatch((x,y),width,height,boxstyle='round,pad=0,rounding_size=0.018',transform=ax.transAxes,facecolor=face,edgecolor=edge,lw=.85)
    ax.add_patch(p)


def arrow(ax,a,b,color=MUTED,**kw):
    p=FancyArrowPatch(a,b,transform=ax.transAxes,arrowstyle='-|>',mutation_scale=10,color=color,lw=1.1,clip_on=False,**kw)
    ax.add_patch(p)


def card_icon(ax,cx,cy,number):
    width=.065;height=.07
    box(ax,cx-width/2,cy-height/2,width,height,'white',MUTED)
    txt(ax,cx-.017,cy,str(number),size=12,bold=True,color=MUTED,ha='center',va='center')
    for yy in (cy+.018,cy,cy-.018):
        ax.plot([cx+.004,cx+.025],[yy,yy],transform=ax.transAxes,color=MUTED,lw=1)


def framework():
    fig=plt.figure(figsize=(7.4,5.0))
    ax=fig.add_axes([0,0,1,1]);ax.set_axis_off()
    txt(ax,.03,.966,'Real groups, AI estimates, observed answers',size=13,bold=True)
    txt(ax,.03,.918,'Describe a group. Ask how it travels. Check the estimates against the survey.',size=8.8,color=MUTED)
    xs=[.03,.275,.52,.765];width=.205;height=.205
    for y,letter,title,color in [( .828,'A','Germany: modes used during an air journey',OBSERVED),(.482,'B','Munich: the reported airport-access category',AI)]:
        txt(ax,.03,y,letter,size=11.5,bold=True,color=color)
        txt(ax,.066,y,title,size=10,bold=True)
    for base_y,airport in [(.576,False),(.23,True)]:
        for j,x in enumerate(xs):
            edge=AI if j==2 else OBSERVED if j in (0,3) else GRID
            face=PALE_PURPLE if j==2 else PALE_BLUE if j in (0,3) else '#F7F9FA'
            box(ax,x,base_y,width,height,face,edge)
            if j<3: arrow(ax,(x+width+.004,base_y+height/2),(xs[j+1]-.006,base_y+height/2))
        cy=base_y+.145
        icon(ax,'lock' if airport else 'plane',xs[0]+width/2,cy,size=.044,color=OBSERVED)
        card_icon(ax,xs[1]+width/2,cy,2 if airport else 1)
        icon(ax,'robot',xs[2]+width/2,cy,size=.048,color=AI)
        icon(ax,'compare',xs[3]+width/2,cy,size=.046,color=OBSERVED)
        lines=[
            ('Airport summary','FMG 2025 · private source') if airport else ('Real survey journeys','MiD 2023 · public tables'),
            ('Two clues','Purpose + departing\nflight type') if airport else ('One clue','1 of 4 selected\nattributes'),
            ('Predict access shares','Generic group card only') if airport else ('Predict three shares','Car, local transit,\nlong-distance train'),
            ('Compare locally','Observed shares vs AI') if airport else ('Check the answers','Observed shares vs AI'),
        ]
        for x,(heading,sub) in zip(xs,lines):
            txt(ax,x+width/2,base_y+.09,heading,size=8.6,bold=True,ha='center')
            txt(ax,x+width/2,base_y+(.055 if '\n' in sub else .041),sub,size=7.8,color=MUTED,ha='center',linespacing=1.05)
    txt(ax,.03,.548,'23 groups from 4 selected attributes; 14 attributes screened using information gain.',size=7.7,color=MUTED)
    txt(ax,.03,.523,'Group alone / group + overall hint. Three selected modes can overlap; totals need not be 100%.',size=7.7,color=MUTED)
    # The private observation path bypasses the model and rejoins at local scoring.
    ax.plot([.1325,.1325,.8675],[.23,.166,.166],transform=ax.transAxes,color=OBSERVED,lw=1.1,linestyle=(0,(3,2)),clip_on=False)
    arrow(ax,(.8675,.166),(.8675,.225),color=OBSERVED,linestyle=(0,(3,2)))
    txt(ax,.50,.157,'Airport observations bypass the AI; only generic group cards are sent.',size=8,ha='center',color=OBSERVED)
    txt(ax,.03,.093,'Munich shares describe mutually exclusive reported categories. All ten are scored.',size=8,color=MUTED)
    txt(ax,.03,.055,'The models estimate group shares; we do not create or sample individual passengers.',size=8,color=MUTED)
    save(fig,'revised_01_dual_framework',{
        'type':'conceptual diagram; no observed or simulated numerical results',
        'mid':'Nonexclusive mode co-use within overnight journeys whose recorded main mode is aircraft.',
        'mid_processing':'Four attributes selected from fourteen by normalized information gain with a fixed two-traveller/two-journey allocation; twenty-three single-attribute groups. Compare group-only and group-plus-public-overall-rate-hint arms.',
        'fmg':'Exclusive reported airport-access category for originating departing passengers; six purpose-by-flight-type groups.',
        'privacy':'Only generic group cards go to the model; airport observations, volumes, weights and numerical hints are excluded from requests. Approved six-group derived targets and normalized weights are published separately for offline evaluation; sources and native rows remain private.',
        'interpretation':'Group-share estimates, not sampled synthetic passengers.',
    })


def probability(value,where):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError(f'Expected probability in [0,1] at {where}.')
    return float(value)


def load_data(path):
    if not path.exists():
        raise FileNotFoundError(f'Fresh locally scored figure input is absent: {path}. Use --only framework until the actual run is ready; no previous results are substituted.')
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or not isinstance(data.get('metadata',{}),dict):
        raise ValueError('Expected figure_data.json object with metadata and result lists.')
    return data


def model_label(model,metadata):
    if model in metadata.get('model_labels',{}): return metadata['model_labels'][model]
    if 'gpt-4.1' in model:return 'GPT-4.1'
    if 'gemma' in model.lower():
        for size in ('27b','12b','4b'):
            if re.search(r'(?:^|[-_/])'+size+r'(?:$|[-_/])',model.lower()):
                return 'Gemma 3 '+size.upper()
        return 'Gemma'
    return model.split('/')[-1]


def display_metadata(metadata):
    """Retain study labels, not arbitrary private input-file metadata."""
    allowed=('run_id','created_utc','mid_arm','fmg_arm','mid_prompt_arm','fmg_prompt_arm',
             'mid_models','fmg_model','model_labels','repeats','repeat_count','prediction_aggregation',
             'mid_condition','fmg_condition','prediction_basis')
    return {key:metadata[key] for key in allowed if key in metadata}


def completed_rounds(metadata,panel,model,arm):
    matches=[r for r in metadata.get('block_availability',[]) if
             r.get('panel_id')==panel and r.get('model_id')==model and r.get('arm')==arm]
    if not matches:return None
    if len(matches)!=1:raise ValueError('Duplicate block-availability entries for a plotted model.')
    value=matches[0].get('complete_prefix_rounds')
    if isinstance(value,bool) or not isinstance(value,int) or value<=0:
        raise ValueError('A plotted model must have a positive completed-round count.')
    return value


def mid_contrasts(data,source):
    records=data.get('mid_example')
    if not isinstance(records,list) or not records:
        raise ValueError('mid_example must contain actual observed shares and fresh predictions.')
    metadata=data.get('metadata',{})
    groups=list(dict.fromkeys(row['group'] for row in records))
    if len(groups)!=2:raise ValueError('The fixed household-car contrast requires exactly two groups.')
    if 'mid_group_order' in metadata:
        if set(metadata['mid_group_order'])!=set(groups):raise ValueError('mid_group_order does not match the supplied groups.')
        groups=metadata['mid_group_order']
    available=set.intersection(*(set(row.get('predictions',{})) for row in records))
    models=metadata.get('mid_models')
    if models is None:
        gpt=[m for m in available if 'gpt-4.1' in m]
        gemma=[m for m in available if 'gemma' in m.lower()]
        if len(gpt)!=1 or len(gemma)!=1:raise ValueError('Specify metadata.mid_models with exactly one GPT-4.1 and one Gemma model.')
        models=[gpt[0],gemma[0]]
    if len(models)!=2 or not set(models)<=available:raise ValueError('Both selected MiD models must have every contrast prediction.')
    cells={}
    for row in records:
        key=(row['group'],row['mode'])
        if key in cells:raise ValueError(f'Duplicate MiD contrast cell: {key}')
        if row['mode'] not in MID_MODES:raise ValueError(f'Unexpected MiD outcome: {row["mode"]}')
        cells[key]={'observed':probability(row['observed'],str(key)+' observed'),
                    'predictions':{m:probability(row['predictions'][m],str(key)+' '+m) for m in models}}
    if set(cells)!={(g,m) for g in groups for m in MID_MODES}:raise ValueError('The full two-group, three-mode contrast is required.')
    fig,axes=plt.subplots(3,2,figsize=(7.4,4.9),sharex=True)
    fig.subplots_adjust(left=.075,right=.96,bottom=.16,top=.77,wspace=.22,hspace=.53)
    fig.text(.03,.965,'Can AI reproduce the household-car contrast?',fontsize=13,fontweight='bold',va='top')
    fig.text(.03,.916,'Germany · modes reported on outward/return journeys with aircraft as the recorded main mode',fontsize=8.2,color=MUTED)
    rounds={m:completed_rounds(metadata,'mid_2023',m,'overall_rate_anchored') for m in models}
    labels={m:model_label(m,metadata)+(f' ({rounds[m]} rounds)' if rounds[m] is not None else '') for m in models}
    legend=[Patch(facecolor=OBSERVED,label='Observed'),Patch(facecolor=AI,label=labels[models[0]]),Patch(facecolor=AI_LIGHT,edgecolor=AI,hatch='//',label=labels[models[1]])]
    fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.026,.891),ncol=3,frameon=False,fontsize=8.3,columnspacing=2)
    for col,group in enumerate(groups):
        bbox=axes[0,col].get_position()
        fig.text(bbox.x0+bbox.width/2,.815,group,fontsize=10.2,fontweight='bold',ha='center')
    exact=[]
    for r,mode in enumerate(MID_MODES):
        for c,group in enumerate(groups):
            ax=axes[r,c];cell=cells[(group,mode)]
            vals=[cell['observed'],*(cell['predictions'][m] for m in models)]
            for i,(value,color) in enumerate(zip(vals,[OBSERVED,AI,AI_LIGHT])):
                y=2-i
                ax.barh(y,value*100,height=.57,color=color,edgecolor=AI if i==2 else color,lw=.4,hatch='//' if i==2 else None,zorder=3)
                ax.text(value*100+1.8,y,f'{value*100:.1f}%',fontsize=8.0,ha='left',va='center',color=color if i<2 else AI)
            ax.set_ylim(-.55,2.65);ax.set_xlim(0,115)
            ax.set_yticks([]);ax.xaxis.set_major_locator(MultipleLocator(25))
            ax.set_xticks([0,25,50,75,100]);ax.grid(axis='x',color=GRID,lw=.6,zorder=0)
            ax.spines['left'].set_visible(False);ax.spines['bottom'].set_visible(False)
            ax.tick_params(axis='x',length=0,pad=2)
            ax.set_title(MID_MODES[mode],loc='left',fontsize=9,pad=6)
            if r==2:ax.set_xlabel('Share of journeys (%)',fontsize=8)
            exact.append({'group':group,'mode':mode,**cell,'display_unit':'percentage, probability × 100'})
    fig.text(.03,.067,'Fresh averages with the public overall-share hint. Association does not establish causation.',fontsize=8,color=MUTED)
    fig.text(.03,.03,'Only three modes are shown; they may overlap. Bars show shares, not newly sampled passengers.',fontsize=8,color=MUTED)
    save(fig,'revised_02_mid_contrasts',{'models':models,'complete_rounds':rounds,'rows':exact,'metadata':display_metadata(metadata),'interpretation':'Fixed illustrative two-group contrast; no causal estimate or sampling uncertainty.'},source)


def distribution(values,where):
    if set(values)!=set(FMG_MODES):raise ValueError(f'{where} must supply all ten native FMG modes, including Other.')
    result={m:probability(values[m],f'{where}/{m}') for m in FMG_MODES}
    if not math.isclose(math.fsum(result.values()),1,abs_tol=1e-6,rel_tol=0):
        raise ValueError(f'{where} does not sum to one; no silent normalisation is allowed.')
    return result


def fmg_group_label(value):
    label=str(value).replace('_',' ').replace(' · ','\n').replace(' | ','\n').replace(' / ','\n').replace(' — ','\n').replace(' – ','\n')
    if '\n' not in label:
        for purpose in ('Business','Private'):
            if label.lower().startswith(purpose.lower()+' '):
                label=purpose+'\n'+label[len(purpose)+1:];break
    return '\n'.join(textwrap.fill(x,width=18) for x in label.split('\n'))


def fmg_results(data,source):
    rows=data.get('fmg');metadata=data.get('metadata',{})
    if not isinstance(rows,list) or len(rows)!=6:raise ValueError('FMG figure requires six actual purpose-by-flight-type groups.')
    if len({x['group'] for x in rows})!=6:raise ValueError('FMG group labels must be unique.')
    available=set.intersection(*(set(x.get('predictions',{})) for x in rows))
    model=metadata.get('fmg_model')
    if model is None:
        matches=[m for m in available if 'gpt-4.1' in m]
        if len(matches)!=1:raise ValueError('Specify metadata.fmg_model as the fresh GPT-4.1 model.')
        model=matches[0]
    if model not in available:raise ValueError('The chosen FMG model is missing one or more group predictions.')
    if 'fmg_group_order' in metadata:
        index={x['group']:x for x in rows}
        if set(metadata['fmg_group_order'])!=set(index):raise ValueError('FMG group order differs from supplied groups.')
        rows=[index[g] for g in metadata['fmg_group_order']]
    exact=[]
    for row in rows:
        observed=distribution(row['observed'],row['group']+' observed')
        predicted=distribution(row['predictions'][model],row['group']+' '+model)
        collapse=lambda d:{family:math.fsum(d[m] for m in members) for family,_,members,_ in FAMILIES}
        mae_pp=100*math.fsum(abs(predicted[m]-observed[m]) for m in FMG_MODES)/len(FMG_MODES)
        exact.append(dict(group=row['group'],observed_native=observed,predicted_native=predicted,observed_visual=collapse(observed),predicted_visual=collapse(predicted),mean_absolute_error_native_pp=mae_pp))
    fig,ax=plt.subplots(figsize=(7.4,5.65))
    fig.subplots_adjust(left=.255,right=.97,bottom=.16,top=.76)
    fig.text(.03,.966,'Munich: compare each group’s access choices',fontsize=13,fontweight='bold',va='top')
    rounds=completed_rounds(metadata,'fmg_2025',model,'unanchored')
    round_note=f' mean of {rounds} rounds' if rounds is not None else ' estimates'
    fig.text(.03,.921,f'Observed 2025 shares and {model_label(model,metadata)}{round_note} · no airport numerical hint',fontsize=8.5,color=MUTED)
    family_handles=[Patch(facecolor=color,edgecolor='white',label=label) for _,label,_,color in FAMILIES]
    fig.legend(handles=family_handles,loc='upper left',bbox_to_anchor=(.028,.893),ncol=3,frameon=False,fontsize=8,columnspacing=1.8,handlelength=1.6)
    fig.text(.03,.804,'Solid = observed     Hatched = AI estimate',fontsize=8,color=MUTED)
    ax.text(109,5.55,'Mean error\n(pp)',ha='center',va='bottom',fontsize=7.5,color=MUTED)
    centers=list(reversed(range(len(exact))))
    for i,(center,item) in enumerate(zip(centers,exact)):
        for observed in (True,False):
            y=center+(.155 if observed else -.155)
            values=item['observed_visual'] if observed else item['predicted_visual']
            left=0.
            for family,_,_,color in FAMILIES:
                width=values[family]*100
                ax.barh(y,width,left=left,height=.245,color=color,edgecolor='white' if observed else AI,lw=.32,hatch=None if observed else '//',zorder=3)
                if width>=8:
                    ax.text(left+width/2,y,f'{width:.1f}',ha='center',va='center',fontsize=7.6,color='white' if family=='rail' else INK,zorder=5)
                left+=width
            ax.text(-1.8,y,'Observed' if observed else 'AI',ha='right',va='center',fontsize=7.4,color=OBSERVED if observed else AI,fontweight='bold')
        ax.text(109,center,f'{item["mean_absolute_error_native_pp"]:.1f}',ha='center',va='center',fontsize=10,color=AI,fontweight='bold')
        if i<len(exact)-1:
            ax.axhline(center-.5,color=GRID,lw=.5,zorder=0)
    ax.axvline(103.5,color=GRID,lw=.7,zorder=0)
    ax.set_xlim(0,118);ax.set_ylim(-.55,len(exact)-.45)
    ax.set_yticks(centers,[fmg_group_label(x['group']) for x in exact],fontsize=8.2)
    ax.tick_params(axis='y',length=0,pad=56)
    ax.set_xticks([0,25,50,75,100]);ax.tick_params(axis='x',length=0)
    ax.grid(axis='x',color=GRID,lw=.55,zorder=0)
    ax.spines['left'].set_visible(False);ax.spines['bottom'].set_visible(False)
    ax.set_xlabel('Share of each passenger group (%)',fontsize=8.5,labelpad=5)
    fig.text(.03,.082,'Private car combines four parking/drop-off categories; rail combines S-Bahn and ÜFEX.',fontsize=7.9,color=MUTED)
    fig.text(.03,.045,'Error is the mean absolute difference across all ten original categories, in percentage points.',fontsize=7.9,color=MUTED)
    save(fig,'revised_03_fmg_results',{
        'model':model,'complete_rounds':rounds,'rows':exact,
        'visual_families':[{'family':f,'label':l,'source_modes':list(m),'color':c} for f,l,m,c in FAMILIES],
        'scoring_categories':list(FMG_MODES),'visual_aggregation_only':True,
        'native_modes_renormalised':False,'metadata':display_metadata(metadata),
        'interpretation':'Derived aggregate study comparison; no individual passenger records or causal effects.',
    },source)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',choices=('framework','mid','fmg','all'),default='all')
    parser.add_argument('--data',type=Path,default=DEFAULT_DATA)
    args=parser.parse_args();style()
    if args.only in ('framework','all'):framework()
    if args.only!='framework':
        path=args.data.resolve();data=load_data(path)
        if args.only in ('mid','all'):mid_contrasts(data,path)
        if args.only in ('fmg','all'):fmg_results(data,path)


if __name__=='__main__':main()
