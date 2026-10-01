import numpy as np
from easyecg_review.analysis import analyze,detect_peaks,filter_ecg,matches
from conftest import synthetic


def test_clean_detection_matches_known_beats():
    raw,words,beats=synthetic()
    result,_=analyze(raw,words,150,.000806)
    detected=np.asarray([b['sample'] for b in result['beats']])
    truth=np.rint(beats*150).astype(int)
    assert matches(truth,detected,15).mean()>.98
    assert matches(detected,truth,15).mean()>.98
    assert result['summary']['usable_s']>=90
    assert abs(result['summary']['rate_window_median_bpm']-75)<1
    assert result['summary']['candidate_counts']['premature_beat_candidate']==0
    assert result['summary']['confirmed_extrasystoles'] is None


def test_inverted_ecg_detection():
    raw,_,beats=synthetic();raw=-raw;words=(raw.astype(int)+2048).astype(np.uint16)
    result,_=analyze(raw,words,150,.000806)
    detected=np.asarray([b['sample'] for b in result['beats']])
    assert matches(np.rint(beats*150),detected,15).mean()>.97


def test_controlled_premature_pattern():
    beats=np.arange(1,119,.8);i=np.argmin(abs(beats-50));beats[i]-=.28
    raw,words,_=synthetic(beats=beats)
    result,_=analyze(raw,words,150,.000806)
    events=[e for e in result['events'] if e['kind']=='premature_beat_candidate']
    assert len(events)==1 and abs(events[0]['onset_s']-beats[i])<.1


def test_long_interval_candidate():
    beats=np.arange(1,119,.8);beats=beats[(beats<50)|(beats>52)]
    # Background activity distinguishes this from an almost-flat dropout.
    raw,words,_=synthetic(beats=beats,noise=.004)
    result,_=analyze(raw,words,150,.000806)
    events=[e for e in result['events'] if e['kind']=='long_rr_candidate']
    assert events and events[0]['duration_s']>=2


def test_flat_and_clipped_excluded():
    raw=np.zeros(18000,dtype=np.int16);words=(raw.astype(int)+2048).astype(np.uint16)
    result,_=analyze(raw,words,150,.000806)
    assert result['summary']['usable_s']==0
    assert result['summary']['confirmed_extrasystoles'] is None
    raw,words,_=synthetic();raw[6000:6600]=2047;words[6000:6600]=4095
    result,_=analyze(raw,words,150,.000806)
    assert not result['windows'][4]['usable']


def test_motion_impulse_excludes_rhythm_events():
    raw,words,_=synthetic();raw[6000:6100]=1500;words[6000:6100]=3548
    result,_=analyze(raw,words,150,.000806)
    assert not result['windows'][4]['usable']
    assert not any(40<=e['onset_s']<50 and e['kind']!='poor_signal' for e in result['events'])
