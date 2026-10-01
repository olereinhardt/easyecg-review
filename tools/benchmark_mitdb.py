#!/usr/bin/env python3
"""Reproducible limited public-data development benchmark, not clinical validation.

Requires explicit --download to fetch missing PhysioNet excerpts. Metrics match
predictions to annotations one-to-one within 150ms; the algorithm sees no labels.
"""
import argparse
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from scipy.signal import resample_poly
import wfdb
from easyecg_review.analysis import analyze
from easyecg_review import __version__

BEATS=set('NLRAaJSVF ejE/fQ'.replace(' ',''))
# E (ventricular escape) is not a premature beat and is excluded here.
ECTOPIC=set('AaJSV')


def score(pred,ref,tolerance=22.5):
    pred=np.sort(np.asarray(pred,int));ref=np.sort(np.asarray(ref,int));i=j=tp=0
    while i<len(pred) and j<len(ref):
        difference=pred[i]-ref[j]
        if abs(difference)<=tolerance:tp+=1;i+=1;j+=1
        elif difference<0:i+=1
        else:j+=1
    return {'tp':tp,'fp':len(pred)-tp,'fn':len(ref)-tp,
            'sensitivity':tp/len(ref) if len(ref) else None,
            'positive_predictive_value':tp/len(pred) if len(pred) else None}


def evaluate(x,samples,symbols,analyzer=analyze,profile='preserve'):
    # Preservation prevents artificial amplitude clipping of a different device.
    # This is a waveform benchmark at 150Hz, not a PC-80B hardware simulation.
    scale=max(.000806,float(np.max(abs(x)))/1900) if profile=='preserve' else .000806
    clip=float(np.mean((x < -2048*scale)|(x >2047*scale)))
    raw=np.clip(np.rint(x/scale),-2048,2047).astype(np.int16)
    result,_=analyzer(raw,(raw.astype(np.int32)+2048).astype(np.uint16),150,scale)
    samples=np.asarray(samples);symbols=np.asarray(symbols)
    truth=samples[np.isin(symbols,list(BEATS))];ectopic=samples[np.isin(symbols,list(ECTOPIC))]
    p=np.asarray([b['sample'] for b in result['beats']],int)
    usable=np.asarray([b['sample'] for b in result['beats'] if b['usable']],int)
    events=np.asarray([round(e['onset_s']*150) for e in result['events'] if e['kind']=='premature_beat_candidate'],int)
    return {'duration_s':len(x)/150,'scale_mv_per_lsb':scale,'quantization_clipping_fraction':clip,
            'truth_beat_count':len(truth),'truth_premature_ectopic_count':len(ectopic),
            'qrs_matching_150ms':score(p,truth),'usable_qrs_matching_all_truth':score(usable,truth),
            'ectopic_candidates_matching_all_truth':score(events,ectopic),
            'usable_s':result['summary']['usable_s'],'candidate_counts':result['summary']['candidate_counts']}


def cached_excerpt(cache,record,seconds,download):
    path=cache/f'mit{record}_{seconds}s.npz'
    if not path.exists():
        if not download:raise ValueError(f'Missing {path}; use --download to authorize public-data retrieval')
        rec=wfdb.rdrecord(record,pn_dir='mitdb',sampto=seconds*360)
        ann=wfdb.rdann(record,'atr',pn_dir='mitdb',sampto=seconds*360)
        ratio=Fraction(150,int(rec.fs));x=resample_poly(rec.p_signal[:,0],ratio.numerator,ratio.denominator)
        cache.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(path,signal=x,samples=np.rint(ann.sample*150/rec.fs).astype(int),symbols=np.asarray(ann.symbol),channel=rec.sig_name[0])
    return np.load(path,allow_pickle=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--records',nargs='+',default=['100','200','108','207','101','103','201','208'])
    p.add_argument('--seconds',type=int,default=600);p.add_argument('--cache',type=Path,default=Path('private/public-cache'))
    p.add_argument('--download',action='store_true');p.add_argument('--profile',choices=['preserve','pc80b'],default='preserve')
    p.add_argument('--baseline-module',type=Path,help='Optional previous analysis.py for paired comparison')
    p.add_argument('-o','--output',type=Path,required=True);args=p.parse_args()
    if not 30<=args.seconds<=1800 or any(not r.isdigit() for r in args.records):p.error('Numeric records; seconds must be 30..1800')
    baseline=None
    if args.baseline_module:
        spec=importlib.util.spec_from_file_location('benchmark_baseline',args.baseline_module)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);baseline=module.analyze
    rows=[]
    for record in args.records:
        z=cached_excerpt(args.cache,record,args.seconds,args.download)
        row={'record':record,'channel':str(z['channel']) if 'channel' in z else 'channel 0',
             'current':evaluate(z['signal'],z['samples'],z['symbols'],profile=args.profile)}
        if baseline:row['v0_1_baseline']=evaluate(z['signal'],z['samples'],z['symbols'],baseline,args.profile)
        rows.append(row);print(record,json.dumps(row['current']['qrs_matching_150ms']),json.dumps(row['current']['ectopic_candidates_matching_all_truth']),flush=True)
    metrics={'software_version':__version__,'dataset':'MIT-BIH Arrhythmia Database 1.0.0',
       'source':'https://physionet.org/content/mitdb/1.0.0/','profile':args.profile,
       'limitations':['Limited excerpts; development benchmark, not clinical validation',
         'Channel 0 resampled to 150Hz; preserve profile adapts amplitude scale to avoid artificial clipping',
         'pc80b profile intentionally clips to the fixed hardware range; profiles are not comparable',
         'Ectopic reference symbols A,a,J,S,V; escape beats E excluded',
         'All annotated beats remain in denominator, including quality-excluded intervals',
         '150ms matching does not evaluate clinical beat type, onset/duration or motion artifact reliability',
         'No external expert review of patient ECG; template width is not a clinical QRS measurement'],
       'records':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(metrics,indent=2)+'\n')

if __name__=='__main__':main()
