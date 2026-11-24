# Author review

The main paper is designed to keep the journal text under 1,000 words, with three figures and references. The supplement holds formulas, prompt design, operational failures and detailed diagnostics. Start with the [plain-language walkthrough](PLAIN_LANGUAGE_WALKTHROUGH.md) to see the study as group cards, three estimates and a comparison with survey rates.

- Confirm the title and outcome definition: **ground-mode co-use on air journeys**, rather than identified airport-access choice.
- Assess whether the aggregate adaptation of LLM-PDM is the intended contribution. Joint passengers and individual behavior were not simulated or validated.
- Review the fixed two-traveller/two-journey variable rule, same-data screening/evaluation and household-companion definition.
- Review the full results, including the three weaker persona models and Gemma 3 12B's operational failure. The only anchored persona model beating the observed-rate baseline was GPT-4.1.
- Inspect all three figures and the observed-versus-predicted labels in the Excel appendix.
- Confirm author names, order, affiliations, acknowledgments and AI-use disclosure. The draft deliberately leaves the author line empty.
- Review the journal's current submission requirements before submitting. This repository and Overleaf project are a review package, not a submitted or accepted article.

Evidence and checks: `results/manuscript_qa.json`, `figures/validation_report.json` and workbook preservation validation. `results/release_qa.json` records the initial release audit; revision checks are recorded separately. Reproduction uses archived outputs and incurs no API charge.
