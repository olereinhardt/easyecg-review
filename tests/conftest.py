from datetime import datetime
import binascii
import struct
import numpy as np
import pytest


def section(sid,body):
    header=struct.pack('<HHIBB6s',0,sid,16+len(body),13,13,b'SCPECG' if sid==0 else b'\0'*6)
    data=header+body
    return struct.pack('<H',binascii.crc_hqx(data[2:],0xffff))+data[2:]


def scp(words=None,date=datetime(2026,9,30,12),amp=806,interval=6666,diff=0):
    words=np.full(4500,2048,dtype='<u2') if words is None else np.asarray(words,dtype='<u2')
    tags=struct.pack('<BH',25,4)+struct.pack('<HBB',date.year,date.month,date.day)
    tags+=struct.pack('<BH',26,3)+bytes([date.hour,date.minute,date.second])+b'\xff\0\0'
    bodies={1:tags,2:bytes.fromhex('0100010000100100000008000000'),
            3:struct.pack('<BBIIBB',1,4,1,len(words),101,0),
            6:struct.pack('<HHBBH',amp,interval,diff,0,len(words)*2)+words.tobytes()}
    lengths={0:16+(len(bodies)+1)*10,**{i:16+len(b) for i,b in bodies.items()}}
    offset=7;pointers=b''
    for sid,length in lengths.items():
        pointers+=struct.pack('<HII',sid,length,offset);offset+=length
    payload=section(0,pointers)+b''.join(section(sid,b) for sid,b in bodies.items())
    rest=struct.pack('<I',6+len(payload))+payload
    return struct.pack('<H',binascii.crc_hqx(rest,0xffff))+rest


def index(ranges):
    return ('Easy ECG Monitor\r\nTotal records: '+str(len(ranges))+'\r\nNo. From To\r\n'+
            ''.join(f'{i} {lo}.scp {hi}.scp\r\n' for i,lo,hi in ranges)).encode('ascii')


def synthetic(duration=120,fs=150,beats=None,noise=0):
    t=np.arange(int(duration*fs))/fs;x=.012*np.sin(2*np.pi*.2*t)
    beats=np.arange(1,duration-1,.8) if beats is None else np.asarray(beats)
    for b in beats:
        x+=.70*np.exp(-((t-b)/.018)**2)-.14*np.exp(-((t-b+.035)/.014)**2)
        x+=.10*np.exp(-((t-b-.23)/.05)**2)+.06*np.exp(-((t-b+.18)/.04)**2)
    if noise:x+=np.random.default_rng(123).normal(0,noise,len(t))
    raw=np.clip(np.rint(x/.000806),-2048,2047).astype(np.int16)
    words=(raw.astype(np.int32)+2048).astype(np.uint16)
    return raw,words,beats
