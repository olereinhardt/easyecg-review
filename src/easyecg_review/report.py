"""Localized review PDFs. Vector ECG strips with physically calibrated grids."""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from collections import Counter
from xml.sax.saxutils import escape
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['axes.unicode_minus']=False
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib.font_manager import FontProperties
from .analysis import LABELS
from .i18n import tr,reason_text,event_evidence,get_language
from .pdftext import register_fonts,Text,line,visual,font_path

INK=colors.HexColor('#14334B');TEAL=colors.HexColor('#007F87');MUTED=colors.HexColor('#566575')
WARNING='Experimentelle Auswertung zur ärztlichen Prüfung. Keine Diagnose; keine zuverlässige Entwarnung.'


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
    prop=FontProperties(fname=font_path())
    fig,axes=plt.subplots(3,1,figsize=(10,4.0),sharex=True,gridspec_kw={'height_ratios':[2,1,.6]})
    w=result['windows']; t=np.array([x['start_s']/60 for x in w]);rate=np.array([x['median_bpm'] if x['median_bpm'] else np.nan for x in w])
    axes[0].plot(t,rate,color='#007f87',lw=1)
    axes[0].set_ylabel(visual(tr('hr_axis')));axes[0].grid(alpha=.2)
    axes[0].set_title(visual(tr('trend_title')),fontsize=10)
    bins=np.arange(0,rec.duration+60,60)
    times=[e['onset_s'] for e in result['events'] if e['kind']=='premature_beat_candidate']
    counts,_=np.histogram(times,bins=bins)
    axes[1].bar(bins[:-1]/60,counts,width=1,align='edge',color='#bb3344')
    axes[1].set_ylabel(visual(tr('candidate_axis')),fontsize=9)
    axes[1].set_title(visual(tr('candidate_trend')),fontsize=9)
    axes[1].grid(axis='y',alpha=.2)
    quality=np.asarray([x.get('usable_fraction',float(x['usable'])) for x in w],float)
    axes[2].bar(t,quality,width=10/60,align='edge',color='#007f87',label=visual(tr('usable')))
    axes[2].bar(t,1-quality,width=10/60,align='edge',color='#dc9b3e',label=visual(tr('restricted')))
    axes[2].set_ylim(0,1.2);axes[2].set_yticks([]);axes[2].set_xlabel(visual(tr('minutes')));axes[2].legend(loc='upper right',ncol=2,fontsize=8)
    for ax in axes:
        for item in [ax.title,ax.xaxis.label,ax.yaxis.label,*ax.get_xticklabels(),*ax.get_yticklabels()]:item.set_fontproperties(prop)
    axes[2].legend(loc='upper right',ncol=2,prop=prop)
    fig.tight_layout();return plot_image(fig)


def summary_pdf(path,recordings,results,manifest):
    font,bold=register_fonts()
    def p(text,heading=False,small=False):return Text(text,size=15 if heading else 7.5 if small else 9,bold=heading,color=TEAL if heading else INK)
    def table(rows,widths):
        cells=[[p(cell,small=True) for cell in row] for row in rows]
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E6F1F3')),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,0),(-1,0),.7,TEAL),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#DCE4E9')),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    agg=aggregate(results)
    story=[p(tr('pdf_title'),True),p(tr('heading')),p(tr('warning')),p(tr('emergency'))]
    story.append(table([[tr('scope'),tr('value')],[tr('recording_count'),f'{len(manifest["ranges"])} / {len(recordings)}'],
        [tr('crc'),len(manifest['files'])],[tr('duration'),duration(agg['duration_s'])],
        [tr('usable'),f'{duration(agg["usable_s"])} ({agg["usable_percent"]:.1f}%)'],
        [tr('excluded'),duration(agg['excluded_s'])],[tr('rate'),f'{number(agg["rate_window_min_bpm"])} / {number(agg["rate_window_median_bpm"])} / {number(agg["rate_window_max_bpm"])} /min']], [110*mm,68*mm]))
    story += [Spacer(1,5*mm),p(tr('review_tasks'),True),p(tr('candidate_summary',count=agg['candidate_counts'].get('premature_beat_candidate',0)))]
    story.append(table([[tr('category'),tr('count')],*[[tr(k),v] for k,v in agg['candidate_counts'].items() if k not in ('poor_signal','ventricular_pattern_candidate','narrow_premature_candidate')]], [145*mm,33*mm]))
    story += [p(tr('limitations'),small=True),PageBreak(),p(tr('recordings'),True),p(tr('time_basis'))]
    if manifest['skipped']:story.append(p(tr('incomplete',count=len(manifest['skipped']))))
    # Exact import warnings are audit diagnostics, retained verbatim.
    for warn in manifest['warnings'][:12]:story.append(p(warn,small=True))
    rows=[[tr('id'),tr('start'),tr('duration'),tr('usable'),tr('count')]]
    for rec,r in zip(recordings,results):
        rows.append([f'{rec.index}/{rec.part}',clock(rec,0),duration(rec.duration),f'{100*r["summary"]["usable_s"]/rec.duration:.0f}%',r['summary']['candidate_counts']['premature_beat_candidate']])
    story.append(table(rows,[17*mm,63*mm,32*mm,35*mm,31*mm]))
    for rec,result in zip(recordings,results):
        if rec.duration<=30:continue
        story += [PageBreak(),p(tr('recording',index=rec.index,part=rec.part),True),p(f'{clock(rec,0)} - {clock(rec,rec.duration)} | {duration(rec.duration)} | {rec.fs:g} Hz'),trend(rec,result)]
        reasons=Counter(reason_text(reason) for w in result['windows'] for reason in w['reasons'])
        story += [p(tr('reasons'),True),table([[tr('reason'),tr('windows')],*reasons.most_common()],[145*mm,33*mm])]
        ranked=[e for e in result['events'] if e['kind'] not in ('poor_signal','ventricular_pattern_candidate','narrow_premature_candidate')]
        priority={'wide_complex_run_candidate':0,'ectopic_run_candidate':1,'long_rr_candidate':2,'persistent_irregular_rr_candidate':3,'signal_dropout':4,'premature_beat_candidate':5}
        ranked.sort(key=lambda e:(priority.get(e['kind'],6),-e['duration_s'] if e['kind']=='signal_dropout' else e['onset_s']))
        selected=[];seen=set()
        for e in ranked:
            if e['kind'] in seen:continue
            selected.append(e);seen.add(e['kind'])
            if len(selected)==6:break
        if selected:story += [p(tr('selected_events'),True),table([[tr('start'),tr('evidence')],*[[clock(rec,e['onset_s']),tr(e['kind'])+'\n'+event_evidence(e)] for e in selected]],[48*mm,130*mm])]
    story += [PageBreak(),p(tr('methods'),True)]
    for key in ('method_filter','method_rhythm','method_limits','handover'):story.append(p(tr(key)))
    display=manifest.get('display',{})
    story += [p(tr('pdf_gain',gain=f'{display.get("gain_factor",2):g}',mm=f'{display.get("review_mm_per_mv",20):g}')),p(tr('sources'),True),
        p('github.com/majbthrd/easyecg2gdf\nedfplus.info/specs/edfplus.html\nwfdb.readthedocs.io\nneuropsychology.github.io/NeuroKit/\nteuniz.net/edfbrowser/',small=True)]
    def footer(c,doc):
        c.setStrokeColor(TEAL);c.line(16*mm,14*mm,194*mm,14*mm);c.setFillColor(MUTED)
        line(c,16*mm,10*mm,tr('footer'),150*mm,size=7)
        line(c,169*mm,10*mm,tr('page',page=doc.page),25*mm,size=7,right=True)
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=17*mm,bottomMargin=21*mm,
        title=tr('pdf_title'),author='easyecg-review').build(story,onFirstPage=footer,onLaterPages=footer)


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
    c.setFillColor(MUTED);line(c,x0,y+half+1.3*mm,clock(rec,start_s)+f' | t={start_s:.1f}s | '+tr('raw' if filtered is None else 'filtered'),width,size=7)
    clipped=int(np.count_nonzero(abs(data[lo:hi])*gain_mm_mv>half_height_mm))
    notice=' | '+tr('outside',count=clipped) if clipped else ''
    line(c,x0+50*mm,y-half-2.5*mm,f'{speed_mm_s:g} mm/s | {gain_mm_mv:g} mm/mV | '+tr('print')+notice,width-50*mm,size=6,right=True)
    if clipped:
        c.setFillColor(colors.red);line(c,x0,y-half-2.5*mm,tr('clipped'),49*mm,size=6)
    # A true 1mV calibration pulse at the left of every strip.
    c.setStrokeColor(INK);c.setLineWidth(.5)
    pulse_mv=1. if gain_mm_mv<=half_height_mm else .25
    c.setFont(font,5);c.drawString(x0-9*mm,y-3*mm,f'{pulse_mv:g}mV')
    path=c.beginPath();path.moveTo(x0-7*mm,y);path.lineTo(x0-6*mm,y);path.lineTo(x0-6*mm,y+gain_mm_mv*pulse_mv*mm)
    path.lineTo(x0-3*mm,y+gain_mm_mv*pulse_mv*mm);path.lineTo(x0-3*mm,y);path.lineTo(x0-2*mm,y);c.drawPath(path)


def select_strips(rec,result,max_per_kind=3):
    chosen=[(max(0,min(rec.duration-10,rec.duration/2-5)),tr('representative'))]
    for kind in LABELS:
        events=[e for e in result['events'] if e['kind']==kind and not (kind=='poor_signal' and e['evidence']=='Aufnahmerand/Filterrand')]
        if kind=='long_rr_candidate':events.sort(key=lambda e:-e['duration_s'])
        if kind=='poor_signal':events.sort(key=lambda e:-e['duration_s'])
        for e in events[:max_per_kind]:
            start=max(0,min(rec.duration-10,e['onset_s']-3))
            if all(abs(start-s)>3 for s,_ in chosen):chosen.append((start,tr(kind)+' | '+event_evidence(e)))
    return chosen


def strips_pdf(path,recordings,results,filtered_signals,max_per_kind=3,gain_factor=2.):
    c=canvas.Canvas(str(path),pagesize=landscape(A4),pageCompression=1);c.setTitle(tr('strips'));page=0
    for rec,result,filtered in zip(recordings,results,filtered_signals):
        raw_mv=rec.raw.astype(float)*rec.scale
        for start,label in select_strips(rec,result,max_per_kind):
            page+=1;c.setFillColor(INK)
            line(c,16*mm,194*mm,tr('recording',index=rec.index,part=rec.part)+' | '+tr('strips'),265*mm,size=13,bold=True)
            line(c,16*mm,187*mm,tr('warning'),265*mm,size=8)
            text=Text(label,size=7.5,leading=10,color=MUTED);_,h=text.wrap(265*mm,12*mm);text.drawOn(c,16*mm,182*mm-h)
            draw_strip(c,rec,result,start,135*mm,filtered=None,raw_mv=raw_mv,gain_mm_mv=10*gain_factor)
            draw_strip(c,rec,result,start,59*mm,filtered=filtered,gain_mm_mv=10*gain_factor)
            c.setFillColor(MUTED)
            line(c,16*mm,18*mm,tr('markers'),265*mm,size=8)
            line(c,16*mm,13*mm,tr('red_line'),265*mm,size=8)
            line(c,16*mm,7*mm,f"SCP: {rec.blocks[0].number} - {rec.blocks[-1].number} | "+tr('unverified_time'),240*mm,size=7)
            line(c,256*mm,7*mm,tr('page',page=page),25*mm,size=7,right=True);c.showPage()
    c.save()


def full_pdf(path,recordings,results,gain_factor=2.):
    c=canvas.Canvas(str(path),pagesize=landscape(A4),pageCompression=1);c.setTitle(tr('full_title'));page=0
    for rec,result in zip(recordings,results):
        raw_mv=rec.raw.astype(float)*rec.scale
        for start in range(0,int(np.ceil(rec.duration)),80):
            page+=1;c.setFillColor(INK)
            line(c,16*mm,197*mm,tr('recording',index=rec.index,part=rec.part)+' | '+tr('full_title')+' | '+clock(rec,start),265*mm,size=12,bold=True)
            line(c,16*mm,190*mm,tr('full_note',gain=f'{5*gain_factor:g}'),265*mm,size=7)
            for i in range(4):
                if start+i*20>=rec.duration:break
                draw_strip(c,rec,result,start+i*20,(165-i*42)*mm,seconds=20,speed_mm_s=12.5,gain_mm_mv=5*gain_factor,markers=False,raw_mv=raw_mv,half_height_mm=18)
            c.setFillColor(MUTED);line(c,16*mm,10*mm,tr('warning'),240*mm,size=7)
            line(c,256*mm,10*mm,tr('page',page=page),25*mm,size=7,right=True);c.showPage()
    c.save()
