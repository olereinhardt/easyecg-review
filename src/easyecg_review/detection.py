"""Multi-detector QRS proposal, alignment and transparent morphology features.

Uses public WFDB XQRS and NeuroKit2 NeuroKit/SWT detectors. No regularization,
synthetic beat insertion or signal_fixpeaks correction is applied.
"""
from dataclasses import dataclass
import warnings
import numpy as np
from scipy.signal import butter,sosfiltfilt,iirnotch,filtfilt,welch
from scipy.ndimage import uniform_filter1d,median_filter
from wfdb.processing import xqrs_detect
import neurokit2 as nk


def bandpass(x,fs,low=.5,high=40):
    return sosfiltfilt(butter(3,[low,high],btype='bandpass',fs=fs,output='sos'),x)


def clean_signal(x,fs,mains_mode='auto',low=.5,high=40):
    """Zero-phase filtering for review/detection only, never raw export."""
    frequency=0.;ratios={}
    if mains_mode=='auto' and len(x)>=2*fs:
        # Evenly spaced excerpts include interference appearing late in a run.
        pieces=[]
        for start in np.linspace(0,max(0,len(x)-int(20*fs)),min(12,max(1,len(x)//int(20*fs))),dtype=int):
            pieces.append(x[start:start+int(20*fs)])
        f,p=welch(np.concatenate(pieces),fs=fs,nperseg=min(int(4*fs),sum(map(len,pieces))))
        broad=float(p[(f>.5)&(f<min(65,fs/2-1))].sum())
        for line in (50.,60.):
            if line>=fs/2-2:continue
            power=float(p[abs(f-line)<=.5].sum())
            shoulder=p[((abs(f-line)>=2)&(abs(f-line)<=5))]
            reference=float(np.median(shoulder)) if len(shoulder) else 0.
            ratio=power/max(reference*max(1,np.count_nonzero(abs(f-line)<=.5)),1e-18)
            ratios[str(int(line))]={'peak_to_background':ratio,'fraction':power/max(broad,1e-18)}
        eligible=[(v['peak_to_background'],float(k)) for k,v in ratios.items() if v['peak_to_background']>5 and v['fraction']>.01]
        if eligible:frequency=max(eligible)[1]
    elif mains_mode in ('50','60'):frequency=float(mains_mode)
    elif mains_mode!='off':raise ValueError('mains_mode must be auto, off, 50 or 60')
    reviewed=np.asarray(x,float).copy()
    if frequency:
        b,a=iirnotch(frequency,30,fs=fs);reviewed=filtfilt(b,a,reviewed)
    reviewed=bandpass(reviewed,fs,low,high)
    return reviewed,{'method':'zero-phase Butterworth 3rd order','bandpass_hz':[low,high],
        'mains_mode':mains_mode,'applied_notch_hz':frequency,'notch_q':30,'mains_evidence':ratios,
        'raw_exports_filtered':False}


def refine(proposals,signal,fs,method):
    aligned=[]
    for sample in proposals:
        # SWT detector has a positive group/detection delay; compensate on ECG.
        before=.13 if method=='swt' else .065
        after=.035 if method=='swt' else .065
        left=max(0,int(sample-before*fs));right=min(len(signal),int(sample+after*fs)+1)
        if right<=left:continue
        peak=left+int(np.argmax(np.abs(signal[left:right])))
        aligned.append(peak)
    return np.asarray(sorted(set(aligned)),int)


def nearest_matches(a,b,tolerance):
    if not len(a) or not len(b):return np.zeros(len(a),bool)
    idx=np.searchsorted(b,a)
    return np.minimum(abs(b[np.clip(idx-1,0,len(b)-1)]-a),abs(b[np.clip(idx,0,len(b)-1)]-a))<=tolerance


def morphology(signal,peaks,fs,robust_template=True):
    """QRS shape features are proxies, not clinical QRS-duration measurements."""
    q=bandpass(signal,fs,3,30);shape=bandpass(signal,fs,1,35)
    radius=int(.16*fs);vectors=[];width=[];amplitude=[];polarity=[]
    for peak in peaks:
        lo=max(0,peak-radius);hi=min(len(q),peak+radius+1)
        v=np.pad(shape[lo:hi],(lo-(peak-radius),(peak+radius+1)-hi),mode='edge')
        v=v-np.median(np.r_[v[:max(1,radius//3)],v[-max(1,radius//3):]])
        vectors.append(v/max(np.linalg.norm(v),1e-12))
        energy=q[lo:hi]**2
        energy=uniform_filter1d(energy,max(1,int(.02*fs)))
        cumulative=np.cumsum(energy)
        if len(cumulative) and cumulative[-1]>1e-14:
            left=np.searchsorted(cumulative,.10*cumulative[-1]);right=np.searchsorted(cumulative,.90*cumulative[-1])
            width.append((right-left)/fs*1000)
        else:width.append(0.)
        center=shape[max(0,peak-int(.07*fs)):min(len(shape),peak+int(.07*fs)+1)]
        amplitude.append(float(np.max(abs(center))) if len(center) else 0.)
        polarity.append(int(np.sign(shape[peak])))
    vectors=np.asarray(vectors);width=np.asarray(width);amplitude=np.asarray(amplitude)
    if len(peaks):
        # Local templates: narrow, non-early beats in +/-30s. No manual labels.
        rr=np.r_[np.nan,np.diff(peaks)/fs]
        correlations=[];reference_width=[]
        for i,p in enumerate(peaks):
            lo=np.searchsorted(peaks,p-int(30*fs));hi=np.searchsorted(peaks,p+int(30*fs))
            ids=np.arange(lo,hi);ids=ids[ids!=i]
            if not len(ids):correlations.append(1.);reference_width.append(float(width[i]));continue
            median_rr=np.nanmedian(rr[ids]);normal=ids[(rr[ids]>=.90*median_rr)&(rr[ids]<=1.25*median_rr)]
            if len(normal)<4:normal=ids
            if robust_template:
                # Use a repeated local shape for rhythm screening; opposite
                # morphologies must not cancel into an unrepresentative median.
                candidates=vectors[normal];similarity=candidates@candidates.T
                support=np.sum(similarity>.65,axis=1);best=np.flatnonzero(support==support.max())
                medoid=best[np.argmin(width[normal[best]])]
                normal=normal[similarity[medoid]>.65]
            else:
                # Proposal screening uses the narrow local reference. Rhythm
                # screening recomputes a robust template on retained QRS only.
                limit=np.percentile(width[normal],60)
                normal=normal[width[normal]<=limit+1e-6]
            template=np.median(vectors[normal],axis=0);template/=max(np.linalg.norm(template),1e-12)
            correlations.append(float(np.clip(np.dot(vectors[i],template),-1,1)))
            reference_width.append(float(np.median(width[normal])))
        corr=np.asarray(correlations);reference_width=np.asarray(reference_width)
    else:corr=np.asarray([]);reference_width=np.asarray([])
    return {'qrs_energy_width_ms':width,'reference_width_ms':reference_width,'template_correlation':corr,
            'amplitude_mv':amplitude,'polarity':np.asarray(polarity,int)}


def detect(signal,fs):
    q=bandpass(signal,fs,3,30);methods={'xqrs':[],'neurokit':[],'swt':[]};failures=[]
    chunk=int(300*fs);overlap=int(5*fs)
    for start in range(0,len(signal),chunk):
        left=max(0,start-overlap);right=min(len(signal),start+chunk+overlap)
        segment=signal[left:right]
        for method in methods:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    if method=='xqrs':peaks=xqrs_detect(segment,fs=fs,verbose=False)
                    else:peaks=nk.ecg_findpeaks(segment,sampling_rate=fs,method='kalidas2017' if method=='swt' else 'neurokit')['ECG_R_Peaks']
                peaks=refine(np.asarray(peaks)+left,q,fs,method)
                methods[method].extend(int(p) for p in peaks if start<=p<min(start+chunk,len(signal)))
            except (ValueError,IndexError,ZeroDivisionError) as ex:
                failures.append({'method':method,'chunk_start_s':start/fs,'reason':str(ex)[:160]})
    methods={k:np.asarray(sorted(set(v)),int) for k,v in methods.items()}
    proposals=sorted((int(p),name) for name,peaks in methods.items() for p in peaks)
    clusters=[]
    for p,name in proposals:
        if not clusters or p-clusters[-1][0][0]>.08*fs:clusters.append([(p,name)])
        else:clusters[-1].append((p,name))
    all_peaks=np.asarray([int(np.median([p for p,_ in cluster])) for cluster in clusters],int)
    all_votes=np.asarray([len({name for _,name in cluster}) for cluster in clusters],int)
    features=morphology(signal,all_peaks,fs,robust_template=False)
    amplitude=features['amplitude_mv'];width=features['qrs_energy_width_ms'];corr=features['template_correlation']
    if len(amplitude):
        local_amplitude=np.asarray([np.median(amplitude[max(0,i-15):i+16]) for i in range(len(amplitude))])
        acceptable_amp=amplitude>=np.maximum(.006,.12*local_amplitude)
        # Retain strong single-detector proposals when morphology also supports
        # a QRS. Consensus candidates are not automatically declared valid.
        keep=(all_votes>=2)|((all_votes==1)&(corr>.85)&(amplitude>.35*local_amplitude))
        keep &= acceptable_amp & (width>=20) & (width<=260)
        # Explicit refractory competition by detector support, then shape.
        kept=[]
        for i in np.flatnonzero(keep):
            if kept and all_peaks[i]-all_peaks[kept[-1]]<.24*fs:
                j=kept[-1]
                score_i=all_votes[i]+max(0,corr[i])+.2*amplitude[i]/max(local_amplitude[i],1e-6)
                score_j=all_votes[j]+max(0,corr[j])+.2*amplitude[j]/max(local_amplitude[j],1e-6)
                if score_i>score_j:kept[-1]=int(i)
            else:kept.append(int(i))
        selected=np.asarray(kept,int)
    else:selected=np.asarray([],int)
    final=all_peaks[selected]
    final_features=morphology(signal,final,fs)
    rejected=np.setdiff1d(np.arange(len(all_peaks)),selected)
    return {'peaks':final,'votes':all_votes[selected],'features':final_features,'method_peaks':methods,
        'failures':failures,'rejected':[{'sample':int(all_peaks[i]),'votes':int(all_votes[i]),
        'amplitude_mv':float(amplitude[i]),'template_correlation':float(corr[i]),
        'reason':'insufficient support/amplitude/width or refractory competition'} for i in rejected]}
