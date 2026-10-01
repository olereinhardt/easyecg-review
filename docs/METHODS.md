# Methods and limitations (0.2)

All labels are experimental review hints, not diagnoses. The program never
relabels a detected QRS as a clinically confirmed normal/PAC/PVC beat.

## Raw signal and filtering

SCP integers, calibration and device status words are retained. Detection uses
mV; PDF gain is a separate display parameter. EDF+/WFDB are not filtered, amplified
or resampled. Zero-phase third-order Butterworth bandpass defaults to 0.5–40Hz.
Automatic mains estimation uses up to 12 evenly spaced 20s excerpts, Welch spectra,
50/60Hz peak-to-shoulder ratio >5 and >1% of analysed spectral power. The strongest
eligible mains peak gets a Q=30 notch; explicit 50/60/off bypasses this choice.
Notch evidence and bandpass settings are stored. A brief/local transient can be
missed by spectral sampling. Zero-phase filtering is offline and can ring near
steps; raw curves and excluded edges are essential for review. Filters are not
appropriate for diagnostic ST/QT measurements.

## QRS proposals

WFDB XQRS, NeuroKit2 `neurokit`, and `kalidas2017` SWT run in 300s chunks with 5s
overlap. Proposals are aligned to dominant absolute waveform deflections in
3–30Hz (SWT asymmetric delay compensation), clustered within 80ms, and checked
for amplitude, 20–260ms energy width and a 240ms refractory competition. Strong
single-detector proposals can remain in the review output but cannot enter
rhythm counting. At least two detectors must support a rhythm-counted beat.
Support is a vote count, **not** a calibrated probability. Detector failures and
rejected proposals remain available; rejected proposals are not expert-labeled
non-beats. No beat is inserted to regularize RR and no `signal_fixpeaks` rhythm
correction is used. Broad, biphasic complexes and tall T waves remain difficult;
QRS position may reflect a dominant S instead of a conventional R apex.

Morphology uses ±160ms 1–35Hz waveform vectors with endpoint-baseline removal and
unit-norm correlation. The proposal screen uses narrow local references; final
rhythm screening recomputes a repeated-shape local template within ±30s. It uses
non-early intervals where sufficient, and a morphology medoid/correlated group
rather than averaging opposite shapes. Local width is a 10–90% cumulative-energy
span in 3–30Hz, **not** a delineated clinical QRS duration. Template shape is local,
automatic and not guaranteed to represent normal conduction.

## Quality and near-flat uncertainty

10s gates cover ADC clipping, raw amplitude variation, baseline drift, abrupt
steps relative to normal QRS slopes, residual high-frequency noise (after applied
notch) and detector disagreement. First/last 2s are excluded. Nearly constant
250ms rolling raw variation below max(2.5 ADC steps, 0.0015mV), persisting ≥1s,
marks a separate sample-level dropout. Such intervals are excluded, explicitly
shown, and never counted as confirmed pauses. Contact/movement/technical failure
is possible; absence of recorded activity cannot safely exclude a rhythm cause.
Upper device status bits are retained but their undocumented meaning is not used.

Coverage is sample-level; window `usable_fraction` and reasons are available.
Excluded time is not known normal. Quality gates are heuristic and can reject
real ECG or accept artifacts. Motion-artifact clinical accuracy has not been
established.

## RR and morphology candidates

Local reference is a median of neighbouring 0.25–2.5s RR intervals, excluding the
immediate preceding/following pair. Three context intervals suffice; no five
uniform-normal-beat gate. Short RR <85% of reference needs a longer follower,
different shape, or stronger prematurity (<78%). Similar-shape candidates also
need structured local context: robust variability of adjacent-pair cycles ≤0.12,
or a repeatable every-second/every-third short-interval pattern, reducing false
“extrasystoles” in unstructured irregular rhythms. This gate can
miss true ectopy during irregular rhythm; no AF/P-wave classification is performed.

Strong different-shape candidates supported by all three detectors may qualify
without strict 85% prematurity, provided relative energy width and timing support
apply. Different-shape/wider candidates receive a VES-pattern-review label;
remaining candidates receive a similar/narrow-pattern label. Neither is a
validated clinical subtype. Morphology outliers are also reported separately.

Consecutive candidates produce couplets/runs; repeated every-second/every-third
candidate chains of ≥4 produce bigeminy/trigeminy hints. Fast different-shape runs
require ≥3 consecutively flagged complexes and estimated rate >configured fast
threshold. Sensitivity for runs is limited by individual beat flags and quality.
Long RR ≥2s requires usable bounding beats and continuous usable intervening
signal. Ten-second median rate >100/<50 per minute gives high/low-rate hints.
30s RR windows require ≥85% sample coverage, ≥12 usable intervals, CV >0.18 and
RMSSD >0.12s. Three adjacent such windows yield persistent irregularity ≥90s.
These labels overlap and must not be added to the individual candidate count.

## Interpretation

No validated AF, VT, PAC/PVC, AV block, ischemia/ST, QT/QTc, pacemaker or asystole
assessment. No all-clear, clinical burden estimate or treatment recommendations.
A nearly flat interval is not assigned a cardiac or technical diagnosis.
`confirmed_extrasystoles` is always null. EDF annotations and WFDB `Q` markers are
explicitly unverified. The lead and device clock/timezone are unknown. AI is a
separate optional text review, never an authoritative beat classifier.

References: [WFDB](https://wfdb.readthedocs.io/en/latest/processing.html),
[NeuroKit ECG documentation](https://neuropsychology.github.io/NeuroKit/functions/ecg.html),
[NeuroKit implementation](https://github.com/neuropsychology/NeuroKit/blob/master/neurokit2/ecg/ecg_findpeaks.py),
[PyWavelets](https://pywavelets.readthedocs.io/),
[MIT-BIH](https://physionet.org/content/mitdb/1.0.0/).
