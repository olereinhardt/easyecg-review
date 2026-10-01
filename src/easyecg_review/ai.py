"""Optional, explicitly invoked Ollama interface; main processing never networks."""
import json
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from .report import aggregate

PROMPT = '''You are reviewing an experimental single-lead ECG preprocessing report.
This is NOT a validated medical device or a clinical diagnosis. The candidate counts
are heuristic detections, NOT confirmed PACs/PVCs, AF, pauses or other diagnoses.
Do not infer ECG morphology or conditions from summary statistics alone. Describe
uncertainty, artifact and questions for a clinician. Never give an all-clear,
treatment advice, or replace medical assessment. Respond in German. Keep inferred
possibilities explicitly separate from observations. If waveforms are absent,
state that you did not inspect ECG waveforms. Context follows:\n'''


def create_context(recordings,results,include_waveforms=False):
    context={'schema':'easyecg-review-ai-context-v1','purpose':'unvalidated clinician-review preparation',
        'privacy':'No names, device serial, filenames, hashes or absolute dates; timings relative within recordings',
        'limitations':['Single lead; electrode position unknown','No validated diagnosis or PAC/PVC classification',
                      'No reliable exclusion of disease','Artifact can resemble arrhythmia'],
        'aggregate':aggregate(results),'recordings':[]}
    for rec,result in zip(recordings,results):
        item={'id':f'r{rec.index:03d}_p{rec.part:02d}','summary':result['summary'],'config':result['config'],
              'events_sample':[e for e in result['events'] if e['kind']!='poor_signal'][:10]}
        context['recordings'].append(item)
    if include_waveforms:
        context['waveforms']=[]
        for rec,result in zip(recordings,results):
            events=[e for e in result['events'] if e['kind']=='premature_beat_candidate'][:1]
            if not events:continue
            start=max(0,min(rec.duration-10,events[0]['onset_s']-3));lo=int(start*rec.fs);hi=lo+int(10*rec.fs)
            context['waveforms'].append({'id':f'r{rec.index:03d}_p{rec.part:02d}','onset_s':start,'fs_hz':rec.fs,
                'unit':'mV','filtered':False,'samples':[round(float(v),6) for v in rec.raw[lo:hi]*rec.scale]})
            if len(context['waveforms'])>=6:break
    return context

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('AI endpoint redirects are disabled')


def ai_review(context_path:Path,output:Path,model:str,endpoint:str,allow_remote=False):
    url=urlsplit(endpoint)
    if url.scheme not in ('http','https') or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use an http(s) endpoint without credentials/query/fragment')
    local=url.hostname in ('localhost','127.0.0.1','::1')
    if not local and not allow_remote:raise ValueError('Remote endpoint requires --allow-remote; this sends the context file')
    if not local and url.scheme!='https':raise ValueError('Remote endpoint requires HTTPS')
    if context_path.stat().st_size>2*1024**2:raise ValueError('AI context exceeds 2 MiB')
    context=json.loads(context_path.read_text(encoding='utf8'))
    if context.get('schema')!='easyecg-review-ai-context-v1':raise ValueError('Not an Easy ECG AI context')
    if output.exists():raise ValueError('AI output exists; choose a new path')
    payload=json.dumps({'model':model,'stream':False,'prompt':PROMPT+json.dumps(context,ensure_ascii=False),
                        'options':{'temperature':0}}).encode('utf8')
    request=urllib.request.Request(endpoint,data=payload,headers={'Content-Type':'application/json'},method='POST')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=180) as response:
        raw=response.read(2*1024**2+1)
    if len(raw)>2*1024**2:raise ValueError('AI response exceeds 2 MiB')
    text=json.loads(raw).get('response')
    if not isinstance(text,str) or not text.strip():raise ValueError('AI endpoint returned no response text')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('# UNVALIDIERTER KI-TEXT - keine Diagnose\n\nModell: '+model+'\n\n'+text+'\n',encoding='utf8')
