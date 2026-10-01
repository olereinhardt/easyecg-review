# Viewing / physician workflows (checked 2026-10-01)

| Tool | Platform / purpose | Export to use |
| --- | --- | --- |
| EDFbrowser | Open-source GUI, Linux/Windows; EDF+, ECG display, annotations, filtering, QRS/RR tools | `.edf` |
| PhysioNet WAVE | Open-source X11 waveform viewer and annotation editor | WFDB `.hea` + `.dat` + `.qrs` |
| WFDB Python | Open-source scientific reading, plotting, detection, benchmarking | WFDB |
| BioSig / SigViewer | Open-source biosignal ecosystem; relevant to upstream GDF workflow | Ask about supported version/formats; this implementation exports EDF+/WFDB |
| GE HealthCare CardioDay | Clinical Holter analysis ecosystem, linked to supported recorders/monitors | Ask practice/vendor about foreign data import |
| SCHILLER medilog DARWIN2 | Clinical Holter analysis, depending on installed edition/workflow | Ask practice/vendor about foreign data import |

For local Linux review, **EDFbrowser** is the easiest first choice. Open an EDF+
file from its recording folder, select the ECG channel and inspect annotations.
No additional signal filter is applied by this exporter. If a viewer applies a
filter, record the settings and also inspect raw ECG. Its generic SCP converter
is not assumed to support this device's unusual raw format and custom index.

Do not assume every cardiology practice can import EDF+ into its normal Holter
system. Clinical products often use manufacturer-specific recorder formats.
Offer PDFs for immediate visual review, EDF+ for compatible readers, and the
original device data/software if requested. Ask which format they accept before
relying on an automated import. ISHNE, DICOM waveform and a general SCP-ECG writer
are not implemented; valid conversion would need additional metadata and testing.

WFDB example:

```python
import wfdb
record = wfdb.rdrecord('auswertung/r.../r...')  # path without extension
wfdb.plot_wfdb(record=record, title='Unfiltered PC-80B ECG')
```

Sources:
* https://www.teuniz.net/edfbrowser/
* https://www.teuniz.net/edfbrowser/EDFbrowser%20manual.html
* https://physionet.org/physiotools/wag/wave-1.htm
* https://wfdb.readthedocs.io/en/latest/processing.html
* https://biosig.sourceforge.net/
* https://github.com/cbrnr/sigviewer
* https://www.gehealthcare.com/en-gb/products/diagnostic-cardiology/ambulatory-ecg/cardioday-holter-ecg-software
* https://www.schiller.ch/de/products/medilog-darwin2-p198
* https://www.edfplus.info/specs/edfplus.html
* https://github.com/majbthrd/easyecg2gdf
