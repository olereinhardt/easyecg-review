# Localization (0.3.0)

The desktop interface, CLI descriptions/progress, common application errors,
PDF summary/review/full-curve reports, event names, quality explanations and
optional AI response language support 18 languages.

| Code | Language | Variant |
| --- | --- | --- |
| de | German | Deutsch |
| en | English | English |
| fr | French | Français |
| es | Spanish | Español |
| pt | Portuguese | European Portuguese; regional aliases map to pt |
| zh | Chinese | Simplified Chinese |
| ja | Japanese | 日本語 |
| ru | Russian | Русский |
| tr | Turkish | Türkçe |
| nl | Dutch | Nederlands |
| it | Italian | Italiano |
| ar | Arabic | Modern Standard Arabic; RTL text |
| uk | Ukrainian | Українська |
| pl | Polish | Polski |
| cs | Czech | Čeština |
| da | Danish | Dansk |
| sv | Swedish | Svenska |
| nb | Norwegian | Bokmål; no is an alias |

## Select a language

```sh
easyecg gui --language de
easyecg run INPUT.zip -o OUTPUT --recordings 64 --language fr
easyecg --language ja run INPUT.zip -o OUTPUT
easyecg ai-review OUTPUT/ai_context.json --model MODEL \
  -o OUTPUT/ai-review.md --language en
```

The UI has a language selector. Switching language updates labels, table headers,
status and inventory descriptions, preserving paths, options and selection.
The selected language is frozen while conversion runs, and passed explicitly to
the processing subprocess. Each run produces reports in one language.
Language is saved in `$XDG_CONFIG_HOME/easyecg-review/settings.json`, or
`~/.config/easyecg-review/settings.json`. Application preference precedence:
explicit `--language`, `EASYECG_LANGUAGE`, saved preference, `LC_ALL`,
`LC_MESSAGES`, `LANG`, then German. Regional codes such as `fr_FR.UTF-8`,
`pt-BR`, `zh-CN` and `no_NO` are normalized. Chinese variants currently all
resolve to Simplified Chinese; Traditional Chinese is not a separate catalog.
An explicitly unsupported language is rejected. An unrecognized system locale
falls back to German. The application never changes the process-wide OS locale.

## Translation catalogs

`src/easyecg_review/locales/<code>.json` contains 149 semantic message keys.
All delivered catalogs contain every key. Named placeholders, such as `{count}`,
`{index}`, `{part}`, `{page}`, `{gain}`, `{mm}` and `{details}`, must be retained.
UTF-8 plain text is used; HTML is not executed. At runtime, a missing key falls
back to English; an unknown key raises an error rather than showing a key name.
To add a language, copy en.json, translate every value, register its native name
and AI language in i18n.py, then run the catalog/font/export tests. Catalogs and
font resources are included in both wheel and source distribution.

Clinical terminology translations are development translations and have not
been reviewed by native-speaking clinicians. Clinical use still requires review
of the raw ECG and the original analysis limitations. The software remains
experimental and is not a diagnostic medical device.

## PDF and UI fonts

PDFs embed bundled DejaVu Sans and WenQuanYi Zen Hei, including Unicode maps.
Arabic is shaped and reordered **after line wrapping**, with RTL alignment.
The ECG time axis always runs left to right, regardless of text language. CJK
paragraphs support character-based line breaks. Charts use the same bundled
fonts; narrow canvas labels are fitted to their available width.

On Linux with standard Tk/Xft, the application registers bundled fonts privately
with Fontconfig; it does not install system fonts. The UI chooses DejaVu Sans or
WenQuanYi Zen Hei. Arabic UI labels are explicitly shaped for Tk 8.6. Install
`python3-tk` if Tk is absent. A custom Tk build using only X11 core bitmap fonts
cannot display all scripts; use the distribution's standard Tk/Xft build.
On other operating systems, Tk may need an installed CJK/Arabic font. PDF font
embedding works independently of installed desktop fonts. Windows/macOS GUI
font behavior has not been tested in this release.

## Stable technical data

Language affects presentation and the optional AI response request, not analysis
thresholds, detections, calibrated samples or event categories. EDF+/WFDB
annotations, CSV headers, JSON field names and timestamps retain their stable
technical representations. Scientific metric labels (RR, CV, RMSSD, correlation,
energy-width) use fixed identifiers and decimal points.

Detailed parser exceptions, dependency errors, original import warnings and
verbatim evidence in analysis.json/events.csv remain audit diagnostics in their
original technical wording. PDF event descriptions and quality reasons are
translated; quantitative evidence is extracted with stable metric identifiers.
Argparse's standard framework diagnostics/headings use its standard English
wording. CLI argument names and commands remain stable.

manifest.json records `language`, catalog SHA-256, software version and source
module hashes. Local AI output headings are translated and the prompt requests
the selected response language; an external model may ignore that request.
No AI service is contacted by changing language or by normal conversion.

## Reproduce the synthetic PDF preview

From the unpacked source tree, with development dependencies installed:

```sh
python tools/localization_preview.py -o language-preview.pdf
```

This produces one combined preview with an overview, methodology, trend and
review strip in each language. All ECG data are synthetic. No recordings are
read from your device and no external service is contacted.
