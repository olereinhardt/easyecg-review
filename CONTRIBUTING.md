# Contributing

Use English commits and public issue descriptions. Install `.[dev]`, run pytest,
then build the wheel/sdist. Keep parser/export invariants and raw calibration
separate from display and experimental analysis changes.

Never attach personal recordings, reports, device identifiers or health logs to
public issues. Use synthetic minimal reproductions or appropriately licensed
public datasets. Inspect staged files before every push; ignore rules are not an
anonymization or access-control mechanism. The project bundles only synthetic
fixtures and aggregate public-reference metrics.

Changes to beat detection should disclose false positives, false negatives,
quality exclusions, reference annotations and benchmark preprocessing. Report
all tested records, including poor results; do not claim clinical validity from
a small development benchmark. Avoid conflating energy width with clinical QRS
duration or calling waveform pattern groups confirmed PAC/PVC/AF/VT diagnoses.

See docs/COMMIT_MESSAGES.md for suggested changeset boundaries. GitHub Actions
runs synthetic tests/builds; it does not upload or download patient data.
