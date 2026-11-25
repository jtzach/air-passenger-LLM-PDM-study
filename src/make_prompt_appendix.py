"""Typeset the exact frozen public prompt strings, with no airport data access."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def esc(text):
    chars={"\\":r"\textbackslash{}","&":r"\&","%":r"\%","$":r"\$","#":r"\#",
           "_":r"\_","{":r"\{","}":r"\}","~":r"\textasciitilde{}","^":r"\textasciicircum{}"}
    return "".join(chars.get(c,c) for c in text)

def box(title,text):
    # Newlines are paragraph/line layout only; archived request files preserve
    # exact bytes, including whitespace and model parameters.
    paras=[]
    for paragraph in text.split("\n\n"):
        paras.append(esc(paragraph).replace("\n",r"\par "+"\n"))
    return "\\begin{promptbox}[title={"+esc(title)+"}]\n"+"\n\n".join(paras)+"\n\\end{promptbox}\n"

def main():
    library=json.loads((ROOT/"config/sequential_prompt_library_20261125.json").read_text(encoding="utf-8"))
    mid,fmg=library["panels"]
    personas=json.loads((ROOT/"data/processed/personas.json").read_text(encoding="utf-8"))
    example=next(p for p in personas if p["feature"]=="anzauto_gr1" and p["category_label"]=="No car")
    without=mid["prompts"]["unanchored"][example["persona_id"]]
    with_hint=mid["prompts"]["overall_rate_anchored"][example["persona_id"]]
    hint=next(p for p in with_hint.split("\n\n") if p.startswith("Population-level reference"))
    output=[r"\subsection{MiD: exact no-hint request}"]
    output.append("This is the full user message for the no-household-car group. No additional system message was sent. "
                  "The same wording is used for all four models; only the group paragraph changes between cards. "
                  "Model, seed, temperature and output limits are separate API parameters in the archived request files.")
    output.append(box("MiD group description, without overall-rate hint",without))
    output.append("For the hinted condition, insert the following paragraph immediately before the final paragraph beginning ``Return only one JSON object''. All other words remain the same.")
    output.append(box("Exact paragraph added for the MiD hint condition",hint))
    control=mid["prompts"]["unanchored"]["no_persona"]
    control_paragraph=next(p for p in control.split("\n\n") if p.startswith("Cohort profile:"))
    output.append("For the no-group control, replace the complete cohort-profile paragraph with the following. The control retains the overall-rate paragraph in the hinted condition.")
    output.append(box("Exact MiD no-group replacement",control_paragraph))
    output.append(r"\subsection{The 23 exact MiD group paragraphs}")
    output.append("Each paragraph below replaces only the cohort-profile paragraph in the full prompt above. They are separate requests; the attributes are never combined into a joint person.")
    for p in personas:
        paragraph=next(q for q in mid["prompts"]["unanchored"][p["persona_id"]].split("\n\n") if q.startswith("Cohort profile:"))
        output.append(box(p["feature_label"]+": "+p["category_label"],paragraph))
    output.append(r"\subsection{Munich: exact generic request, without an airport-data hint}")
    example_id="fmg_business_domestic"
    output.append(box("Munich business / domestic group: full request",fmg["prompts"]["unanchored"][example_id]))
    output.append("The following are the six exact group-description paragraphs. Each replaces only that paragraph in the request above. No target percentages, source volumes or source weights appear in these messages.")
    for key,text in fmg["prompts"]["unanchored"].items():
        if key=="no_persona":continue
        paragraph=next(p for p in text.split("\n\n") if p.startswith("Group description:"))
        output.append(box(key.removeprefix("fmg_").replace("_"," / "),paragraph))
    paragraph=next(p for p in fmg["prompts"]["unanchored"]["no_persona"].split("\n\n") if p.startswith("Group description:"))
    output.append(box("Exact Munich no-group replacement",paragraph))
    destination=ROOT/"manuscript/generated/exact_prompts_appendix.tex"
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text("\n\n".join(output)+"\n",encoding="utf-8")
    print(destination)

if __name__=="__main__":main()
