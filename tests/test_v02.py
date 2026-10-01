"""Regression cases for detection, filtering, dropout and explicit selection."""
from datetime import timedelta
import json
import numpy as np
import pytest
from scipy.signal import periodogram
from conftest import synthetic,scp,index
from easyecg_review.analysis import analyze
from easyecg_review.detection import clean_signal
from easyecg_review.cli import load_config,main
from easyecg_review.gui import build_run_command
from easyecg_review.io import load_recordings,list_recordings,FormatError


def test_frequent_bigeminy_not_rejected_for_lack_of_regular_context():
    beats=np.arange(1,119,.8)
    beats[10:130:2]-=.28
    raw,words,_=synthetic(beats=beats)
    result,_=analyze(raw,words,150,.000806)
    expected=beats[10:130:2]
    found=np.asarray([e['onset_s'] for e in result['events'] if e['kind']=='premature_beat_candidate'])
    assert sum(np.min(abs(found-b))<.1 for b in expected)>=.95*len(expected)
    assert result['summary']['candidate_counts']['bigeminy_candidate']>=1



def test_frequent_trigeminy_context():
    beats=np.arange(1,119,.8);beats[12:132:3]-=.28
    raw,words,_=synthetic(beats=beats)
    result,_=analyze(raw,words,150,.000806)
    expected=beats[12:132:3]
    found=np.asarray([e['onset_s'] for e in result['events'] if e['kind']=='premature_beat_candidate'])
    assert len(found)>0 and sum(np.min(abs(found-b))<.1 for b in expected)>=.95*len(expected)
    assert result['summary']['candidate_counts']['trigeminy_candidate']>=1

def test_noncompensatory_early_beat():
    beats=np.arange(1,119,.8);j=60
    beats[j:]-=.30  # reset rhythm: follower is normal, no long recovery interval
    raw,words,_=synthetic(beats=beats)
    result,_=analyze(raw,words,150,.000806)
    assert any(e['kind']=='premature_beat_candidate' and abs(e['onset_s']-beats[j])<.1 for e in result['events'])


def test_large_broad_t_waves_do_not_double_beat_count():
    raw,_,beats=synthetic();t=np.arange(len(raw))/150;x=raw*.000806
    for b in beats:x+=.30*np.exp(-((t-b-.28)/.065)**2)
    raw=np.rint(x/.000806).astype(np.int16);words=(raw.astype(int)+2048).astype(np.uint16)
    result,_=analyze(raw,words,150,.000806)
    p=np.asarray([b['time_s'] for b in result['beats']])
    assert sum(min(abs(beats-v))>.1 for v in p)<=2
    assert sum(min(abs(p-v))>.1 for v in beats)<=2


def test_flat_dropout_is_not_counted_as_pause():
    raw,words,_=synthetic();lo,hi=50*150,56*150
    raw[lo:hi]=0;words[lo:hi]=2048
    result,_=analyze(raw,words,150,.000806)
    assert any(e['kind']=='signal_dropout' and e['duration_s']>5 for e in result['events'])
    assert not any(e['kind']=='long_rr_candidate' and e['onset_s']<56 and e['onset_s']+e['duration_s']>50 for e in result['events'])
    assert not any(b['usable'] for b in result['beats'] if 50<b['time_s']<56)


def test_auto_mains_notch_and_baseline_rejection_are_phase_neutral():
    raw,_,beats=synthetic();fs=150;t=np.arange(len(raw))/fs;x=raw*.000806
    noisy=x+.18*np.sin(2*np.pi*50*t)+.20*np.sin(2*np.pi*.12*t)
    auto,info=clean_signal(noisy,fs,'auto');off,_=clean_signal(noisy,fs,'off')
    assert info['applied_notch_hz']==50
    f,pauto=periodogram(auto[300:-300],fs);_,poff=periodogram(off[300:-300],fs)
    assert pauto[np.argmin(abs(f-50))]<.01*poff[np.argmin(abs(f-50))]
    assert pauto[np.argmin(abs(f-.12))]<.01*periodogram(noisy[300:-300],fs)[1][np.argmin(abs(f-.12))]
    for b in beats[4:-4]:
        center=round(b*fs);assert abs(np.argmax(auto[center-5:center+6])-5)<=1
    _,clean_info=clean_signal(x,fs,'auto');assert clean_info['applied_notch_hz']==0


def test_selection_only_decodes_selected_scp_and_inventory_marks_error(tmp_path):
    root=tmp_path/'device';(root/'ECG_0').mkdir(parents=True)
    (root/'README.TXT').write_bytes(index([(1,1,1),(2,2,2)]))
    (root/'ECG_0/1.SCP').write_bytes(scp());bad=bytearray(scp());bad[-1]^=1
    (root/'ECG_0/2.SCP').write_bytes(bad)
    rows=list_recordings(root);assert [r['index'] for r in rows]==[1,2]
    assert rows[0]['error'] is None and 'CRC' in rows[1]['error']
    recs,manifest=load_recordings(root,selected_ids=[1]);assert [r.index for r in recs]==[1]
    assert len(manifest['files'])==1 and len(manifest['ranges'])==2
    with pytest.raises(FormatError,match='CRC'):load_recordings(root)
    with pytest.raises(FormatError,match='No recordings'):load_recordings(root,selected_ids=[])
    with pytest.raises(FormatError,match='Unknown'):load_recordings(root,selected_ids=[3])


def test_gui_command_never_treats_empty_selection_as_all():
    with pytest.raises(ValueError,match='Messreihe'):build_run_command('source','out',[])
    cmd=build_run_command('source','out',[3,1],full=True)
    assert cmd[cmd.index('--recordings')+1:cmd.index('--gain-factor')]==['1','3']
    assert cmd[cmd.index('--gain-factor')+1]=='2.0'
    assert '--full-curves' in cmd
    with pytest.raises(ValueError):build_run_command('source','out',[1],gain=float('nan'))


def test_config_allows_mains_mode_and_rejects_invalid_cutoff(tmp_path):
    path=tmp_path/'config.json';path.write_text(json.dumps({'mains_mode':'50','highpass_hz':.7}))
    assert load_config(path).mains_mode=='50'
    path.write_text('{"lowpass_hz":76}')
    with pytest.raises(ValueError):load_config(path)


def test_display_gain_changes_report_only(tmp_path):
    root=tmp_path/'device';(root/'ECG_0').mkdir(parents=True)
    raw,words,_=synthetic(duration=30)
    (root/'README.TXT').write_bytes(index([(1,1,1)]));(root/'ECG_0/1.SCP').write_bytes(scp(words))
    import pyedflib
    from pypdf import PdfReader
    arrays=[]
    for factor in (1,2):
        out=tmp_path/f'results{factor}'
        assert main(['run',str(root),'-o',str(out),'--recordings','1','--gain-factor',str(factor),'--full-curves'])==0
        manifest=json.loads((out/'manifest.json').read_text())
        assert manifest['display']['review_mm_per_mv']==10*factor
        pdf=''.join(p.extract_text() for p in PdfReader(out/'review_strips.pdf').pages)
        assert f'{10*factor} mm/mV' in pdf
        with pyedflib.EdfReader(str(next(out.glob('r*/*.edf')))) as reader:arrays.append(reader.readSignal(0,digital=True))
        assert manifest['status']=='complete'
    np.testing.assert_array_equal(arrays[0],raw);np.testing.assert_array_equal(arrays[1],raw)
