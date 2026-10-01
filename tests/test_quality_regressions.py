import numpy as np
from easyecg_review.analysis import analyze
from conftest import synthetic


def test_reproducible_steep_qrs_not_all_rejected_as_steps():
    fs=150;duration=120;t=np.arange(duration*fs)/fs
    x=.02*np.sin(2*np.pi*.2*t)
    for b in np.arange(1,duration-1,.8):
        x+=1.5*np.exp(-((t-b)/.007)**2)
        x-=.3*np.exp(-((t-b+.025)/.01)**2)
    raw=np.rint(x/.000806).astype(np.int16);words=(raw.astype(int)+2048).astype(np.uint16)
    result,_=analyze(raw,words,fs,.000806)
    assert result['summary']['usable_s']>=80
    assert result['summary']['candidate_counts']['premature_beat_candidate']==0


def test_quality_excludes_movement_but_keeps_raw_shape():
    raw,words,_=synthetic();original=words.copy()
    # Abrupt baseline offset, sufficiently long to test drift and a large step.
    raw[6000:6900]=np.clip(raw[6000:6900].astype(int)+1300,-2048,2047)
    words=(raw.astype(int)+2048).astype(np.uint16);copy=words.copy()
    result,_=analyze(raw,words,150,.000806)
    assert not result['windows'][4]['usable']
    np.testing.assert_array_equal(words,copy)
