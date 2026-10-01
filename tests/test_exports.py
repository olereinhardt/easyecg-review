import numpy as np
import pyedflib
import wfdb
from easyecg_review.io import parse_scp,Recording
from easyecg_review.export import write_exports
from easyecg_review.analysis import analyze
from conftest import scp,synthetic


def test_edf_wfdb_roundtrip_and_status_preservation(tmp_path):
    raw,words,_=synthetic(duration=30);words[100]|=0x8000
    rec=Recording(1,1,[parse_scp(scp(words))],150)
    result,_=analyze(raw,words,150,.000806)
    write_exports(tmp_path,rec,result)
    with pyedflib.EdfReader(str(tmp_path/(rec.name+'.edf'))) as reader:
        np.testing.assert_array_equal(reader.readSignal(0,digital=True),raw)
        assert reader.getSampleFrequency(0)==150
        assert reader.getStartdatetime()==rec.start
        assert reader.getPhysicalDimension(0)=='mV'
        assert np.max(abs(reader.readSignal(0)-raw*.000806))<.000003
        assert any('unverified' in t for t in reader.readAnnotations()[2])
    read=wfdb.rdrecord(str(tmp_path/rec.name),physical=False)
    np.testing.assert_array_equal(read.d_signal[:,0],raw)
    assert read.adc_gain==[1/.000806] and read.base_datetime==rec.start
    np.testing.assert_array_equal(np.load(tmp_path/'raw.npz')['device_words'],words)
    ann=wfdb.rdann(str(tmp_path/rec.name),'qrs');assert set(ann.symbol)=={'Q'}


def test_partial_second_padding_explicit(tmp_path):
    raw,words,_=synthetic(duration=30);words=words[:-1];raw=raw[:-1]
    rec=Recording(1,1,[parse_scp(scp(words))],150)
    result,_=analyze(raw,words,150,.000806)
    write_exports(tmp_path,rec,result,('edf',))
    assert result['edf']['padding_samples']==1
    with pyedflib.EdfReader(str(tmp_path/(rec.name+'.edf'))) as reader:
        assert len(reader.readSignal(0))==4500
        assert any('PADDING' in t for t in reader.readAnnotations()[2])
    assert len(np.load(tmp_path/'raw.npz')['raw_centered'])==4499
