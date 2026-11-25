# Historical pause note — superseded by authorized resumption

**Current status:** the user explicitly requested continuation. The amended run completed on 25 November 2026 at 17:42:44 UTC. See [the resumption audit](ADMINISTRATIVE_RESUMPTION_20261125.md) and [current continuation instructions](CONTINUE_HERE.md). The text below preserves the earlier shutdown handoff and does not describe the current paper or experiment state.

## Original shutdown handoff

Do not restart experiments until the user explicitly says to continue.

The user requested a placeholder draft before shutting down. `manuscript/revised_main.tex` is the new review draft; numerical results and two figures remain placeholders. The previously completed pilot is still `manuscript/main.tex`.

The active study process was stopped and its absence verified. Saved progress and every request remain under `../outputs/sequential_study_20261125/run_v2/`; the private scoring configuration is in its parent folder. Source and request hashes are frozen. Read `pause_state.json`, `progress.json`, `frozen_plan.json` and all terminal records before considering a restart. In-flight responses have unknown outcomes and conservative cost reservations; do not silently delete or repurchase them. The frozen runner will classify interrupted records and halt affected blocks, so design an explicit documented administrative-resumption amendment if needed, without selectively replacing unfavorable answers. No registered statistical checkpoint had yet been reached at pause.

The FMG workbook remains in the private Overleaf project. The supervisor permits publication of derived findings only, not external processing of FMG data. Generic Munich prompts contain no airport figures, counts, weights or numerical hints. All original airport extracts remain outside the public repository.

Existing code: `src/run_sequential_experiment.py` and `src/sequential_inference.py` are frozen and tested; `src/analyse_sequential_results.py` awaits a finalized run; `src/make_revised_figures.py` awaits fresh figure data; the exact prompt appendix and main-text gray hint box are already written. Preserve all local uncommitted changes.
