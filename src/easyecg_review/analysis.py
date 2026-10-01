"""Experimental morphology/RR screening with explicit signal uncertainty.

Candidate annotations are for human review, not clinical diagnoses. Raw data
are retained unchanged; none of the detector results are expert-adjudicated.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import numpy as np
from scipy.signal import butter,sosfiltfilt,iirnotch,filtfilt
from scipy.ndimage import uniform_filter1d
from .detection import bandpass,clean_signal,detect,nearest_matches

@dataclass
class Config:
    quality_window_s: float = 10.
    fast_bpm: float = 100.
    slow_bpm: float = 50.
    long_rr_s: float = 2.
    premature_ratio: float = .85
    min_agreement: float = .55
    baseline_range_mv: float = .65
    max_step_mv: float = .40
    step_qrs_multiplier: float = 3.
    flat_std_mv: float = .006
    irregular_cv: float = .18
    mains_mode: str = 'auto'
    highpass_hz: float = .5
    lowpass_hz: float = 40.
    edge_exclusion_s: float = 2.
    dropout_min_s: float = 1.
    morphology_correlation: float = .80

LABELS={
 'premature_beat_candidate':'Vorzeitiger/ektoper Schlag-Kandidat',
 'ventricular_pattern_candidate':'Abweichender vorzeitiger Komplex (VES-Muster prüfen)',
 'narrow_premature_candidate':'Ähnlicher/schmaler vorzeitiger Komplex (SVES-Muster prüfen)',
 'morphology_outlier_candidate':'Abweichende QRS-Form ohne gesicherte Ursache',
 'ectopic_couplet_candidate':'Zwei aufeinanderfolgende ektope Kandidaten',
 'ectopic_run_candidate':'Serie von mindestens drei ektopen Kandidaten',
 'bigeminy_candidate':'Bigeminus-Muster-Kandidat',
 'trigeminy_candidate':'Trigeminus-Muster-Kandidat',
 'wide_complex_run_candidate':'Schnelle Serie abweichender Komplexe (Rhythmus prüfen)',
 'long_rr_candidate':'Langer RR-Abstand bei ausreichendem Signal',
 'signal_dropout':'Nahezu flaches Signal / Mess- oder Kontaktproblem möglich',
 'fast_rate_candidate':'Erhöhte geschätzte Herzfrequenz',
 'slow_rate_candidate':'Niedrige geschätzte Herzfrequenz',
 'irregular_rr_candidate':'Unregelmäßige RR-Abstände',
 'persistent_irregular_rr_candidate':'Anhaltende RR-Unregelmäßigkeit (keine AF-Diagnose)',
 'poor_signal':'Signalqualität eingeschränkt',
}

def filter_ecg(x,fs,low=.5,high=40):return bandpass(x,fs,low,high)
def matches(a,b,tolerance):return nearest_matches(a,b,tolerance)
def detect_peaks(x,fs):
    d=detect(x,fs)
    return d['peaks'],d['method_peaks']['neurokit']

def runs(mask):
    padded=np.r_[False,mask,False].astype(int)
    return list(zip(np.flatnonzero(np.diff(padded)==1),np.flatnonzero(np.diff(padded)==-1)))


def local_reference(peaks,index,fs):
    """Use neighbouring cycle lengths without requiring normal-beat runs.

    The median is robust to isolated early beats/long followers. Alternating
    intervals naturally yield a cycle midpoint; no five-normal-beats gate.
    """
    rr=np.diff(peaks)/fs
    lo=max(0,index-10);hi=min(len(rr),index+10)
    ids=np.arange(lo,hi);ids=ids[(ids!=index-1)&(ids!=index)]
    values=rr[ids];values=values[(values>.25)&(values<2.5)]
    if len(values)<3:return None
    return float(np.median(values))


def analyze(raw,words,fs,scale,config=None):
    c=config or Config();x=np.asarray(raw,float)*scale
    filtered,filter_info=clean_signal(x,fs,c.mains_mode,c.highpass_hz,c.lowpass_hz)
    detection=detect(filtered,fs);peaks=detection['peaks'];votes=detection['votes'];features=detection['features']
    confidence=votes>=2
    baseline=sosfiltfilt(butter(2,.5,fs=fs,output='sos'),x)
    quality_signal=x
    if filter_info['applied_notch_hz']:
        b,a=iirnotch(filter_info['applied_notch_hz'],30,fs=fs)
        quality_signal=filtfilt(b,a,x)
    high_noise=quality_signal-sosfiltfilt(butter(2,40,fs=fs,output='sos'),quality_signal)
    # Near-constant noise of a few ADC steps is also a dropout, not just exactly
    # repeated integers. Cause remains unknown: technical problem or rhythm.
    size=max(3,int(.25*fs));mean=uniform_filter1d(x,size)
    local_std=np.sqrt(np.maximum(0,uniform_filter1d(x*x,size)-mean*mean))
    near_flat=local_std<max(scale*2.5,.0015)
    dropout=np.zeros(len(x),bool);dropout_intervals=[]
    for lo,hi in runs(near_flat):
        if (hi-lo)/fs>=c.dropout_min_s:
            dropout[lo:hi]=True;dropout_intervals.append((lo,hi))
    windows=[];good=np.zeros(len(x),bool);step=int(c.quality_window_s*fs)
    for lo in range(0,len(x),step):
        hi=min(len(x),lo+step);v=x[lo:hi];adc=words[lo:hi]&0xfff
        ids=np.flatnonzero((peaks>=lo)&(peaks<hi));rr=np.diff(peaks[ids])/fs
        std=float(np.std(v));span=float(np.ptp(v));clip=float(np.mean((adc<=2)|(adc>=4093)))
        drift=float(np.ptp(baseline[lo:hi]));maxstep=float(np.max(abs(np.diff(v)))) if len(v)>1 else 0.
        hf=float(np.std(high_noise[lo:hi])/max(np.std(filtered[lo:hi]),.001))
        agreement=float(np.mean(confidence[ids])) if len(ids) else 0.
        slopes=[]
        for p in peaks[ids]:
            qlo=max(lo,p-int(.08*fs));qhi=min(hi,p+int(.08*fs)+1)
            if qhi-qlo>1:slopes.append(float(np.max(abs(np.diff(x[qlo:qhi])))))
        typical=float(np.median(slopes)) if len(slopes)>=3 else 0.
        limit=max(c.max_step_mv,c.step_qrs_multiplier*typical)
        reasons=[]
        if clip>.001:reasons.append('ADC-Grenzwerte/Clipping')
        if std<c.flat_std_mv:reasons.append('Flaches Signal/Kontakt prüfen')
        if drift>c.baseline_range_mv:reasons.append('Starke Basislinienbewegung')
        if maxstep>limit:reasons.append('Sprunghafte Signaländerung')
        if hf>.65:reasons.append('Starke hochfrequente Störung')
        if len(ids)<3:reasons.append('Zu wenige QRS-Kandidaten')
        if agreement<c.min_agreement:reasons.append('Geringe QRS-Detektorübereinstimmung')
        good[lo:hi]=not reasons
        windows.append({'start_s':lo/fs,'duration_s':(hi-lo)/fs,'usable':not reasons,'reasons':reasons,
          'std_mv':std,'range_mv':span,'clipped_fraction':clip,'baseline_range_mv':drift,'max_step_mv':maxstep,
          'step_limit_mv':limit,'hf_ratio':hf,'detector_agreement':agreement,'qrs_candidates':len(ids),'median_bpm':None})
    edge=int(c.edge_exclusion_s*fs);good[:edge]=False
    if edge:good[-edge:]=False
    good[dropout]=False
    def reliable_interval(lo,hi):
        left=max(0,int(lo));right=min(len(good),int(hi)+1)
        return right>left and bool(np.all(good[left:right]))
    usable=np.asarray([good[p] and confidence[i] for i,p in enumerate(peaks)],bool)
    rr=np.diff(peaks)/fs;events=[];beat_labels=[[] for _ in peaks];early=np.zeros(len(peaks),bool);ventricular=np.zeros(len(peaks),bool)
    def add(kind,onset,duration,evidence):events.append({'kind':kind,'onset_s':float(onset),'duration_s':float(duration),'evidence':evidence})
    references=[]
    for i,p in enumerate(peaks):
        reference=local_reference(peaks,i,fs);references.append(reference)
        prev=float(rr[i-1]) if i else None;nxt=float(rr[i]) if i<len(rr) else None
        if i and prev>=c.long_rr_s and usable[i] and usable[i-1] and reliable_interval(peaks[i-1],p):
            add('long_rr_candidate',peaks[i-1]/fs,prev,f'RR={prev:.3f}s; Erkennungslücke möglich, keine bestätigte Pause')
            beat_labels[i].append('long_rr_candidate')
        if reference is None or prev is None or nxt is None or not usable[i] or i<2 or i>=len(peaks)-2:continue
        # Context requires valid adjacent RR intervals but not five uniformly
        # spaced beats. Frequent ectopy is intentionally retained.
        if not reliable_interval(peaks[i-1],peaks[i+1]) or not usable[i-1] or not usable[i+1]:continue
        corr=float(features['template_correlation'][i]);width=float(features['qrs_energy_width_ms'][i]);ref_width=float(features['reference_width_ms'][i])
        different=corr<c.morphology_correlation
        wider=width>max(100.,1.20*ref_width)
        very_early=prev<c.premature_ratio*reference
        # Mild timing deviations need morphology or a clear recovery interval;
        # strong prematurity allows non-compensatory PAC-like followers.
        recovery=nxt>1.08*reference
        context=rr[max(0,i-12):min(len(rr),i+12)]
        pairs=(context[:-1]+context[1:])/2
        context_cv=(1.4826*np.median(abs(pairs-np.median(pairs)))/np.median(pairs)) if len(pairs)>=5 else 0.
        # A short interval in an unstructured irregular rhythm is insufficient
        # evidence for a same-shape extrasystole. Regular paired ectopy retains
        # low pair-cycle variability even with alternating short/long RR.
        structured_context=context_cv<=.12
        short_ids=np.flatnonzero(context<c.premature_ratio*reference)
        # Trigeminy has variable pair sums; retain repeatable alternating
        # patterns without relaxing the gate for arbitrary irregular RR.
        for period in (2,3):
            target=i-1-max(0,i-12)
            if any(hi-lo>=3 and target in short_ids[lo:hi+1] for lo,hi in runs(np.diff(short_ids)==period)):
                structured_context=True
        timing_pattern=very_early and (recovery or different or prev<.78*reference) and (different or structured_context)
        # Strongly different, corroborated complexes need not satisfy a strict
        # prematurity threshold (e.g. frequent/interpolated ectopy). Require
        # timing support to avoid labeling all persistent abnormal morphologies.
        morphology_pattern=(votes[i]==3 and different and
            ((corr<.35 and prev<.98*reference and width>1.20*ref_width) or
             (wider and recovery and prev<.95*reference)))
        ectopic=timing_pattern or morphology_pattern
        if ectopic:
            early[i]=True;ventricular[i]=different and (wider or corr<.35)
            subtype='ventricular_pattern_candidate' if ventricular[i] else 'narrow_premature_candidate'
            evidence=f'RR davor={prev:.3f}s, danach={nxt:.3f}s, Referenz={reference:.3f}s; Formkorrelation={corr:.2f}, Kontext-CV={context_cv:.2f}, QRS-Energiebreite={width:.0f}ms (Proxy); {votes[i]}/3 Detektoren'
            add('premature_beat_candidate',p/fs,0,evidence);add(subtype,p/fs,0,evidence)
            beat_labels[i].extend(['premature_beat_candidate',subtype])
        elif different and corr<.65:
            add('morphology_outlier_candidate',p/fs,0,f'Formkorrelation={corr:.2f}; Energiebreite={width:.0f}ms (keine klinische QRS-Dauer); Ursache unklar')
            beat_labels[i].append('morphology_outlier_candidate')
    # Repeated morphology/RR patterns, separate from individual beat counts.
    for lo,hi in runs(early):
        count=hi-lo
        if count>=2:
            kind='ectopic_couplet_candidate' if count==2 else 'ectopic_run_candidate'
            add(kind,peaks[lo]/fs,(peaks[hi-1]-peaks[lo])/fs,f'{count} aufeinanderfolgende unbestätigte ektope Kandidaten')
        if count>=3 and np.all(ventricular[lo:hi]):
            rate=60/np.mean(np.diff(peaks[lo:hi])/fs)
            if rate>c.fast_bpm:add('wide_complex_run_candidate',peaks[lo]/fs,(peaks[hi-1]-peaks[lo])/fs,f'{count} abweichende Komplexe, {rate:.1f}/min; kein gesicherter VT-Nachweis')
    ectopic_ids=np.flatnonzero(early)
    for period,kind in [(2,'bigeminy_candidate'),(3,'trigeminy_candidate')]:
        if len(ectopic_ids)<4:continue
        chain=np.r_[False,np.diff(ectopic_ids)==period]
        for lo,hi in runs(chain):
            ids=ectopic_ids[max(0,lo-1):hi]
            if len(ids)>=4 and reliable_interval(peaks[ids[0]],peaks[ids[-1]]):
                add(kind,peaks[ids[0]]/fs,(peaks[ids[-1]]-peaks[ids[0]])/fs,f'{len(ids)} Kandidaten, jedes {period}. erkannte QRS; unbestätigtes Muster')
    for lo,hi in dropout_intervals:
        add('signal_dropout',lo/fs,(hi-lo)/fs,'Nahezu konstante Rohkurve; technische/Kontaktstörung möglich, Rhythmusursache nicht ausgeschlossen; nicht als Pause gezählt')
    for w in windows:
        lo=int(w['start_s']*fs);hi=min(len(x),lo+int(w['duration_s']*fs));fraction=float(np.mean(good[lo:hi]))
        ids=np.flatnonzero((peaks>=lo)&(peaks<hi)&usable)
        valid_rr=[(peaks[b]-peaks[a])/fs for a,b in zip(ids[:-1],ids[1:]) if b==a+1 and reliable_interval(peaks[a],peaks[b])]
        w['usable_fraction']=fraction;w['usable']=fraction>=.5
        if any(dropout[lo:hi]):w['reasons'].append('Nahezu flacher Teilabschnitt')
        if lo<edge or hi>len(x)-edge:w['reasons'].append('Teilweise Aufnahmerand')
        if len(valid_rr)>=2 and fraction>=.5:w['median_bpm']=float(60/np.median(valid_rr))
    for kind,predicate in [('fast_rate_candidate',lambda b:b>c.fast_bpm),('slow_rate_candidate',lambda b:b<c.slow_bpm)]:
        mask=np.asarray([w['median_bpm'] is not None and predicate(w['median_bpm']) for w in windows])
        for lo,hi in runs(mask):
            start=windows[lo]['start_s'];end=windows[hi-1]['start_s']+windows[hi-1]['duration_s']
            values=[w['median_bpm'] for w in windows[lo:hi]]
            add(kind,start,end-start,f'10s-Median {min(values):.1f}-{max(values):.1f}/min; Kontext nötig')
    irregular=[]
    for lo in range(0,len(x),int(30*fs)):
        hi=min(len(x),lo+int(30*fs));flag=False
        if hi-lo>=30*fs and np.mean(good[lo:hi])>=.85:
            ids=np.flatnonzero((peaks>=lo)&(peaks<hi)&usable)
            intervals=np.asarray([(peaks[b]-peaks[a])/fs for a,b in zip(ids[:-1],ids[1:]) if b==a+1 and reliable_interval(peaks[a],peaks[b])])
            if len(intervals)>=12:
                cv=float(np.std(intervals)/np.mean(intervals));rmssd=float(np.sqrt(np.mean(np.diff(intervals)**2)))
                if cv>c.irregular_cv and rmssd>.12:
                    flag=True;add('irregular_rr_candidate',lo/fs,(hi-lo)/fs,f'RR-CV={cv:.3f}, RMSSD={rmssd:.3f}s; Ektopie/physiologische Variabilität/Fehler möglich, kein AF-Nachweis')
        irregular.append(flag)
    for lo,hi in runs(np.asarray(irregular)):
        if hi-lo>=3:add('persistent_irregular_rr_candidate',lo*30,(hi-lo)*30,'Mindestens 90s unregelmäßige RR-Folge; keine P-Wellen-/AF-Klassifikation')
    for lo,hi in runs(~good):
        if (hi-lo)/fs<.2:continue
        reasons=sorted({reason for w in windows if w['start_s']<(hi/fs) and w['start_s']+w['duration_s']>(lo/fs) for reason in w['reasons']})
        add('poor_signal',lo/fs,(hi-lo)/fs,'; '.join(reasons) or 'Unsichere Signalqualität')
    beats=[]
    for i,p in enumerate(peaks):
        beats.append({'sample':int(p),'time_s':p/fs,'usable':bool(usable[i]),'corroborated':bool(confidence[i]),
            'detector_votes':int(votes[i]),'confidence':'high' if votes[i]==3 else 'moderate' if votes[i]==2 else 'low',
            'rr_before_s':float(rr[i-1]) if i else None,'rr_after_s':float(rr[i]) if i<len(rr) else None,
            'local_rr_s':references[i],'template_correlation':float(features['template_correlation'][i]),
            'qrs_energy_width_ms':float(features['qrs_energy_width_ms'][i]),'amplitude_mv':float(features['amplitude_mv'][i]),'labels':beat_labels[i]})
    events.sort(key=lambda e:(e['onset_s'],e['kind']));rates=[w['median_bpm'] for w in windows if w['median_bpm'] is not None]
    counts={kind:sum(e['kind']==kind for e in events) for kind in LABELS}
    summary={'duration_s':len(x)/fs,'usable_s':float(good.sum()/fs),'excluded_s':float((~good).sum()/fs),
      'qrs_candidates':len(peaks),'usable_corroborated_qrs':int(usable.sum()),'rejected_qrs_proposals':len(detection['rejected']),
      'confirmed_extrasystoles':None,'candidate_counts':counts,'rate_window_min_bpm':min(rates) if rates else None,
      'rate_window_median_bpm':float(np.median(rates)) if rates else None,'rate_window_max_bpm':max(rates) if rates else None,
      'device_flag_samples':int(np.count_nonzero(words&0xf000)),
      'status_nibbles':{str(int(v)):int(n) for v,n in zip(*np.unique(words>>12,return_counts=True))}}
    return {'summary':summary,'windows':windows,'beats':beats,'events':events,'config':asdict(c),'filter':filter_info,
        'detector':{'methods':['WFDB XQRS','NeuroKit2 neurokit','NeuroKit2 kalidas2017 SWT'],
        'automatic_rr_regularization':False,'failures':detection['failures'],'rejected_proposals':detection['rejected']}},filtered
