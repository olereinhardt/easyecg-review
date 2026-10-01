# Proposed commit messages (0.2.0)

No repository was created or pushed automatically. Apply these boundaries to
your existing v0.1 tree; do not add personal input or result files.

```text
feat(detection): combine aligned XQRS, NeuroKit and SWT proposals

Replace the energy-only corroborator with three detectors, local waveform
features and explicit support/refractory checks. Retain rejected proposals and
detector failures for review, without inserting beats to regularize rhythm.
```

```text
feat(analysis): screen ectopic patterns with local rhythm and morphology context

Remove the five-regular-neighbour restriction and include non-compensatory
patterns. Add couplet/run, bigeminy/trigeminy, morphology-outlier and persistent
irregularity review hints. Exclude nearly flat intervals from pause counting and
report uncertain signal loss without assigning a cardiac or technical diagnosis.
```

```text
feat(filters): add evidence-based mains rejection and configurable bandpass

Apply zero-phase analysis filtering with optional auto/off/50/60Hz notch. Keep
raw EDF/WFDB samples unchanged and record filter evidence and parameters.
```

```text
feat(ui): select recording sessions and configure doubled PDF gain

Add source-bound multi-selection, explicit empty-selection protection and a
fast CLI inventory. Fully decode only selected sessions. Default PDF gain to
factor two, flag clipped panels and preserve original export calibration.
```

```text
test: add ectopy, T-wave, dropout, selection and calibrated-gain regressions

Compare current and prior algorithms on identically preprocessed MIT-BIH
excerpts; disclose false positives, misses and quality exclusions. Add longer
chunk-boundary coverage and digital EDF/WFDB round-trip verification.
```

```text
docs: prepare version 0.2 sources for public GitHub distribution

Add English/German READMEs, upstream/viewer links, methods and validation,
contribution/privacy guidance, changelog and synthetic CI. Exclude personal
recordings and patient reports from the source archive.
```

Suggested release title: `Release 0.2.0: session selection, display gain and ECG review improvements`
