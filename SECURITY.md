# Security and privacy

Input ZIPs are read without extraction. Path, duplicate, file-size and format
checks reduce malformed-input risk but are not a guarantee against all hostile
inputs. CRC detects corruption, not authenticity. Run untrusted recordings in an
isolated environment with patched Python/dependencies.

All conversion is local. Optional AI transport is a separately invoked command;
remote HTTPS needs explicit opt-in. Context remains sensitive health information.
Output reports retain device timestamps and are not anonymized for publication.

For vulnerabilities, contact the maintainer through a private channel designated
by the repository owner. Do not post health data, tokens or identifying logs in
public issues. This source template intentionally does not invent a maintainer
address. Before enabling GitHub private vulnerability reporting, the repository
owner should set their actual contact process.

Algorithm misclassifications are expected research limitations, not medically
reviewed conclusions; see docs/VALIDATION.md.
