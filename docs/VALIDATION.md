# Validation and test scope (0.2.0)

**Development verification only; no clinical validation.** Public data were used
while changing the heuristics. Results are not an independent held-out evaluation,
and are not evidence of motion-artifact accuracy on the handheld. No private ECG
or patient-specific measurement details are included in this document.

## Automated regression tests

39 tests: strict SCP/CRC/index parsing and malformed ZIPs; digital EDF/WFDB
round trips and calibration; clean/inverted QRS; steep QRS, broad T waves and
movement exclusions; isolated and non-compensatory early beats; frequent
bigeminy/trigeminy; nearly flat dropout versus long RR with background signal;
phase-neutral baseline/mains filtering; selected-session-only decode, empty
selection and GUI command construction; PDF gain/calibration without altering
raw export; AI localhost mock, redirect and remote opt-in checks.

Executed on Python 3.12.14. Exact dependency versions: `requirements-tested.txt`.
The GitHub matrix describes intended CI versions; it has not been run on GitHub
from this delivery. No true medical LLM assessment was requested.

## Paired public-reference comparison

First 600s, channel 0, ten MIT-BIH records. Resampled 360→150Hz. Waveform amplitude
is preserved using a per-record integer scale that avoids artificial ADC clipping;
this is not an electrical PC-80B simulation. Both v0.1 and v0.2 saw identical inputs.
No annotation is supplied to detection. One-to-one matching tolerance: ±150ms.
All beat annotations remain in the denominator, including excluded-quality time.

Reference ectopic symbols: `A,a,J,S,V`; ventricular escape `E` is not premature
and is excluded. Subtype labels, clinical QRS duration, rhythm episode diagnoses
and motion artifacts are not validated by this matching test.

TP = matched; FP = unmatched candidate; FN = missed annotation.

| Record | QRS v0.1 TP / FP / FN | QRS v0.2 TP / FP / FN | Ectopic v0.1 TP / FP / FN | Ectopic v0.2 TP / FP / FN |
| --- | --- | --- | --- | --- |
| 100 | 760 / 0 / 0 | 760 / 0 / 0 | 4 / 0 / 2 | 6 / 0 / 0 |
| 200 | 869 / 0 / 1 | 869 / 0 / 1 | 15 / 0 / 235 | 219 / 1 / 31 |
| 108 | 547 / 126 / 15 | 549 / 16 / 13 | 4 / 0 / 3 | 6 / 13 / 1 |
| 207 | 647 / 107 / 6 | 638 / 65 / 15 | 2 / 0 / 99 | 73 / 17 / 28 |
| 101 | 645 / 4 / 1 | 645 / 3 / 1 | 1 / 0 / 1 | 1 / 0 / 1 |
| 103 | 703 / 0 / 0 | 703 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 201 | 746 / 0 / 15 | 746 / 0 / 15 | 1 / 15 / 40 | 17 / 18 / 24 |
| 208 | 1006 / 0 / 7 | 1005 / 0 / 8 | 39 / 0 / 327 | 175 / 0 / 191 |
| 105 | 832 / 1 / 1 | 832 / 1 / 1 | 21 / 0 / 0 | 21 / 1 / 0 |
| 219 | 757 / 0 / 0 | 757 / 0 / 0 | 2 / 13 / 28 | 15 / 34 / 15 |

| Aggregate | v0.1 TP / FP / FN | v0.2 TP / FP / FN |
| --- | --- | --- |
| QRS | 7512 / 238 / 46 | 7504 / 85 / 54 |
| Ectopic candidates | 89 / 28 / 735 | 533 / 84 / 291 |

QRS false positives decreased, with a small increase in misses overall. Ectopic
sensitivity improved substantially, but remains inconsistent: records 201 and
219 still have many unmatched candidates, and almost half the annotated ectopy
in record 208 is missed. Candidate counts are therefore **not reliable clinical
extrasystole counts**. A missing mark must not be treated as evidence of absence.

Compared with the old two-record v0.1 benchmark, the preprocessing changed: the
old fixed 806nV/LSB profile clipped high-amplitude public signals. Its results
must not be compared directly to the new preservation profile. The paired
baseline above was rerun with the same new input scale, not copied from old metrics.

Full metrics including usable time and the exact profile:
[benchmark_mitdb_v02.json](benchmark_mitdb_v02.json).

## Longer record / chunk boundaries

MIT-BIH 100, first 1800s, channel 0, preservation profile: 2265 matched QRS, zero
unmatched/missed QRS at ±150ms; 34/34 ectopic annotations matched, zero unmatched
candidates. This also exercises multiple 300s detector chunks. It does not
establish performance on difficult rhythm/shape classes or other channels.
[benchmark_long100_v02.json](benchmark_long100_v02.json).

```bash
python tools/benchmark_mitdb.py --download --seconds 600 \
  --records 100 200 108 207 101 103 201 208 105 219 \
  --cache private/public-cache -o private/benchmark.json
python tools/benchmark_mitdb.py --download --seconds 1800 \
  --records 100 --cache private/public-cache -o private/benchmark-long.json
```

The optional `--baseline-module /path/to/v0.1/analysis.py` produces the paired
comparison; the previous implementation is not included in this release.

## Input/export integration and PDFs

The complete supplied input was converted, with all selected SCP CRCs checked
and all raw samples compared after reading EDF+ and WFDB back. Gain changes only
PDF geometry; original integer samples and original device words remain unchanged.
Outputs were checked against manifest hashes. Example report pages were rendered
with Poppler and visually inspected for panel bounds, labels, gain and calibration.
No clinician-adjudicated ground truth exists for that input; report counts cannot
be assigned clinical sensitivity or specificity.

The format interpretation was previously compared sample-for-sample with the
upstream converter at revision `d0432998186b12216e7d103b404c1037145a3666`:
[easyecg2gdf](https://github.com/majbthrd/easyecg2gdf). Conversion checks do not
validate electrode geometry, the amplitude against a calibrated medical signal
generator, or device clock error.

GUI selection/command helpers are tested headlessly. A desktop could not be
opened in this execution environment, so interactive GUI layout and end-user
click flows have not been exercised here. CLI subset and full conversion were
executed. EDF+/WFDB viewer rendering is not vendor Holter-import validation.

Sources: [MIT-BIH](https://physionet.org/content/mitdb/1.0.0/),
[WFDB](https://wfdb.readthedocs.io/),
[NeuroKit](https://neuropsychology.github.io/NeuroKit/functions/ecg.html).


## 0.3.0 localization regression checks

- 100 pytest checks pass in the Python 3.12 development environment.
- All 18 catalogs contain the same 149 keys and named placeholders.
- Every catalog glyph, including shaped Arabic presentation forms, is covered
  by the bundled PDF fonts. No missing glyph warnings in final sample renders.
- GUI language forwarding, context isolation and language preference aliases
  are checked. The real Tk 8.6/Xft UI was switched through all 18 languages,
  preserving selected recording IDs and input paths.
- Summary (including trend), review-strip and full-curve PDFs were rendered for
  all 18 languages using a 120-second synthetic signal; layouts were inspected.
- EDF+ digital samples remain identical to the synthetic input with English,
  Chinese, Japanese and Arabic report selections. Existing gain/export tests
  and 39 analysis/input regressions continue to pass.
- io.py, analysis.py, detection.py and export.py are byte-identical to the
  recovered 0.2.0 release. The real personal ECG archive was not reprocessed
  for this presentation-only release.
- Wheel and source distribution contain every catalog and font/license asset.

These are development checks, not clinical validation or professional review
of the medical translations. PDF Arabic is drawn in visual glyph order; text
extraction may return that visual order rather than logical Unicode order.
