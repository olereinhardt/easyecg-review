# Supported PC-80B profile

This is intentionally not a general SCP-ECG decoder. The supported PC-80B profile
have 9796 bytes, 4500 raw samples, section 2 descriptor
`0100010000100100000008000000`, one lead in section 3, and uncompressed,
non-differential section 6. Unknown table descriptors, multiple leads or
compression flags are rejected rather than decoded speculatively.

* File header: uint16 CRC then uint32 total length, little-endian.
* Sequential sections have 16-byte headers. File and section CRC-16/CCITT
  (initial 0xffff) are checked. All bounds, lengths, duplicates and required
  sections are checked. CRC is error detection, not authentication.
* Date/time: section 1 TLV tags 25 (year/month/day) and 26 (hour/min/sec).
* Calibration/payload: section 6 amplitude nV/LSB, sample interval microseconds,
  two unsupported differential/bimodal bytes, payload byte length, uint16 words.
* Signal value: `(word & 0x0fff) - 2048`, multiplied by amplitude / 1e6 for mV.
* Upper four bits are preserved in `device_words` in raw.npz. Their semantics
  are undocumented. They are counted but not used as contact/beat diagnoses.
* Unknown electrode arrangement: labels explicitly say `unknown lead` even
  though the file contains an internal lead code. No lead II assumption.

The original converter uses 150 Hz. The device header holds 6666 us, which would
mathematically imply ~150.015 Hz. This release uses **150 Hz nominal**, matching
4500 samples per 30s segment and the embedded 30s timestamp cadence. It records
both the nominal frequency and original interval; it does not resample or alter
samples. Actual clock error is unknown. Other sample intervals are rejected.

README.TXT ranges define recording sessions; numeric file IDs are looked up
across ECG_0..ECG_n, not inferred from lexicographic sorting or a fixed directory
capacity. Exact expected numbering is verified. Overlaps/duplicates are errors.
Case-insensitive name matching accepts `.SCP` / `.scp`. Missing/invalid blocks
stop by default; explicit --allow-missing splits around them. Timestamp offsets
larger than 50ms or calibration/lead changes also split, with a warning.

EDF+ stores the centered integers unchanged, digital range -2048..2047 and
physical endpoints rounded to the EDF eight-character fields (rounding error
stored in analysis.json). This introduces at most a few nV in the delivered
profile; WFDB and NPZ retain the unrounded scaling. One-second EDF records may
need final zero-padding for non-integral durations; padding is annotated and
reported, never analyzed. Exact 30s device segments need no padding.

ZIP input is read without extraction, with path/duplicate/size checks. Device
README and each selected SCP receive SHA-256 in the manifest. Directory symlinks outside
the input tree are rejected. The source archive does not contain private data.

The list/inventory command reads only index and boundary files. Subset conversion
validates and decodes selected sessions; an unselected corrupt payload is not
claimed to be validated and does not block selected exports.
