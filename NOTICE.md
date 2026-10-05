# Attribution and licensing

Easy ECG format interpretation is informed by:
https://github.com/majbthrd/easyecg2gdf
Reference revision: recorded in docs/VALIDATION.md.
Upstream: Peter Lawrence (2017); its read_scp.c credits George B. Moody and
Edna S. Moody (2000-2014). Upstream is GPL-2.0-or-later.

This implementation is newly written in Python, does not bundle the upstream
C converter, and is distributed under GPL-2.0-or-later. See LICENSE.
CRC validation uses binascii.crc_hqx from the Python standard library.
Third-party runtime libraries have their respective licenses; no vendored
binary libraries are included in the Source ZIP.

Authoring year: 2026. This software is experimental and carries no warranty.
Reports, heuristics and external AI are not clinically validated.

Bundled font resources:
- DejaVu Sans / Sans Bold: Bitstream Vera and DejaVu font licenses; see
  src/easyecg_review/fonts/DEJAVU-LICENSE.txt.
- WenQuanYi Zen Hei (0.9.45): GPL-2.0 with font embedding exception; see
  src/easyecg_review/fonts/WQY-LICENSE.txt.
Font files are redistributed unchanged. The embedding exception applies to PDFs.
