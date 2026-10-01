from datetime import datetime,timedelta
from pathlib import Path
import binascii
import struct
import zipfile
import numpy as np
import pytest
from easyecg_review.io import parse_scp,parse_index,load_recordings,FormatError
from conftest import scp,index


def test_decode_calibration_flags_and_time():
    words=np.arange(4500,dtype=np.uint16)%4096;words[15]|=0xc000
    b=parse_scp(scp(words),17,'17.SCP')
    assert b.start==datetime(2026,9,30,12)
    np.testing.assert_array_equal(b.words,words)
    np.testing.assert_array_equal(b.centered,(words&4095).astype(np.int32)-2048)
    assert b.amplitude_nv==806 and b.interval_us==6666

@pytest.mark.parametrize('corruption',['truncate','payload','length','section_crc'])
def test_corruption_rejected(corruption):
    b=bytearray(scp())
    if corruption=='truncate':b=b[:-3]
    elif corruption=='payload':b[-5]^=1
    elif corruption=='length':b[2]^=1
    else:
        b[6]^=1;b[:2]=struct.pack('<H',binascii.crc_hqx(b[2:],0xffff))
    with pytest.raises(FormatError):parse_scp(bytes(b))

@pytest.mark.parametrize('kwargs',[{'diff':1},{'amp':0},{'interval':0}])
def test_unsupported_signal_rejected(kwargs):
    with pytest.raises(FormatError):parse_scp(scp(**kwargs))


def test_index_overlap_and_total():
    assert parse_index(index([(1,1,3),(2,4,4)]))==[(1,1,3),(2,4,4)]
    with pytest.raises(FormatError):parse_index(index([(1,1,3),(2,3,4)]))
    with pytest.raises(FormatError):parse_index(index([(1,1,3)]).replace(b'Total records: 1',b'Total records: 2'))


def make_input(tmp_path,missing=False,gap=False):
    root=tmp_path/'input';root.mkdir();(root/'README.TXT').write_bytes(index([(1,299,301)]))
    for n in range(299,302):
        if missing and n==300:continue
        d=root/('ECG_0' if n<=300 else 'ECG_1');d.mkdir(exist_ok=True)
        delta=(n-299)*30+(30 if gap and n==301 else 0)
        (d/f'{n}.SCP').write_bytes(scp(date=datetime(2026,9,30,12)+timedelta(seconds=delta)))
    return root


def test_cross_directory_session(tmp_path):
    r,m=load_recordings(make_input(tmp_path))
    assert len(r)==1 and r[0].duration==90 and len(m['files'])==3


def test_missing_rejected_or_split(tmp_path):
    root=make_input(tmp_path,missing=True)
    with pytest.raises(FormatError):load_recordings(root)
    r,m=load_recordings(root,True)
    assert len(r)==2 and all(x.duration==30 for x in r)
    assert m['skipped'][0]['number']==300


def test_time_gap_splits_without_fill(tmp_path):
    r,m=load_recordings(make_input(tmp_path,gap=True))
    assert [x.duration for x in r]==[60,30] and m['warnings']


def test_zip_traversal_rejected(tmp_path):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('../evil',b'x')
    with pytest.raises(FormatError):load_recordings(path)


def test_zip_case_duplicate_rejected(tmp_path):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('a.SCP',b'x');z.writestr('a.scp',b'x')
    with pytest.raises(FormatError):load_recordings(path)
