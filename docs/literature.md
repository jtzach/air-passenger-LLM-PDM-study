# Literature basis and precise novelty boundary

Checked against primary sources on November 24, 2026. The bibliography in `manuscript/refs.bib` contains eight entries: four research papers and four official data/documentation sources. The main contribution is an openly reproducible aggregate benchmark for three ground-mode co-use indicators within MiD 2023 air journeys. It is not the first application of LLM personas to transport, and absence of an identical paper is not proof of universal novelty.

| Primary source | What the source establishes | Difference in this study |
|---|---|---|
| Tzachristas, Narayanan, and Antoniou (2026), [LLM-PDM](https://doi.org/10.26599/COMMTR.2026.9640004) | Persona-conditioned survey generation, persona weights, and distribution guidance; German MiD 2017 and transfer evaluation. | One-attribute aggregate cohorts and directly elicited probabilities; no reconstructed joint personas or synthetic individuals. Overall-rate guidance follows the spirit of Appendix C, with explicitly withheld conditional targets. |
| Bisbee et al. (2024), [Synthetic Replacements for Human Survey Data?](https://doi.org/10.1017/pan.2024.5) | Persona-generated survey means can look plausible while variation, relationships, prompt sensitivity, and replication are problematic. | Tests conditional aggregate margins and repeated outputs against a transparent constant baseline; does not claim replacement of respondents. |
| Mo et al. (2026), [Large Language Models for Travel Behavior Prediction](https://doi.org/10.1016/j.trip.2026.102124) | Compares direct prompting, optimized prompts, embeddings, and conventional prediction models under varying labeled-data budgets. | No labeled individual records or fitted individual choice model; the task is marginal frequency elicitation. Publisher abstract and the lead author's institutional publication list were checked. |
| Liu, Li, and Yin (2026), [Aligning LLM with Humans for Travel Choices](https://doi.org/10.1287/trsc.2025.0330) | Learns traveler personas and a persona-loading function, evaluating individual and aggregate choice outcomes on Swissmetro. | Uses observed one-way groups without learning a joint latent persona assignment. This limits the claim to public aggregate observables. |

## Reading notes on LLM-PDM

The complete 18-page user-supplied published PDF was read, including Algorithms 1–3, Sections 3–7, and Appendices A–F. Page 5 was also rendered to inspect the algorithms visually.

- The original framework factorizes joint persona weights as chained conditional probabilities and samples or allocates responses to joint attribute combinations. Separate one-way MiT tables cannot identify those weights. Multiplying marginals would introduce an unverified independence assumption.
- Appendix C explicitly illustrates guidance containing overall population mode rates. The present two-arm design operationalizes this transparently; no cohort-specific target rates are supplied.
- The original task generates survey responses; this study asks directly for conditional probabilities. Calling the present output a synthetic population, individual simulation, or exact replication would be inaccurate.
- The original paper contains different generation settings across descriptions and variants, including 0.7 and 0.2–0.4 temperatures and differing output caps. Our configuration is specified independently, not represented as one uniquely prescribed original setting.
- The original preprocessing discusses reallocating unspecified responses to common categories in one section, while its appendix describes complete-case filtering. Our method retains raw missingness and reports explicit eligibility/coverage exclusions rather than inheriting an ambiguous rule.
- The original appendix describes joined person/household records while naming a Tabellenband release. We do not use that description to claim that published marginal tables identify a joint persona population.
- Original replication links: [GitHub](https://github.com/jtzach/LLM-based-AI-surveys-MiD2017) and [dataset DOI](https://doi.org/10.26599/ETSD.2025.9190065). They are pointers reported in the paper; this study does not claim to have rerun its code or independently validated its results.

## Official data sources

- [MiT 2023](https://mobilitaet-in-tabellen-2023.bast.de/): public cross-tabulations; raw requests/responses and retrieval metadata are archived in the study repository.
- [Methods report, version 2.0, August 2025](https://www.mobilitaet-in-deutschland.de/pdf/infas_Methodenbericht_MiD2023_7555.pdf): survey design and field period.
- [Data-use handbook, August 2025](https://www.mobilitaet-in-deutschland.de/pdf/infas_HandbuchZurDatennutzung_MiD2023_7555.pdf): units, file structure, weights, and missingness.
- [Official publication index](https://www.mobilitaet-in-deutschland.de/publikationen2023.html): supplementary study materials and questionnaire. In the supplementary materials, overnight-journey module PDF pages 20–21 (internal overview pages 17–18) state the population, recall, up-to-three-journey limit, and multiple-response outward/return question.

## Scope of the novelty claim

The defensible claim is the specific combination of MiD 2023 air-journey co-use, reproducible aggregate-only cohort construction, a fixed descriptive selection rule, and explicit comparison of unanchored versus overall-rate-guided LLM estimates to an empirical constant baseline. Single-attribute profiles avoid unsupported joint-persona assumptions. The claim must remain this narrow even if performance is strong. No exhaustive systematic-review claim, causal finding, airport-access finding, Munich-specific validation, or superiority over a fitted individual-level transport model is supported.

## Journal fit

The [Findings author instructions](https://findingspress.org/for-authors) and linked [official template](https://www.overleaf.com/latex/templates/findings-template/bmhtkwbzvvcx) were checked and archived. The paper uses Questions, Methods, and Findings, a short abstract, no separate literature-review section, and three figures. Full technical equations and call details are supplementary; the main text retains all essential population, task, selection, comparator, and inference boundaries. A null or unfavorable model result remains a reportable finding. Submission metadata, authorship, conflicts, and final author approval are separate from preparing this review draft.
