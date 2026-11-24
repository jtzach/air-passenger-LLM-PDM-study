"""Audit local manuscript sources and compiled PDFs; no manuscript mutation.

The reproducible word convention treats whitespace-separated words containing
letters/digits as words after removing TeX markup. Captions, keywords, and
acknowledgments are included; title, bibliography, and embedded figure labels
are excluded. In-text citation commands count as one token per cited source;
the rendered PDF count is also recorded as a deliberately broader check.
"""
from pathlib import Path
import json
import logging
import re
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parents[1]


def plain(text):
    # TeX comments only; escaped percent symbols remain ordinary characters.
    text = re.sub(r"(?<!\\)%[^\n]*", "", text)
    text = re.sub(r"\\cite[pt]?\{([^{}]*)\}",
                  lambda m: " ".join("CITATION" for _ in m[1].split(",")), text)
    text = re.sub(r"\\(?:ref|label|studyfigure|maketitle|centering|begin|end)\*?(?:\[[^]]*\])?(?:\{[^{}]*\}){0,2}", "", text)
    text = re.sub(r"\\[A-Za-z]+\*?(?:\[[^]]*\])?", "", text)
    text = text.replace("{", "").replace("}", "").replace("~", " ")
    text = text.replace("\\%", "%").replace("\\&", "&")
    return " ".join(text.split())


def count(text):
    return sum(bool(re.search(r"[A-Za-z0-9]", word)) for word in text.split())


def main():
    source = (ROOT / "manuscript/main.tex").read_text(encoding="utf-8")
    body = source.split(r"\begin{document}", 1)[1].split(r"\bibliographystyle", 1)[0]
    abstract = body.split(r"\begin{abstract}", 1)[1].split(r"\end{abstract}", 1)[0]
    normalized = plain(body)
    report = {
        "source_main_words_including_abstract_captions_keywords_acknowledgments": count(normalized),
        "abstract_words": count(plain(abstract)),
        "word_count_convention": __doc__.strip(),
        "pending_result_markers": len(re.findall(r"\\pending\{", body)),
        "numbered_sections": re.findall(r"\\section\{([^{}]+)\}", body),
        "figure_count": len(re.findall(r"\\begin\{figure\}", body)),
        "bibliography_entries": len(re.findall(r"^@", (ROOT / "manuscript/refs.bib").read_text(), re.M)),
    }
    for name in ("main", "supplement"):
        path = ROOT / f"manuscript/{name}.pdf"
        if path.exists():
            reader = PdfReader(path)
            pdf_text = "\n".join(page.extract_text() for page in reader.pages)
            before_refs = pdf_text.split("References", 1)[0]
            report[name + "_pdf_pages"] = len(reader.pages)
            report[name + "_pdf_words_before_references_including_figures"] = count(before_refs)
            report[name + "_pdf_has_pending_marker"] = bool(re.search(r"RESULT\s*PENDING", pdf_text))
            if name == "main":
                narrative_parts = []

                def narrative_visitor(text, cm, tm, font, size):
                    # The official template uses Latin Modern Roman; vector
                    # figures use DejaVu Sans. Keep actual rendered citations,
                    # captions, title/date, headings, and page numbers.
                    if "LMRoman" in str((font or {}).get("/BaseFont", "")):
                        narrative_parts.append(text)

                for page in reader.pages:
                    page.extract_text(visitor_text=narrative_visitor)
                narrative = "\n".join(narrative_parts).split("References", 1)[0]
                report["main_rendered_words_excluding_figures_and_references"] = count(narrative)
                report["rendered_narrative_count_note"] = (
                    "Includes actual rendered citations, abstract, captions, "
                    "keywords, acknowledgments, title, date, headings, and page "
                    "numbers. Excludes DejaVu Sans figure text and bibliography. "
                    "This is a conservative check against the 1,000-word limit."
                )
        log = ROOT / f"manuscript/{name}.log"
        if log.exists():
            text = log.read_text(encoding="utf-8", errors="replace")
            report[name + "_overfull_boxes"] = len(re.findall("Overfull", text))
            report[name + "_unresolved_citations"] = bool(re.search("Citation.*undefined|There were undefined citations", text))
    output = ROOT / "results/manuscript_qa.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
