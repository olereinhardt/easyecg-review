"""Export unfiltered calibrated samples; experimental events are explicit."""
from pathlib import Path
import csv
from datetime import timedelta
import numpy as np
import pyedflib
import wfdb


def edf_number(value):
    for decimals in range(6,-1,-1):
        text=f'{value:.{decimals}f}'
        if len(text)<=8:return float(text)
    raise ValueError('EDF calibration field overflow')


def write_exports(directory: Path,recording,result,formats=('edf','wfdb')):
    directory.mkdir(parents=True,exist_ok=True)
    raw=recording.raw;words=recording.words;fs=recording.fs
    np.savez_compressed(directory/'raw.npz',raw_centered=raw,device_words=words,fs_hz=fs,scale_mv_per_lsb=recording.scale)
    if 'edf' in formats:
        # EDF records are 1 second. Partial final seconds are explicitly padded.
        pad=(-len(raw))%int(fs);signal=np.pad(raw,(0,pad),mode='constant')
        pmin=edf_number(-2048*recording.scale);pmax=edf_number(2047*recording.scale)
        with pyedflib.EdfWriter(str(directory/(recording.name+'.edf')),1,file_type=pyedflib.FILETYPE_EDFPLUS) as writer:
            writer.setStartdatetime(recording.start)
            writer.setPatientCode('anonymous')
            writer.setPatientName('X')
            writer.setEquipment('PC-80B_Easy_ECG')
            writer.setRecordingAdditional('raw_experimental_review')
            writer.setSignalHeader(0,{'label':'ECG unknown lead','dimension':'mV','sample_frequency':fs,
                'physical_min':pmin,'physical_max':pmax,'digital_min':-2048,'digital_max':2047,
                'transducer':'single-lead PC-80B','prefilter':'device unknown; no additional filtering'})
            writer.writeSamples([signal.astype(np.int32)],digital=True)
            writer.writeAnnotation(0,-1,'RAW ECG; local device time; lead unverified')
            writer.writeAnnotation(0,-1,'Events are unverified heuristic candidates')
            for event in result['events']:
                writer.writeAnnotation(event['onset_s'],event['duration_s'],event['kind'])
            if pad:writer.writeAnnotation(len(raw)/fs,pad/fs,'PADDING: no recorded data')
        result['edf']={'padding_samples':pad,'physical_min_mv':pmin,'physical_max_mv':pmax,
                       'max_calibration_rounding_error_mv':max(abs(pmin+2048*recording.scale),abs(pmax-2047*recording.scale))}
    if 'wfdb' in formats:
        wfdb.wrsamp(recording.name,fs=fs,units=['mV'],sig_name=['ECG_unknown_lead'],
            d_signal=raw[:,None],fmt=['16'],adc_gain=[1/recording.scale],baseline=[0],
            base_datetime=recording.start,comments=['RAW PC-80B signal; lead and device timezone unverified',
            'Amplitude interpretation from reverse engineered Easy ECG format',
            'Q annotations are unverified QRS detections, not normal beats; device words retained in raw.npz'],write_dir=str(directory))
        if result['beats']:
            wfdb.wrann(recording.name,'qrs',sample=np.asarray([b['sample'] for b in result['beats']],dtype=np.int64),
                symbol=['Q']*len(result['beats']),fs=fs,write_dir=str(directory))
    fields=['sample','time_s','device_time','usable','corroborated','detector_votes','confidence','rr_before_s','rr_after_s','local_rr_s','template_correlation','qrs_energy_width_ms','amplitude_mv','labels']
    with (directory/'beats.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fields);writer.writeheader()
        for beat in result['beats']:
            row=dict(beat);row['device_time']=(recording.start+timedelta(seconds=beat['time_s'])).isoformat()
            row['labels']=';'.join(row['labels']);writer.writerow(row)
    with (directory/'rejected_qrs.csv').open('w',newline='',encoding='utf8') as f:
        fields=['sample','votes','amplitude_mv','template_correlation','reason']
        writer=csv.DictWriter(f,fields);writer.writeheader()
        writer.writerows(result['detector']['rejected_proposals'])
    fields=['kind','onset_s','duration_s','device_time','evidence']
    with (directory/'events.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fields);writer.writeheader()
        for event in result['events']:
            row=dict(event);row['device_time']=(recording.start+timedelta(seconds=event['onset_s'])).isoformat();writer.writerow(row)
    with (directory/'quality.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,list(result['windows'][0]));writer.writeheader()
        for window in result['windows']:
            row=dict(window);row['reasons']=';'.join(row['reasons']);writer.writerow(row)
