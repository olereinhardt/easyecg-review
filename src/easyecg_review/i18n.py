"""UTF-8 catalogs and context-local language selection; no OS locale mutation."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from importlib.resources import files
import json
import os
from pathlib import Path

LANGUAGES = {'de':'Deutsch','en':'English','fr':'Français','es':'Español','pt':'Português',
    'zh':'简体中文','ja':'日本語','ru':'Русский','tr':'Türkçe','nl':'Nederlands','it':'Italiano',
    'ar':'العربية','uk':'Українська','pl':'Polski','cs':'Čeština','da':'Dansk','sv':'Svenska','nb':'Norsk bokmål'}
AI_LANGUAGES = dict(zip(LANGUAGES, ['German','English','French','Spanish','Portuguese','Simplified Chinese',
    'Japanese','Russian','Turkish','Dutch','Italian','Arabic','Ukrainian','Polish','Czech','Danish','Swedish','Norwegian Bokmål']))
_current = ContextVar('easyecg_language',default='de')

def normalize(code):
    base=str(code).split('.')[0].replace('_','-').lower().split('-')[0]
    if base=='no':base='nb'
    if base not in LANGUAGES:raise ValueError(f'Unsupported language: {code}; choose {", ".join(LANGUAGES)}')
    return base

@lru_cache(maxsize=18)
def catalog(code):
    return json.loads(files('easyecg_review').joinpath('locales',normalize(code)+'.json').read_text(encoding='utf8'))

def get_language():return _current.get()
def set_language(code):return _current.set(normalize(code))
@contextmanager
def using_language(code=None):
    token=set_language(code or get_language())
    try:yield get_language()
    finally:_current.reset(token)

def tr(key,**values):
    messages=catalog(get_language())
    template=messages.get(key,catalog('en').get(key))
    if template is None:raise KeyError(f'Unknown translation key: {key}')
    return template.format(**values)

def settings_path():
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'easyecg-review'/'settings.json'

def preferred_language():
    override=os.environ.get('EASYECG_LANGUAGE')
    if override:return normalize(override)
    try:
        value=json.loads(settings_path().read_text(encoding='utf8')).get('language')
        if value:return normalize(value)
    except (OSError,ValueError,TypeError,AttributeError):pass
    for name in ('LC_ALL','LC_MESSAGES','LANG'):
        value=os.environ.get(name)
        if value:
            try:return normalize(value)
            except ValueError:break
    return 'de'

def save_language(code):
    path=settings_path();path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps({'language':normalize(code)})+'\n',encoding='utf8');tmp.replace(path)

REASONS={'ADC-Grenzwerte/Clipping':'clipping','Flaches Signal/Kontakt prüfen':'flat',
 'Starke Basislinienbewegung':'baseline','Sprunghafte Signaländerung':'step','Starke hochfrequente Störung':'hf_noise',
 'Zu wenige QRS-Kandidaten':'few_qrs','Geringe QRS-Detektorübereinstimmung':'disagreement',
 'Nahezu flacher Teilabschnitt':'partial_flat','Teilweise Aufnahmerand':'edge','Aufnahmerand/Filterrand':'edge',
 'Unsichere Signalqualität':'uncertain_quality'}
def reason_text(reason):return tr(REASONS[reason]) if reason in REASONS else reason

def event_evidence(event):
    """Show language-neutral metrics plus a translated clinical caution.

    Original diagnostic prose remains verbatim in analysis.json/events.csv.
    This avoids silently rewriting technical evidence or changing the analysis.
    """
    import re
    if event['kind']=='poor_signal':return '; '.join(reason_text(r) for r in event['evidence'].split('; '))
    text=event['evidence']
    metrics=re.findall(r'(?:RR-CV|RMSSD|RR|Formkorrelation|Kontext-CV|QRS-Energiebreite|Energiebreite|Referenz|RR davor|danach)=([\d.]+)(s|ms)?',text)
    # Metric labels are standardized for reproducibility across languages.
    names=re.findall(r'(RR-CV|RMSSD|RR|Formkorrelation|Kontext-CV|QRS-Energiebreite|Energiebreite|Referenz|RR davor|danach)=',text)
    aliases={'Formkorrelation':'correlation','Kontext-CV':'context-CV','QRS-Energiebreite':'energy-width',
             'Energiebreite':'energy-width','Referenz':'reference-RR','RR davor':'RR-before','danach':'RR-after'}
    details=', '.join(f'{aliases.get(name,name)}={value}{unit}' for name,(value,unit) in zip(names,metrics))
    return tr('technical_details',details=details) if details else tr(event['kind'])

ERROR_KEYS={'Output directory must be new or empty (no silent overwrite)':'output_not_empty',
 'Choose output outside the input directory':'output_inside','Input must be an Easy ECG directory or ZIP':'invalid_input',
 'No valid data to export':'no_data','No recordings selected':'no_recordings'}
def error_text(error):
    message=str(error)
    if message in ERROR_KEYS:return tr(ERROR_KEYS[message])
    if message.startswith('Unknown recording IDs: '):return tr('unknown_ids',ids=message.split(': ',1)[1])
    return message
