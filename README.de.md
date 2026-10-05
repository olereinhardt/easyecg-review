# Easy ECG Review – deutsche Anleitung

Lokale Datenformat Umwandlung und Auswertesoftware für das **Lepu Medical Creative PC-80B Easy ECG** handheld EKG.

Version **0.3.0**: PC-80B-Gerätearchiv lokal lesen, einzelne Messreihen auswählen,
ungefiltertes EDF+/WFDB exportieren und deutsche PDF-Prüfberichte erzeugen.
Die vollständige Projektbeschreibung mit Links und Veröffentlichungshinweisen
steht im [englischen README](README.md).

Diese Software wurde mit KI durch ChatGPT entwickelt. Sie ist nicht als Medizin Software, 
sondern als praktisches Tool für alle Besitzer des PC-80B zum konvertieren und Anzeigen 
der Datensätze und einfachere Kontrolle durch einen Arzt gedacht.

**Experimentelle Auswertung, keine Diagnose.** Kandidaten können falsch sein,
echte Ereignisse fehlen. Die Software liefert keine sichere Extrasystolenanzahl
und keine Entwarnung. Auffällige Kurven ärztlich beurteilen lassen.

## Installation und Oberfläche

```bash
sudo apt install python3-venv python3-tk
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
easyecg gui
```

1. ZIP oder Geräteordner wählen; bei manueller Pfadeingabe „Messreihen laden“.
2. In der Tabelle gewünschte Reihen markieren (Strg/Umschalt für Mehrfachauswahl).
   „Alle auswählen“ und „Keine auswählen“ sind ebenfalls verfügbar.
3. Neuen oder leeren Ausgabeordner wählen.
4. Verstärkung und Netzfilter einstellen; bei Bedarf vollständiges Kurven-PDF aktivieren.
5. „Ausgewählte Messreihen konvertieren“ starten.

Die Auswahl bleibt an den geladenen Eingang gebunden. Nach einer Pfadänderung
muss das Inventar neu geladen werden. Eine leere Auswahl startet keine Konvertierung.
Das Inventar prüft Index sowie Anfangs-/Enddatei; alle ausgewählten SCP-Dateien
werden erst beim Konvertieren vollständig geprüft. Fehler in nicht ausgewählten
Reihen verhindern den gezielten Export einer gültigen Reihe nicht.

## Verstärkung und Filter

**Standardfaktor 2** verdoppelt die bisherige PDF-Darstellung: Prüfstreifen
20 mm/mV bei 25 mm/s, Vollübersicht 10 mm/mV bei 12,5 mm/s. Faktor 1 entspricht
Version 0.1. Erlaubt sind 0,25–8. EDF+/WFDB/NPZ bleiben unverändert kalibriert.
Hohe Ausschläge außerhalb der festen Panelhöhe werden am Streifen kenntlich
gemacht. Für die maßstäbliche Papierdarstellung mit 100% ohne Seitenanpassung drucken.

Analysefilter: phasenneutraler Bandpass, standardmäßig 0,5–40 Hz. Netzfilter
`auto` prüft 50/60-Hz-Evidenz; alternativ `off`, `50`, `60`. Filter betreffen nur
Analyse und gefilterte Sichtkurve. Parameter und Evidenz stehen in `analysis.json`.

```bash
easyecg list '/pfad/geraet.zip'
easyecg run '/pfad/geraet.zip' -o '/pfad/auswertung' \
  --recordings 1 2 --gain-factor 2 --notch auto --full-curves
# Alle Reihen: --recordings weglassen.
```

## Ergebnisse und Grenzen

`summary.pdf` enthält Umfang, Signalqualität, Kandidaten, Trends und Prüfaufgaben.
`review_strips.pdf` zeigt ausgewählte Roh-/Filterkurven; `full_curves.pdf` zeigt
optional sämtliche Rohsamples. EDF+ und WFDB liegen je Messreihe/Teil vor.
CSV/JSON enthalten sämtliche QRS, Belege und Qualitätsparameter; `raw.npz` erhält
auch die unbekannten oberen Statusbits des Geräts.

Die neue Erkennung kombiniert XQRS, NeuroKit2 und SWT, gleicht QRS-Positionen ab
und prüft RR-/Formmerkmale. Sie berücksichtigt häufige Wechselmuster und manche
vorzeitigen Schläge ohne kompensatorische Pause. Zusätzliche Prüfhinweise:
Couplets, Serien, Bigeminus/Trigeminus, schnelle Serien abweichender Komplexe,
lange RR-Abstände, hohe/niedrige Frequenz und anhaltende RR-Unregelmäßigkeit.
SVES-/VES-Formgruppen sind **keine gesicherte Klassifikation**. Die technische
Energiebreite ist keine klinische QRS-Dauer. Kategorien überlappen und dürfen
nicht zu einer Extrasystolensumme addiert werden.

Nahezu flache Abschnitte erscheinen als **Signalverlust mit unklarer Ursache**,
mit möglichem Kontakt-/Messproblem. Sie werden aus der Rhythmus-/Pausenzählung
ausgeschlossen. Eine echte Rhythmusursache wird dadurch nicht ausgeschlossen.
ST/Ischämie, QT/QTc, Schrittmacher und sichere AF-/VT-/SVES-/VES-Diagnostik sind
nicht implementiert. Auch drei übereinstimmende Detektoren können irren.

Für Linux ist [EDFbrowser](https://www.teuniz.net/edfbrowser/) der empfohlene
erste Viewer; WFDB kann mit [WAVE](https://physionet.org/physiotools/wag/wave-1.htm)
angesehen werden. Das ursprüngliche Formatprojekt ist
[easyecg2gdf](https://github.com/majbthrd/easyecg2gdf).
Weitere Links: [Viewer/Arztsoftware](docs/TOOLS.md),
[Methoden](docs/METHODS.md), [Testergebnisse](docs/VALIDATION.md).

Zur Arztübergabe Übersicht, Prüfstreifen, EDF+ sowie Symptome mit Uhrzeit,
Aktivität und Elektrodenposition mitnehmen. EDF+-Import vorher mit der Praxis
klären; Gerätezeit/Zeitzone und Einzelableitung sind nicht extern verifiziert.

Die optionale KI-Schnittstelle bleibt ein gesonderter lokaler Ollama-Aufruf;
keine automatische Datenübertragung. KI-Texte sind unvalidiert und ändern keine
Zählungen. Anleitung und Datenschutzgrenzen im englischen README.

Quellpaket, Build-Dateien, Tests, englische Commit-Vorschläge, GPL-Lizenz und
GitHub-Workflow liegen bei. Persönliche Aufnahmen/Berichte gehören nicht ins
öffentliche Repository. Bei Abbruch zeigt `manifest.json` fertige Reihen; in einen
neuen Ordner mit verbleibenden IDs neu starten. Details: [Recovery](docs/RECOVERY.md).


## Sprachwahl ab Version 0.3.0

Oberfläche und PDF-Berichte unterstützen Deutsch, Englisch, Französisch,
Spanisch, Portugiesisch, vereinfachtes Chinesisch, Japanisch, Russisch, Türkisch,
Niederländisch, Italienisch, Arabisch, Ukrainisch, Polnisch, Tschechisch, Dänisch,
Schwedisch und Norwegisch Bokmål. Im UI lässt sich die Sprache umschalten und
wird gespeichert. Alternativ:

```sh
easyecg gui --language de
easyecg run INPUT.zip -o OUTPUT --recordings 64 --language fr
```

Die 18 UTF-8-Sprachdateien liegen unter `src/easyecg_review/locales/`.
PDF-Schriften sind mitgeliefert und werden eingebettet, einschließlich arabischer
Schriftformung und Schreibrichtung. Messwerte und technische Exportcodes bleiben
stabil. Einzelheiten und Hinweise zum Ergänzen von Sprachen stehen in
[docs/LOCALIZATION.md](docs/LOCALIZATION.md). Medizinische Übersetzungen sind noch
nicht durch muttersprachliche Ärzte geprüft.
