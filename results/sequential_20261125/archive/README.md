# Final sequential request archive

This archive includes every saved request and result from the original paused run and its explicitly frozen administrative resumption. It does not contain the airport workbook, native source rows, or passenger counts. The model inputs are checked against the public-safe prompt library. The separately reviewed evaluation configuration, when included, contains only public MiD targets and the six airport groups' authorized derived rates/weights/baseline, generic prompts and settings. It is an offline scoring artifact, never an API message.

`raw/` contains exact request bodies and scientific outputs, including invalid outputs and unknown interrupted outcomes. Authentication headers were never saved. Any remaining credential/account metadata in response envelopes or errors is redacted only in these public copies; `MANIFEST.json` records source/export hashes and changed files. Model/provider IDs, generation IDs, seeds, timestamps, usage, retries, scores and numerical predictions are retained.

`request_index.csv` identifies each record's role. `excluded_administrative_partial_round` means it belonged to a whole round interrupted by the explicit user pause; its costs remain counted, but its numerical response does not enter the replacement round. `retained_audit_only` includes terminal failures and any other records outside a complete scoring prefix. `in_progress` on an original record means an unknown outcome at the pause; the preserved record is not evidence of a currently running request.

`frozen_plan.json` preserves the amended plan, parent-plan hash, exact request hashes and source-code hashes. `parent_snapshot/` preserves the original plan and pause/progress documentation. `looks/` preserves scheduled decisions. `summary.json` reports all originally registered blocks, including failed and inconclusive ones. Never combine records solely by logical round/card: use the administrative exclusion map or `request_index.csv` to distinguish original and replacement IDs.

The original three-repeat pilot is separate and absent from this archive. Repeat-level intervals concern model generation under stated stability/independence assumptions, not uncertainty in human survey proportions. Rationale text is a generated hypothesis, not evidence of passengers' motives.

## Offline replay (no API calls)

From the repository root, extract this ZIP into `outputs/sequential_replay`, then run:

```text
python src/analyse_sequential_results.py --config outputs/sequential_replay/evaluation_config.json --run-dir outputs/sequential_replay --output outputs/sequential_replay_analysis
```

The evaluation JSON retains its exact historical bytes and canonical hash. Its `catalogue_path` records the original machine's path; the offline analyzer does not read it, so no path override is necessary. Do not edit this historical file to run new calls. A new paid experiment needs an explicitly revised configuration with a local catalogue path and its own new freeze. The private airport workbook is not needed to reproduce scoring from the released six-group derivatives; reproducing the upstream derivation still requires authorized source access.
