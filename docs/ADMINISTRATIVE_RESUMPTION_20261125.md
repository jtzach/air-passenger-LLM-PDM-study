# Administrative resumption amendment — 25 November 2026

The user explicitly paused execution to shut down the laptop and later requested completion. This amendment is made before fresh resumed calls and before the first registered statistical look. It is an administrative change, not an accuracy-based retry policy.

## Preserved design

- The original frozen runner, private configuration, prompts, targets, weights, provider restrictions, output checks, model settings, error allocations, practical margin, and looks remain unchanged.
- All 12 originally registered endpoints remain in the multiplicity denominator. The scheduled looks remain 16, 32, and 64 complete logical rounds.
- Previously halted blocks remain halted. Known invalid answers or service-identity failures discovered in the interrupted round also halt their block under the original rule.
- Three-repeat pilot results remain separate. Additional group or model comparisons remain descriptive.

## Audit at the pause

- The saved global progress ended after round 6. No registered look had occurred.
- There were 1,094 request records: 1,081 valid answers, five invalid answers, and eight requests with unknown outcomes at shutdown.
- Four blocks had already halted: Gemma 3 4B in both MiD conditions and FMG, and Qwen in FMG. Gemma's anchored MiD block retained two complete rounds; the other three retained none.
- All eight active blocks had an incomplete round 7. None had a fully completed cached round 7.
- Total accounted cost was $0.879770375, including $0.04340556 in conservative reservations for the eight unknown outcomes. These reservations remain charged against the original $10 ceiling unless separate verified billing evidence is documented in a later amendment.
- Original active elapsed execution was 866.615342 seconds, measured from the saved execution start to the documented pause. This time remains charged against the original 7,200-second cap. Only the explicit user pause and preparation before resumed execution are excluded.

## Whole-round administrative replacement

Each of the eight incomplete active blocks receives a completely new logical round 7, including its no-card control. Every original partial response is preserved byte-for-byte but excluded from that round's score. The rule applies regardless of its numerical answer. Known failures are not replaced. A fully completed cached round would have been retained regardless of accuracy.

Replacement requests use the suffix `__administrative_replacement1` and a seed offset of +1,000,000 from the original round seed. Their logical round stays 7, so the number of inferential observations and registered looks do not change. Subsequent rounds use their original planned seeds and IDs. This does not claim that distinct seeds prove independence.

The new immutable plan includes the original plan hash, all parent-file hashes, excluded request IDs, replacement requests and hashes, seed rule, code hashes, budget and runtime treatment. Only the original allowlisted public-safe prompt strings enter API messages. No FMG targets, weights, counts, rows, or workbook contents are transmitted.

The resumed runner initializes its budget from every preserved record, including all unscored partial responses and unknown reservations. It refuses to execute twice in the same resumed directory. Another administrative interruption requires another explicit audit and amendment; interrupted requests are never silently resubmitted.

## Analysis and limits

Analysis uses the selected complete logical-round prefix and independently reconstructs its scores. Administratively excluded responses remain in availability and cost totals. The final report discloses the pause, replacement rule, unknown outcomes, retained failures, and conditional nature of model-repeat inference.

Stable returned provider/model labels cannot establish that the hosted service's underlying behavior was unchanged across the pause. Formal repeated-call statements remain conditional on the original independence and stability assumptions; no survey-sampling or human-population confidence claim is added.

Implementation: `src/resume_sequential_experiment.py`; offline tests: `tests/test_sequential_resume.py`. The original frozen files are retained unchanged.
