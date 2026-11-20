"""Local waveform/energy evidence for the current Agent. No model or network."""
from __future__ import annotations
import argparse
from array import array
import json,math,subprocess,sys
from pathlib import Path
from inspect_finishing import ffmpeg_path,metadata,sha


def measure(media,output,*,start=0,end=None,ffmpeg=None,ffprobe=None):
    media=Path(media).resolve(strict=True);output=Path(output).resolve()
    binary=ffmpeg_path(ffmpeg);info=metadata(media,binary,ffprobe)
    end=info['duration'] if end is None else float(end)
    if not 0<=start<end<=info['duration']+.05:raise ValueError('Choose an interval inside the actual media')
    source={'file':str(media),'sha256':sha(media)}
    bins=[];step=.05;rate=16000
    if info['streams']['audio']:
        result=subprocess.run([binary,'-v','error','-ss',str(start),'-i',str(media),'-t',str(end-start),
            '-vn','-ac','2','-ar',str(rate),'-f','s16le','-'],capture_output=True)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1000:])
        samples=array('h');samples.frombytes(result.stdout[:len(result.stdout)//2*2])
        if sys.byteorder=='big':samples.byteswap()
        width=round(step*rate)*2
        for at in range(0,len(samples),width):
            block=samples[at:at+width]
            rms=math.sqrt(sum(v*v for v in block)/len(block))/32768
            peak=max(abs(v) for v in block)/32768
            bins.append({'start':round(at/(2*rate),4),'end':round((at+len(block))/(2*rate),4),
                         'rms_dbfs':round(20*math.log10(max(rms,1e-6)),2),'peak':round(peak,5)})
    quiet=[]
    for b in bins:
        if b['rms_dbfs']<-45:
            if quiet and abs(quiet[-1][1]-b['start'])<.001:quiet[-1][1]=b['end']
            else:quiet.append([b['start'],b['end']])
    quiet=[span for span in quiet if span[1]-span[0]>=.2]
    report={'version':1,'status':'measured','input':source,'source_interval':[start,end],
            'clock':'seconds relative to selected source interval','duration':end-start,'metadata':info,
            'bin_seconds':step,'bins':bins,'silence_candidates':quiet,'threshold_dbfs':-45,
            'semantic_audio_verified':False,'transcript':None,'external_model_calls':0,
            'limits':'Stereo energy envelope after 16kHz decoding; peaks are not true-peak measurements. Energy is not speech, words, speaker identity or musical meaning.'}
    if sha(media)!=source['sha256']:raise ValueError('Media changed during measurement')
    output.mkdir(parents=True,exist_ok=True)
    (output/'signal.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    stride=max(1,math.ceil(len(bins)/1200));points=[]
    for i in range(0,len(bins),stride):
        block=bins[i:i+stride];t=block[0]['start'];peak=max(b['peak'] for b in block)
        x=40+1120*t/(end-start);points.extend([f'{x:.2f},{150-110*peak:.2f}',f'{x:.2f},{150+110*peak:.2f}'])
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="320" viewBox="0 0 1200 320"><rect width="1200" height="320" fill="#18202b"/><path d="M40 150H1160" stroke="#64748b"/><polyline fill="none" stroke="#67d9bb" stroke-width="1" points="'+' '.join(points)+'"/><text x="40" y="30" fill="white" font-family="sans-serif" font-size="18">Measured signal envelope — not speech recognition</text><text x="40" y="295" fill="white" font-family="sans-serif">0s</text><text x="1070" y="295" fill="white" font-family="sans-serif">'+f'{end-start:.3f}s'+'</text></svg>'
    (output/'waveform.svg').write_text(svg,encoding='utf-8')
    report['report']=str(output/'signal.json');report['waveform']=str(output/'waveform.svg')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('media');p.add_argument('--output',required=True)
    p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--ffmpeg');a=p.parse_args()
    r=measure(a.media,a.output,start=a.start,end=a.end,ffmpeg=a.ffmpeg)
    print(json.dumps({k:r[k] for k in ('status','duration','report','waveform','semantic_audio_verified','external_model_calls')},ensure_ascii=False))
if __name__=='__main__':main()
