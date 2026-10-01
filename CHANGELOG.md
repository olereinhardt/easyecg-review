# Changelog

## 0.2.0

- Configurable PDF gain, default factor 2; physical raw-export calibration unchanged.
- Three aligned QRS detectors with transparent confidence, morphology and rejected-proposal audit.
- Zero-phase configurable bandpass and evidence-based optional 50/60Hz notch.
- Local RR/morphology candidate screening without the five-regular-neighbours requirement;
  non-compensatory patterns and rhythm-context checks for irregular sequences.
- Additional overlapping review patterns: couplets, runs, bigeminy/trigeminy,
  fast different-shape runs, morphology outliers and persistent RR irregularity.
- Nearly flat intervals marked as signal dropout of unclear cause, excluded from pause counts.
- Explicit GUI session table and subset conversion, source-bound selection and empty-selection protection.
- Selected-session CRC validation; CLI inventory command.
- Public-reference paired benchmark, regression tests, publication-ready English/German documentation.

## 0.1.0

Initial strict PC-80B SCP parser, raw EDF+/WFDB export, quality-gated experimental
review reports, CLI/Tk GUI and separately invoked optional Ollama context review.
