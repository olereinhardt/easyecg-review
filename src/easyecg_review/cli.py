from __future__ import annotations
import argparse
from dataclasses import fields
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import numpy as np
from . import __version__
from .io import load_recordings,list_recordings,FormatError
from .analysis import Config,analyze
from .export import write_exports
from .report import summary_pdf,strips_pdf,full_pdf,aggregate
from .ai import create_context,ai_review


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    temporary.replace(path)


def load_config(path):
    if not path:return Config()
    value=json.loads(Path(path).read_text(encoding='utf8'))
    if not isinstance(value,dict) or set(value)-{f.name for f in fields(Config)}:
        raise ValueError('Unknown analysis config keys')
    config=Config(**value)
    for field in fields(Config):
        number=getattr(config,field.name)
        if field.name=='mains_mode':
            if number not in ('auto','off','50','60'):raise ValueError('mains_mode must be auto/off/50/60')
            continue
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not np.isfinite(number) or number<=0:
            raise ValueError('Config thresholds must be finite positive numbers')
    if config.quality_window_s!=10:raise ValueError('Quality window fixed to 10 seconds in this version')
    if not 0<config.min_agreement<=1 or not 0<config.premature_ratio<1 or config.slow_bpm>=config.fast_bpm:
        raise ValueError('Invalid threshold relationships')
    if not 0<config.highpass_hz<config.lowpass_hz<75:raise ValueError('Filter cutoffs must satisfy 0 < highpass < lowpass < 75 Hz')
    if not 0<config.morphology_correlation<1:raise ValueError('morphology_correlation must be 0..1')
    return config


def run(args):
    source=Path(args.input).expanduser().resolve();output=Path(args.output).expanduser().resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Output directory must be new or empty (no silent overwrite)')
    if source.is_dir() and output.is_relative_to(source):raise ValueError('Choose output outside the input directory')
    config=load_config(args.config)
    print('Prüfe Geräteindex, SCP-Struktur und CRCs ...',flush=True)
    if args.notch is not None:config.mains_mode=args.notch
    recordings,manifest=load_recordings(source,args.allow_missing,args.recordings)
    output.mkdir(parents=True,exist_ok=True)
    manifest.update({'software_version':__version__,'created_utc':datetime.now(timezone.utc).isoformat(),
                     'selected_recordings':sorted({r.index for r in recordings}),'analysis_config':config.__dict__,
                     'display':{'gain_factor':args.gain_factor,'review_mm_per_mv':10*args.gain_factor,'full_mm_per_mv':5*args.gain_factor,'raw_exports_affected':False},
                     'validation_scope':'CRC and payload checks for selected sessions only; index inventory covers all sessions',
                     'implementation_sha256':{name:hashlib.sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest() for name in ['io','analysis','detection','export','report','cli','gui']},
                     'status':'processing','dependencies':{name:importlib.metadata.version(name) for name in ['numpy','scipy','wfdb','pyedflib','reportlab','matplotlib','neurokit2','PyWavelets']}})
    write_json(output/'manifest.json',manifest)
    results=[];filtered_signals=[]
    for i,rec in enumerate(recordings,1):
        print(f'[{i}/{len(recordings)}] {rec.name}: {rec.duration/60:.1f} min',flush=True)
        directory=output/rec.name;directory.mkdir()
        result,filtered=analyze(rec.raw,rec.words,rec.fs,rec.scale,config)
        result['recording']={'name':rec.name,'index':rec.index,'part':rec.part,'start_device_local':rec.start.isoformat(),
                             'fs_hz':rec.fs,'scale_mv_per_lsb':rec.scale,'scp_numbers':[b.number for b in rec.blocks],
                             'warnings':rec.warnings,'diagnostic_status':'unvalidated candidates only'}
        write_exports(directory,rec,result,args.formats)
        write_json(directory/'analysis.json',result)
        results.append(result);filtered_signals.append(filtered)
        # Durable per-recording outputs and progress checkpoint for interrupted jobs.
        manifest['completed_outputs']=[r['recording']['name'] for r in results]
        write_json(output/'manifest.json',manifest)
    print('Erzeuge PDF-Übersicht und Prüfstreifen ...',flush=True)
    summary_pdf(output/'summary.pdf',recordings,results,manifest)
    strips_pdf(output/'review_strips.pdf',recordings,results,filtered_signals,args.strips_per_kind,args.gain_factor)
    if args.full_curves:
        print('Erzeuge vollständiges Rohkurven-PDF ...',flush=True)
        full_pdf(output/'full_curves.pdf',recordings,results,args.gain_factor)
    write_json(output/'summary.json',aggregate(results))
    write_json(output/'ai_context.json',create_context(recordings,results,args.ai_waveforms))
    manifest['status']='complete';manifest['output_checksums']={}
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name!='manifest.json':
            with path.open('rb') as f:
                h=hashlib.sha256()
                for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
            manifest['output_checksums'][path.relative_to(output).as_posix()]=h.hexdigest()
    write_json(output/'manifest.json',manifest)
    print(f'Fertig: {output}\nsummary.pdf / review_strips.pdf / EDF+ / WFDB. Keine bestätigten Diagnosen.',flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='PC-80B: lokale Konvertierung und experimenteller EKG-Prüfbericht')
    parser.add_argument('--version',action='version',version=__version__)
    sub=parser.add_subparsers(dest='command',required=True)
    listing=sub.add_parser('list',help='Messreihen-Inventar für Auswahl (Randdateien geprüft)')
    listing.add_argument('input');listing.add_argument('--json',action='store_true')
    p=sub.add_parser('run',help='ZIP oder Geräteverzeichnis einlesen')
    p.add_argument('input');p.add_argument('-o','--output',required=True)
    p.add_argument('--recordings',type=int,nargs='+',help='README-Messreihen-IDs auswählen')
    p.add_argument('--gain-factor',type=float,default=2.,help='PDF-Verstärkungsfaktor: Standard 2 = 20 mm/mV (Prüfstreifen), 10 mm/mV (Übersicht); Rohdaten unverändert')
    p.add_argument('--notch',choices=['auto','off','50','60'],help='Netzbrummfilter, überschreibt mains_mode in JSON')
    p.add_argument('--formats',nargs='+',choices=['edf','wfdb'],default=['edf','wfdb'])
    p.add_argument('--config',help='JSON-Datei mit Heuristik-Schwellen')
    p.add_argument('--allow-missing',action='store_true',help='Unvollständige/defekte Eingänge explizit erlauben; Lücken splitten')
    p.add_argument('--full-curves',action='store_true',help='Alle Rohsamples zusätzlich als kompaktes PDF (groß)')
    p.add_argument('--strips-per-kind',type=int,default=3,help='Prüfstreifen je Ereigniskategorie (0-20)')
    p.add_argument('--ai-waveforms',action='store_true',help='Bis zu sechs Rohkurvenausschnitte in den lokalen KI-Kontext aufnehmen')
    a=sub.add_parser('ai-review',help='KI-Kontext explizit an Ollama-Endpunkt senden')
    a.add_argument('context');a.add_argument('--model',required=True)
    a.add_argument('--endpoint',default='http://127.0.0.1:11434/api/generate')
    a.add_argument('--allow-remote',action='store_true',help='KI-Kontext explizit an entfernten HTTPS-Endpunkt senden')
    a.add_argument('-o','--output',required=True)
    sub.add_parser('gui',help='Einfache Tkinter-Oberfläche')
    args=parser.parse_args(argv)
    try:
        if args.command=='run':
            if not 0<=args.strips_per_kind<=20:raise ValueError('--strips-per-kind must be 0..20')
            if not np.isfinite(args.gain_factor) or not .25<=args.gain_factor<=8:raise ValueError('--gain-factor must be finite and 0.25..8')
            run(args)
        elif args.command=='list':
            rows=list_recordings(Path(args.input).expanduser().resolve())
            if args.json:print(json.dumps(rows,ensure_ascii=False,allow_nan=False))
            else:
                for r in rows:print(f"{r['index']:3d} | {r['start_device_local'] or '?'} | ~{r['duration_estimate_s']/60:g} min | SCP {r['from']}..{r['to']} | fehlend {r['missing_files']}"+(f" | {r['error']}" if r['error'] else ''))
        elif args.command=='ai-review':ai_review(Path(args.context),Path(args.output),args.model,args.endpoint,args.allow_remote)
        else:
            from .gui import launch
            launch()
        return 0
    except (FormatError,ValueError,OSError,json.JSONDecodeError) as ex:
        print(f'Fehler: {ex}',file=sys.stderr);return 2
    except KeyboardInterrupt:
        print('Abgebrochen. Fertige Messreihen bleiben im Ausgabeordner; manifest.json zeigt Fortschritt.',file=sys.stderr);return 130

if __name__=='__main__':raise SystemExit(main())
