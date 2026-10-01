"""German review PDFs. Vector ECG strips with physically calibrated grids."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from collections import Counter
from xml.sax.saxutils import escape
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from .analysis import LABELS

INK=colors.HexColor('#14334B');TEAL=colors.HexColor('#007F87');MUTED=colors.HexColor('#566575')
WARNING='Experimentelle Auswertung zur ärztlichen Prüfung. Keine Diagnose; keine zuverlässige Entwarnung.'


def register_fonts():
    regular=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    bold=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    if regular.exists() and bold.exists():
        if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('DejaVu',str(regular)));pdfmetrics.registerFont(TTFont('DejaVu-Bold',str(bold)))
            pdfmetrics.registerFontFamily('DejaVu',normal='DejaVu',bold='DejaVu-Bold',italic='DejaVu',boldItalic='DejaVu-Bold')
        return 'DejaVu','DejaVu-Bold'
    return 'Helvetica','Helvetica-Bold'


def clock(rec,seconds):return (rec.start+timedelta(seconds=float(seconds))).strftime('%d.%m.%Y %H:%M:%S')
def duration(seconds):
    seconds=round(seconds);return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'
def number(v):return '-' if v is None else f'{v:.1f}'


def plot_image(fig,width=178*mm):
    buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=150,bbox_inches='tight');plt.close(fig);buffer.seek(0)
    return Image(buffer,width=width,height=width*fig.get_figheight()/fig.get_figwidth())


def aggregate(results):
    total=sum(r['summary']['duration_s'] for r in results)
    usable=sum(r['summary']['usable_s'] for r in results)
    counts=Counter()
    for result in results:counts.update(result['summary']['candidate_counts'])
    rates=[w['median_bpm'] for r in results for w in r['windows'] if w['median_bpm'] is not None]
    return {'recordings':len(results),'duration_s':total,'usable_s':usable,'excluded_s':total-usable,
            'usable_percent':100*usable/total if total else 0,'candidate_counts':dict(counts),
            'confirmed_extrasystoles':None,'rate_window_min_bpm':min(rates) if rates else None,
            'rate_window_max_bpm':max(rates) if rates else None,
            'rate_window_median_bpm':float(np.median(rates)) if rates else None}


def trend(rec,result):
    fig,axes=plt.subplots(3,1,figsize=(10,4.0),sharex=True,gridspec_kw={'height_ratios':[2,1,.6]})
    w=result['windows']; t=np.array([x['start_s']/60 for x in w]);rate=np.array([x['median_bpm'] if x['median_bpm'] else np.nan for x in w])
    axes[0].plot(t,rate,color='#007f87',lw=1)
    axes[0].set_ylabel('HF / min');axes[0].grid(alpha=.2)
    axes[0].set_title('10s-Fenster-Median; Lücken = von der Heuristik nicht auswertbar',fontsize=10)
    bins=np.arange(0,rec.duration+60,60)
    times=[e['onset_s'] for e in result['events'] if e['kind']=='premature_beat_candidate']
    counts,_=np.histogram(times,bins=bins)
    axes[1].bar(bins[:-1]/60,counts,width=1,align='edge',color='#bb3344')
    axes[1].set_ylabel('Kand./min',fontsize=9)
    axes[1].set_title('Vorzeitige Schlagmuster pro Minute (unbestätigt)',fontsize=9)
    axes[1].grid(axis='y',alpha=.2)
    quality=np.asarray([x.get('usable_fraction',float(x['usable'])) for x in w],float)
    axes[2].bar(t,quality,width=10/60,align='edge',color='#007f87',label='Zugelassen')
    axes[2].bar(t,1-quality,width=10/60,align='edge',color='#dc9b3e',label='Eingeschränkt')
    axes[2].set_ylim(0,1.2);axes[2].set_yticks([]);axes[2].set_xlabel('Minuten ab Beginn');axes[2].legend(loc='upper right',ncol=2,fontsize=8)
    fig.tight_layout();return plot_image(fig)


def summary_pdf(path,recordings,results,manifest):
    font,bold=register_fonts();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyDE',fontName=font,fontSize=9,leading=13,textColor=INK,spaceAfter=7))
    styles.add(ParagraphStyle(name='SmallDE',fontName=font,fontSize=7.5,leading=10,textColor=MUTED,spaceAfter=5))
    styles.add(ParagraphStyle(name='HeadingDE',fontName=bold,fontSize=15,leading=20,textColor=INK,spaceAfter=12))
    styles.add(ParagraphStyle(name='SubDE',fontName=bold,fontSize=11,leading=15,textColor=TEAL,spaceAfter=9))
    def p(text,style='BodyDE'):return Paragraph(text,styles[style])
    def table(rows,widths):
        rows=[[p(str(cell),'SmallDE') for cell in row] for row in rows]
        t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E6F1F3')),('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#DCE4E9')),
                               ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    agg=aggregate(results);story=[]
    story += [p('EASY ECG | Prüfbericht','HeadingDE'),p('PC-80B - Kurven, Signalqualität und unbestätigte Rhythmus-Kandidaten','SubDE'),p(WARNING),
              p('Bei akuten Brustschmerzen, Atemnot, Ohnmacht oder starkem Schwindel: 112. Bei vermuteten Herzproblemen ärztlich abklären lassen; dieser Bericht ersetzt kein 12-Kanal-EKG oder medizinisches Langzeit-EKG.')]
    story += [table([['Umfang','Wert'],['Index gesamt / ausgewertet (Teile)',f'{len(manifest["ranges"])} / {len(recordings)}'],
        ['CRC-geprüfte SCP-Dateien (Auswahl)',str(len(manifest['files']))],['Gesamte Aufzeichnungsdauer',duration(agg['duration_s'])],
        ['Heuristisch auswertbar',f'{duration(agg["usable_s"])} ({agg["usable_percent"]:.1f}%)'],
        ['Eingeschränkt / aus Zählung ausgeschlossen',duration(agg['excluded_s'])],
        ['HF (10s-Mediane), Minimum / Median / Maximum',f'{number(agg["rate_window_min_bpm"])} / {number(agg["rate_window_median_bpm"])} / {number(agg["rate_window_max_bpm"])} pro Minute']], [110*mm,68*mm]),Spacer(1,10*mm)]
    story += [p('Wichtigste Prüfaufgaben','SubDE')]
    if agg['usable_percent']<80:story.append(p('Große Teile der Daten sind für die Rhythmus-Heuristik eingeschränkt. Fehlende Ereignismarkierungen in diesen Abschnitten bedeuten keine unauffällige Herzaktivität.'))
    story.append(p(f'Bestätigte Extrasystolen: <b>nicht bestimmbar</b>. Schläge mit auffälligem RR-/Formmuster: <b>{agg["candidate_counts"].get("premature_beat_candidate",0)} Kandidaten</b>. Diese Zahl ist keine klinische Extrasystolenanzahl; Formmuster zur SVES-/VES-Sichtprüfung sind Hinweise, keine gesicherte Klassifikation.'))
    story.append(table([['Unbestätigte Ereigniskategorie','Anzahl'],*[ [LABELS[k],v] for k,v in agg['candidate_counts'].items() if k not in ('poor_signal','ventricular_pattern_candidate','narrow_premature_candidate')]], [145*mm,33*mm]))
    story.append(p('Kategorien überlappen: Form-Untergruppen, Serien und Wechselmuster sind keine zusätzlichen Extrasystolen. Nahezu flache Abschnitte werden als Signalverlust unklarer Ursache ausgewiesen und aus Rhythmuszählungen ausgeschlossen; eine echte Rhythmusursache ist damit nicht ausgeschlossen.','SmallDE'))
    story.append(p('Lange RR-Abstände können durch übersehene QRS-Komplexe entstehen. Unregelmäßigkeit beweist kein Vorhofflimmern. Hohe/niedrige Frequenz braucht Kontext (Aktivität, Schlaf, Medikamente, Symptome).','SmallDE'))
    story += [PageBreak(),p('Messreihen und Zeitbasis','HeadingDE'),p('Dateikopierzeiten werden nicht zur Synchronisation benutzt. Zeitangaben stammen aus SCP-Tag 25/26 und sind lokale Gerätezeiten ohne verifizierte Zeitzone. Aufeinanderfolgende Dateien werden nur innerhalb des README-Bereichs und bei passender Zeit/Kalibrierung zusammengefügt. Lücken bleiben als getrennte Teile erhalten.')]
    if manifest['skipped']:story.append(p(f'<b>UNVOLLSTÄNDIGER EINGANG:</b> {len(manifest["skipped"])} Dateien fehlen oder wurden verworfen. Siehe manifest.json.'))
    for warn in manifest['warnings'][:12]:story.append(p(escape(warn),'SmallDE'))
    rows=[['Nr./Teil','Beginn (Gerätezeit)','Dauer','Auswertbar','ES-Kand.']]
    for rec,r in zip(recordings,results):
        s=r['summary'];rows.append([f'{rec.index}/{rec.part}',rec.start.strftime('%d.%m.%Y %H:%M:%S'),duration(rec.duration),
            f'{100*s["usable_s"]/rec.duration:.0f}%',s['candidate_counts']['premature_beat_candidate']])
    story.append(table(rows,[17*mm,63*mm,32*mm,35*mm,31*mm]))
    for rec,result in zip(recordings,results):
        if rec.duration<=30:continue
        story += [PageBreak(),p(f'Messreihe {rec.index}, Teil {rec.part}','HeadingDE'),
                  p(f'{clock(rec,0)} bis {clock(rec,rec.duration)} | {duration(rec.duration)} | 150 Hz nominal'),trend(rec,result)]
        reasons=Counter(reason for w in result['windows'] for reason in w['reasons'])
        story.append(p('Häufige Gründe für Einschränkungen','SubDE'))
        story.append(table([['Grund','10s-Fenster'],*reasons.most_common()], [145*mm,33*mm]))
        ranked=[e for e in result['events'] if e['kind']!='poor_signal']
        if ranked:
            priority={'wide_complex_run_candidate':0,'ectopic_run_candidate':1,'long_rr_candidate':2,
                'persistent_irregular_rr_candidate':3,'signal_dropout':4,'premature_beat_candidate':5,
                'bigeminy_candidate':6,'trigeminy_candidate':7,'irregular_rr_candidate':8,
                'fast_rate_candidate':9,'slow_rate_candidate':10,'ectopic_couplet_candidate':11,'morphology_outlier_candidate':12}
            ranked=[e for e in ranked if e['kind'] not in ('ventricular_pattern_candidate','narrow_premature_candidate')]
            ranked.sort(key=lambda e:(priority.get(e['kind'],13),-e['duration_s'] if e['kind']=='signal_dropout' else e['onset_s']))
            selected=[];seen=set()
            for event in ranked:
                if event['kind'] in seen:continue
                selected.append(event);seen.add(event['kind'])
                if len(selected)==6:break
            story.append(p('Auswahl zur Sichtprüfung (alle Ereignisse in events.csv)','SubDE'))
            story.append(table([['Gerätezeit','Kandidat / Evidenz'],*[[clock(rec,e['onset_s']),LABELS[e['kind']]+'<br/>'+escape(e['evidence'])] for e in selected]], [48*mm,130*mm]))
    story += [PageBreak(),p('Methodik, Grenzen und Übergabe','HeadingDE'),
      p('Rohsignal: untere 12 Bit minus 2048; Skalierung aus SCP als nV/LSB. Die Interpretation wurde anhand easyecg2gdf und durch digitalen Export-Rücklesetest geprüft, aber nicht mit einem kalibrierten medizinischen Signalgenerator validiert. Ob die Elektrodenanordnung einer Standardableitung entspricht, ist unbekannt.'),
      p('Analyse: konfigurierbarer phasenneutraler Bandpass (Standard 0,5-40 Hz) und evidenzbasierter 50-/60-Hz-Notch. QRS: WFDB XQRS, NeuroKit2 und SWT; zeitliche Abstimmung, Form-/Amplitudenprüfung und Refraktärabstand. Mindestens zwei Detektoren müssen Rhythmusschläge stützen. Clipping, Basislinienbewegung, Signalstufen, Hochfrequenzstörung und Unstimmigkeit sperren 10s-Fenster. Erste/letzte 2s und nahezu flache Teilabschnitte werden zusätzlich ausgeschlossen. Übereinstimmung beweist keine korrekte Erkennung.'),
      p('Schlag-Kandidat: lokale RR-Referenz ohne Anforderung an fünf regelmäßige Nachbarintervalle; vorzeitiges RR-Muster oder deutliche Formabweichung mit Zeitstützung. Nicht-kompensierte vorzeitige Schläge werden berücksichtigt. Formkorrelation und Energiebreite sind technische Merkmale; die Energiebreite ist keine klinisch gemessene QRS-Dauer. Zusätzlich: Paare, Serien, Bigeminus-/Trigeminus-Muster und mindestens 90s anhaltende RR-Unregelmäßigkeit. Physiologische Variabilität, T-Wellen und Artefakte können weiterhin Fehlmarkierungen und übersehene Ereignisse verursachen.'),
      p('Langer RR: mindestens 2,0 s in auswertbarem Bereich. Hohe HF: 10s-Median &gt; 100/min; niedrige HF: &lt; 50/min. RR-Unregelmäßigkeit: 30s-Fenster, CV &gt; 0,18 und RR-RMSSD &gt; 0,12 s. Schwellen dienen nur der Auswahl von Prüfstellen. Konfiguration und Filterevidenz sind in analysis.json gespeichert.'),
      p('Öffentliche MIT-BIH-Ausschnitte prüfen Erkennung gegen Beat-Annotationen; diese begrenzten Entwicklungstests validieren keine medizinische Zuverlässigkeit und keine Bewegungsartefakte am PC-80B. Ergebnisse und Testbedingungen stehen in docs/VALIDATION.md.'),
      p('Keine validierte Beurteilung von Herzinfarkt/Ischämie, ST-Strecken, QT/QTc, Leitungsblöcken, Schrittmacherfunktion oder sicherer AF-/VT-/SVES-/VES-Klassifikation. Eine unauffällige Markierungsliste schließt Herzprobleme nicht aus.'),
      p(f'PDF-Verstärkung: Faktor {manifest.get("display",{}).get("gain_factor",2):g}; Prüfstreifen {manifest.get("display",{}).get("review_mm_per_mv",20):g} mm/mV. Nur Darstellung; Rohdaten und deren mV-Kalibrierung bleiben unverändert. Begrenzte Panelhöhe kann hohe Ausschläge abschneiden, was am Streifen vermerkt wird.'),
      p('Für den Arzt: summary.pdf, review_strips.pdf, optional full_curves.pdf und die EDF+-Dateien übergeben. Dazu Symptome und Zeitpunkt, Elektrodenposition, Medikamente und Aktivität notieren. EDF+ ist ein offenes Austauschformat; Import in das konkrete Praxis-/Holter-System vorher klären.'),
      p('Ungefilterte Kurven werden in EDF+/WFDB exportiert. raw.npz bewahrt alle originalen 16-Bit-Wörter einschließlich oberer Statusbits. Deren Bedeutung ist unbekannt; die Bits werden nicht als Diagnosen interpretiert. SHA-256 und Gerätezeiten je SCP stehen in manifest.json.'),
      p('KI: optionale lokale, dateibasierte Schnittstelle mit exportiertem Kontext. Kein automatischer Upload. Ein allgemeines Sprachmodell ist kein validierter EKG-Befunder. KI-Texte bleiben gesondert und zählen nie als bestätigte Ereignisse.'),
      p('Quellen','SubDE'),p('Format: github.com/majbthrd/easyecg2gdf<br/>EDF+: edfplus.info/specs/edfplus.html<br/>WFDB: wfdb.readthedocs.io<br/>NeuroKit2: neuropsychology.github.io/NeuroKit/<br/>Viewer: teuniz.net/edfbrowser/<br/>Notfallhinweis: nhs.uk/symptoms/heart-palpitations/','SmallDE')]
    def footer(c,doc):
        c.setStrokeColor(TEAL);c.line(16*mm,14*mm,194*mm,14*mm)
        c.setFont(font,7);c.setFillColor(MUTED);c.drawString(16*mm,10*mm,'EASY ECG | Unbestätigte automatische Prüfhinweise');c.drawRightString(194*mm,10*mm,f'Seite {doc.page}')
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=17*mm,bottomMargin=21*mm,
        title='Easy ECG - experimenteller Prüfbericht',author='easyecg-review').build(story,onFirstPage=footer,onLaterPages=footer)


def draw_strip(c,rec,result,start_s,y,seconds=10,speed_mm_s=25,gain_mm_mv=20,filtered=None,markers=True,raw_mv=None,half_height_mm=34):
    font,bold=register_fonts(); x0=27*mm;width=seconds*speed_mm_s*mm
    half=half_height_mm*mm
    c.setStrokeColor(colors.HexColor('#F3DFDF'));c.setLineWidth(.12)
    gx=mm
    for xpos in np.arange(x0,x0+width+gx/2,gx):c.line(xpos,y-half,xpos,y+half)
    for yy in np.arange(y-half,y+half+gx/2,gx):c.line(x0,yy,x0+width,yy)
    c.setStrokeColor(colors.HexColor('#E6BBBB'));c.setLineWidth(.28)
    for xpos in np.arange(x0,x0+width+.1,5*mm):c.line(xpos,y-half,xpos,y+half)
    for yy in np.arange(y-5*np.floor(half_height_mm/5)*mm,y+half+.1,5*mm):
        if yy>=y-half:c.line(x0,yy,x0+width,yy)
    fs=rec.fs
    data=(rec.raw.astype(float)*rec.scale if raw_mv is None else raw_mv) if filtered is None else filtered
    lo=int(start_s*fs);hi=min(len(data),int((start_s+seconds)*fs))
    if hi>lo:
        c.saveState();clip=c.beginPath();clip.rect(x0,y-half,width,2*half);c.clipPath(clip,stroke=0,fill=0)
        path=c.beginPath();path.moveTo(x0,y+data[lo]*gain_mm_mv*mm)
        for i in range(lo+1,hi):path.lineTo(x0+(i-lo)/fs*speed_mm_s*mm,y+data[i]*gain_mm_mv*mm)
        c.setStrokeColor(INK);c.setLineWidth(.45);c.drawPath(path)
        if markers:
            for b in result['beats']:
                if start_s<=b['time_s']<start_s+seconds:
                    xx=x0+(b['time_s']-start_s)*speed_mm_s*mm
                    c.setFillColor(TEAL if b['usable'] else MUTED);c.circle(xx,y+half-2*mm,.5*mm,stroke=0,fill=1)
            for e in result['events']:
                if e['kind']=='premature_beat_candidate' and start_s<=e['onset_s']<start_s+seconds:
                    xx=x0+(e['onset_s']-start_s)*speed_mm_s*mm;c.setStrokeColor(colors.red);c.line(xx,y-half,xx,y+half)
        c.restoreState()
    c.setFont(font,7);c.setFillColor(MUTED);c.drawString(x0,y+half+1.3*mm,clock(rec,start_s)+f' | t={start_s:.1f}s | '+('ROH' if filtered is None else 'GEFILTERT; Details in analysis.json'))
    clipped=int(np.count_nonzero(abs(data[lo:hi])*gain_mm_mv>half_height_mm))
    notice=f' | {clipped} Samples außerhalb Panel' if clipped else ''
    c.setFont(font,6);c.drawRightString(x0+width,y-half-2.5*mm,f'{speed_mm_s:g} mm/s | {gain_mm_mv:g} mm/mV | 100% drucken'+notice)
    if clipped:
        c.setFillColor(colors.red);c.drawString(x0,y-half-2.5*mm,'Ausschläge abgeschnitten: EDF+ prüfen')
    # A true 1mV calibration pulse at the left of every strip.
    c.setStrokeColor(INK);c.setLineWidth(.5)
    pulse_mv=1. if gain_mm_mv<=half_height_mm else .25
    c.setFont(font,5);c.drawString(x0-9*mm,y-3*mm,f'{pulse_mv:g}mV')
    path=c.beginPath();path.moveTo(x0-7*mm,y);path.lineTo(x0-6*mm,y);path.lineTo(x0-6*mm,y+gain_mm_mv*pulse_mv*mm)
    path.lineTo(x0-3*mm,y+gain_mm_mv*pulse_mv*mm);path.lineTo(x0-3*mm,y);path.lineTo(x0-2*mm,y);c.drawPath(path)


def select_strips(rec,result,max_per_kind=3):
    chosen=[(max(0,min(rec.duration-10,rec.duration/2-5)),'Repräsentative Mitte (keine Normalitätsaussage)')]
    for kind in LABELS:
        events=[e for e in result['events'] if e['kind']==kind and not (kind=='poor_signal' and e['evidence']=='Aufnahmerand/Filterrand')]
        if kind=='long_rr_candidate':events.sort(key=lambda e:-e['duration_s'])
        if kind=='poor_signal':events.sort(key=lambda e:-e['duration_s'])
        for e in events[:max_per_kind]:
            start=max(0,min(rec.duration-10,e['onset_s']-3))
            if all(abs(start-s)>3 for s,_ in chosen):chosen.append((start,LABELS[kind]+' | '+e['evidence']))
    return chosen


def strips_pdf(path,recordings,results,filtered_signals,max_per_kind=3,gain_factor=2.):
    font,bold=register_fonts();c=canvas.Canvas(str(path),pagesize=landscape(A4),pageCompression=1)
    c.setTitle('Easy ECG - ausgewählte Prüfstreifen');page=0
    for rec,result,filtered in zip(recordings,results,filtered_signals):
        raw_mv=rec.raw.astype(float)*rec.scale
        for start,label in select_strips(rec,result,max_per_kind):
            page+=1;c.setFont(bold,13);c.setFillColor(INK);c.drawString(16*mm,194*mm,f'Messreihe {rec.index}, Teil {rec.part} | Prüfstreifen')
            c.setFont(font,8);c.drawString(16*mm,187*mm,WARNING)
            paragraph=Paragraph(escape(label),ParagraphStyle(name='StripLabel',fontName=font,fontSize=7.5,leading=10,textColor=MUTED))
            _, h=paragraph.wrap(265*mm,12*mm)
            paragraph.drawOn(c,16*mm,182*mm-h)
            draw_strip(c,rec,result,start,135*mm,filtered=None,raw_mv=raw_mv,gain_mm_mv=10*gain_factor)
            draw_strip(c,rec,result,start,59*mm,filtered=filtered,gain_mm_mv=10*gain_factor)
            c.setFont(font,8);c.setFillColor(MUTED)
            c.drawString(16*mm,18*mm,'Punkte: unbestätigte QRS; grün = zur Heuristik zugelassen, grau = ausgeschlossen.')
            c.drawString(16*mm,13*mm,'Rote Linie: vorzeitiger Schlag-Kandidat. Gefilterte Kurve nur zur Sichtprüfung, keine ST/QT-Befundung.')
            c.drawString(16*mm,7*mm,f'Dateien: {rec.blocks[0].number}.SCP bis {rec.blocks[-1].number}.SCP | Gerätedatum/Zeitzone nicht extern geprüft.')
            c.drawRightString(281*mm,7*mm,f'Seite {page}');c.showPage()
    c.save()


def full_pdf(path,recordings,results,gain_factor=2.):
    """All raw samples. Calibrated overview at half review speed/gain."""
    font,bold=register_fonts();c=canvas.Canvas(str(path),pagesize=landscape(A4),pageCompression=1);page=0
    for rec,result in zip(recordings,results):
        raw_mv=rec.raw.astype(float)*rec.scale
        for start in range(0,int(np.ceil(rec.duration)),80):
            page+=1;c.setFont(bold,12);c.setFillColor(INK);c.drawString(16*mm,197*mm,f'Messreihe {rec.index}/{rec.part} | Vollständige Rohkurve | {clock(rec,start)}')
            c.setFont(font,7);c.drawString(16*mm,190*mm,f'Übersicht: 12,5 mm/s und {5*gain_factor:g} mm/mV. Alle Samples; ungefiltert. Für Details EDF+ / Prüfstreifen nutzen.')
            for i in range(4):
                if start+i*20>=rec.duration:break
                draw_strip(c,rec,result,start+i*20,(165-i*42)*mm,seconds=20,speed_mm_s=12.5,gain_mm_mv=5*gain_factor,markers=False,raw_mv=raw_mv,half_height_mm=18)
            c.setFont(font,7);c.setFillColor(MUTED);c.drawString(16*mm,10*mm,WARNING);c.drawRightString(281*mm,10*mm,f'Seite {page}');c.showPage()
    c.save()
