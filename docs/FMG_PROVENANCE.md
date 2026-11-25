# Munich airport benchmark: provenance and permitted outputs

The Munich extension uses an FMG aggregate passenger-survey summary supplied through the seminar's Overleaf project. It concerns originating passengers departing Munich Airport in 2025. Transfer passengers and arrivals/egress are excluded according to the supplied summary. The source is aggregate data, not passenger microdata; annual passenger volumes must not be interpreted as interview sample sizes.

## Six observed groups

The primary comparison crosses business/private purpose with domestic/continental/intercontinental departing-flight type. For each of these six groups, the analysis combines the underlying source rows using their annual passenger volumes:

`group mode share = sum(row passenger volume × row mode share) / sum(row passenger volume)`.

The overall baseline is calculated from the same source rows and outcome categories. Group weights are each group's annual volume divided by the matching total. Rounded source volumes are retained without silently adjusting them to a separately reported total. Raw interview counts and sampling variances are unavailable, so these traffic weights do not justify sampling confidence intervals.

Direction and trip duration are marginalised using observed source aggregates. The primary comparison does not equate outbound/return flight with residence status, assume that visitors lack cars, or combine different years into purportedly observed joint personas. A separate proposed set of geography–duration personas is not used as an observed joint validation dataset.

## Outcome coding

The outcome is the **reported airport-access category**. It retains drop-off, airport parking, off-airport parking, other parking, taxi/ride-hailing, rental/carsharing, bus/transfer, S-Bahn, ÜFEX and Other as separate alternatives. In particular, using a shuttle after parking off-airport does not automatically convert that arrangement to the ordinary bus/transfer category. The source's parking category must be preserved.

The supplied summary describes last-mode reporting, but the original questionnaire and classification hierarchy are not included. Therefore, the study does not treat every category as the literal final vehicle in a multimode chain. It also does not equate airport access with national MiD journey-mode co-use. The source's flight-region categories require confirmation of their exact country membership and whether they refer to the next sector or final itinerary destination.

## Local processing and publication scope

On 25 November 2026, the user reported that FMG had approved publication of derived study results, while prohibiting external processing of FMG data. This is the study's recorded authorisation scope, not an independent legal assessment of an agreement.

- The workbook, source-row extracts and private target files remain outside the public repository.
- External model requests use only generic purpose-and-flight-type descriptions from the pre-existing research question. They contain no FMG observed shares, traffic counts, weights, source rows or numerical hints.
- The source-based baseline, aggregation, scoring and comparisons are computed locally. Any published evaluation findings remain distinct from both source data and model-generated predictions.
- Public code documents the calculation without embedding restricted observations. Access to an authorised copy of the source is necessary to reproduce the confidential data-preparation stage.

## Reproduction with authorised source access

Run locally:

```text
python src/prepare_fmg_benchmark.py --workbook PATH_TO_AUTHORISED_WORKBOOK --output PRIVATE_DIRECTORY_OUTSIDE_REPOSITORY
```

The script reads the audited source layout without saving, refreshing or recalculating the workbook. It validates the mode proportions, independently constructs the six groups and matched overall baseline, checks recombination, and verifies that the source file's hash is unchanged. It makes no network requests. Its output targets, long-format table and audit metadata are restricted working files, not public study deliverables.

The co-author summary cites upstream FMG workbooks that were not included in the reviewed upload. The implemented checks establish internal arithmetic consistency and preservation; they do not independently verify the upstream sampling, translation, expansion methodology or reuse agreement.
