"""Measure onset candidates in existing music; no cloud or tempo-grid invention."""
from __future__ import annotations
from array import array
import math
from pathlib import Path
import statistics
import subprocess
import sys

from inspect_finishing import ffmpeg_path, metadata
from post_timeline import ref


def onset_candidates(samples, rate, *, hop_seconds=.01, separation=.18):
    hop=max(1,round(rate*hop_seconds))
    # Difference energy emphasizes transients over a sustained pad or DC offset.
    energies=[]
    previous=0
    for begin in range(0,len(samples),hop):
        block=samples[begin:begin+hop]
        total=0.
        for value in block:
            change=value-previous;total+=change*change;previous=value
        energies.append(math.sqrt(total/max(1,len(block))))
    floor=max(energies,default=0)*.015
    if floor<=0:return []
    novelty=[max(0,value-(energies[i-1] if i else 0)) for i,value in enumerate(energies)]
    peaks=[]
    radius=max(1,round(.5/hop_seconds))
    for i,value in enumerate(novelty):
        local=novelty[max(0,i-radius):i+radius+1]
        threshold=max(floor,statistics.median(local)*3)
        if value<=threshold:continue
        if i and value<novelty[i-1]:continue
        if i+1<len(novelty) and value<novelty[i+1]:continue
        candidate={'time':round(i*hop/rate,4),'strength':value}
        if peaks and candidate['time']-peaks[-1]['time']<separation:
            if value>peaks[-1]['strength']:peaks[-1]=candidate
        else:peaks.append(candidate)
    maximum=max((p['strength'] for p in peaks),default=1)
    return [{**p,'strength':round(p['strength']/maximum,4)} for p in peaks]


def analyze(media, *, start=0, end=None, ffmpeg=None):
    media=Path(media).resolve(strict=True);binary=ffmpeg_path(ffmpeg)
    info=metadata(media,binary)
    end=info['duration'] if end is None else end
    if not info['streams']['audio'] or not 0<=start<end<=info['duration']+.001:
        raise ValueError('Choose a real music source interval')
    rate=11025
    run=subprocess.run([binary,'-v','error','-ss',str(start),'-i',str(media),'-t',str(end-start),
                        '-vn','-ac','1','-ar',str(rate),'-f','s16le','-'],capture_output=True)
    if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace')[-800:])
    samples=array('h');samples.frombytes(run.stdout[:len(run.stdout)//2*2])
    if sys.byteorder=='big':samples.byteswap()
    peaks=onset_candidates(samples,rate)
    intervals=[b['time']-a['time'] for a,b in zip(peaks,peaks[1:]) if .25<=b['time']-a['time']<=1.5]
    period=statistics.median(intervals) if len(intervals)>=4 else None
    consistency=sum(abs(x-period)<=max(.035,period*.1) for x in intervals)/len(intervals) if period else 0
    for peak in peaks:peak['time']=round(start+peak['time'],4)
    return {'version':1,'source':ref(media),'source_interval':[start,end],'clock':'original source seconds',
            'method':'10ms transient-energy peaks; measured onsets, not downbeat recognition',
            'onsets':peaks,'bpm_candidate':round(60/period,2) if period and consistency>=.7 else None,
            'pulse_consistency':round(consistency,3),'downbeats_verified':False,
            'use':'Audition selected peaks; align a chosen music source peak to a dramatic output event. Preserve dialogue and reaction timing.'}
