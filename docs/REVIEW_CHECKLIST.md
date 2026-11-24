# Author review

The main paper is intentionally short: approximately 859 rendered narrative words, plus three figures and references. The supplement holds formulas, prompt design, operational failures and detailed diagnostics.

- Confirm the title and outcome definition: **ground-mode co-use on air journeys**, rather than identified airport-access choice.
- Assess whether the aggregate adaptation of LLM-PDM is the intended contribution. Joint passengers and individual behavior were not simulated or validated.
- Review the fixed two-traveller/two-journey variable rule, same-data screening/evaluation and household-companion definition.
- Review the full results, including the three weaker persona models and Gemma 3 12B's operational failure. The only anchored persona model beating the observed-rate baseline was GPT-4.1.
- Inspect all three figures and the observed-versus-predicted labels in the Excel appendix.
- Confirm author names, order, affiliations, acknowledgments and AI-use disclosure. The draft deliberately leaves the author line empty.
- Review the journal's current submission requirements before submitting. This repository and Overleaf project are a review package, not a submitted or accepted article.

Evidence and checks: `results/manuscript_qa.json`, `figures/validation_report.json`, workbook preservation validation and `results/release_qa.json`. Reproduction uses archived outputs and incurs no API charge.
