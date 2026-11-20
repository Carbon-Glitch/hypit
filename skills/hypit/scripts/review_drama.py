"""Prepare resumable actual audiovisual evidence and a optional current-Agent context.

The proxy runs at1x with original sound; observations are not film acceptance.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path
from post_timeline import read,save,ref,number,editorial_metrics
from inspect_finishing import ffmpeg_path,metadata
from dialogue_guard import transcribe


def prepare(media,folder,*,start=0,end=None,context=None,ffmpeg=None,ffprobe=None):
    media=Path(media).resolve(strict=True);folder=Path(folder).resolve();binary=ffmpeg_path(ffmpeg)
    data=metadata(media,binary,ffprobe);end=data['duration'] if end is None else number(end,'review end',.001)
    if not 0<=start<end<=data['duration']+.001:raise ValueError('Review actual media inside its decoded duration')
    scope={'input':ref(media),'interval':[start,end],'context':ref(context) if context else None,'proxy_rate':1,
           'purpose':'Actual scoped audiovisual diagnosis; no prefilled artistic verdict'}
    target=folder/'evidence.json'
    if target.exists():
        previous=read(target)
        if previous['scope']!=scope:raise ValueError('Evidence folder belongs to another scope; use a versioned folder')
        if ref(previous['proxy']['file'])!=previous['proxy']:raise ValueError('Actual review proxy changed')
        return previous
    folder.mkdir(parents=True,exist_ok=True);proxy=folder/'actual-av.mp4'
    args=[binary,'-v','error','-nostdin','-y','-ss',str(start),'-i',str(media),'-t',str(end-start),'-map','0:v:0','-map','0:a:0?',
          '-vf',r'scale=min(768\,iw):-2','-c:v','libx264','-preset','fast','-crf','25','-c:a','aac','-b:a','96k','-ar','32000','-movflags','+faststart',str(proxy)]
    run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (folder/'proxy.log').write_text(run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError('Cannot prepare actual audiovisual proxy: '+run.stderr[-1200:])
    words=transcribe(proxy) if data['streams']['audio'] else {'status':'not_applicable','segments':[]}
    selected=[]
    for segment in words.get('segments',[]):
        part=dict(segment)
        part['words']=segment.get('words',[])
        selected.append(part)
    value={'version':1,'scope':scope,'proxy':ref(proxy),'actual_duration':metadata(proxy,binary,ffprobe)['duration'],
           'word_timing':{'status':words['status'],'segments':selected,'clock':'relative to supplied proxy; only existing provided timestamps, not new recognition'},
           'artistic_accepted':False,'note':'Proxy preserves speed and sound but lowers spatial resolution; inspect original frames around cuts/contacts/typography.'}
    if ref(media)!=scope['input']:raise ValueError('Source changed during proxy preparation')
    if data['streams']['audio']:
        from audio_signal import measure
        signal=measure(media,folder/'signal',start=start,end=end,ffmpeg=binary,ffprobe=ffprobe)
        value['audio_signal']={k:signal[k] for k in ('report','waveform','semantic_audio_verified')}
    save(target,value);return value


def writing_request(evidence_path,project,output,batch,task,*,inputs=None,source_kind=None,source_shot_table=None,source_shot_context=None,execution_packet=None):
    evidence_path=Path(evidence_path).resolve();data=read(evidence_path);project=Path(project).resolve()
    if ref(data['scope']['input']['file'])!=data['scope']['input'] or ref(data['proxy']['file'])!=data['proxy']:
        raise ValueError('Actual review media no longer matches observation scope')
    request={'version':1,'project_root':str(project),'scope':task,'batch':batch,'source_kind':source_kind or ('reference' if source_shot_table or execution_packet else 'original'),'autonomous_finish':True,
            'task':task+' Return the requested executable EDIT JSON; observations vs creative changes stay distinct. Do not invent a pass. '+
                   'Current Agent reviews the available video. If audio cannot be heard, inspect provided signal data and retain unknown words/timbre. Use the supplied drama-editing method to choose performance, listener reactions, attention and action cuts before tightening waits or speed. '+
                   'Use existing supplied word boundaries when available, otherwise waveform/energy is only approximate timing; visual timing estimates need original-frame confirmation. '+
                   'Actual proxy duration is '+str(data['actual_duration'])+' seconds. Times outside it are invalid; do not claim coverage from impossible estimates. '+
                   'Explicitly diagnose cumulative pace and musical support/development/exit, beyond describing the plot. '+
                   'Important cut reasons belong in the existing EDIT, not new reports.',
            'inputs':[{'file':str(evidence_path),'kind':'actual-audiovisual-evidence'},*(inputs or [])],
            'videos':[{'file':data['proxy']['file'],'source':data['scope']['input'],'source_interval':data['scope']['interval'],'label':'Actual rough-cut audio/video at1x'}],
            'outputs':[{'file':output,'role':'post','coverage':task,'instruction':'Valid executable JSON only; use existing target words and actual media paths/clocks. Include observations, edit reasons and remaining_issues inside the same JSON.'}],
            'max_output_tokens':12000}
    receipt_path=Path(data['scope']['input']['file']+'.post.json')
    if receipt_path.is_file():
        receipt=read(receipt_path)
        if receipt.get('output')==data['scope']['input'] and receipt.get('compiled'):
            compiled=receipt['compiled']
            metrics=editorial_metrics(compiled['clips'],compiled['audio'],compiled['duration'],
                                      compiled.get('pacing',{}).get('source_duration'))
            request['task']+=' Measured clocks for the WHOLE current edit, not local proxy-relative seconds: '+json.dumps(metrics,ensure_ascii=False)+'. Uncovered music is a review candidate; native music and purposeful effects may remain.'
    for key,value in (('source_shot_table',source_shot_table),('source_shot_context',source_shot_context),('execution_packet',execution_packet)):
        if value:request[key]=str((project/value).resolve(strict=True))
    if request['source_kind']=='reference' and not (source_shot_table or execution_packet):
        raise ValueError('Reference post writing needs the existing canonical source table or selected execution packet')
    return request


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('media',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--context',type=Path)
    p.add_argument('--writing-request',type=Path);p.add_argument('--project',type=Path);p.add_argument('--edit-file',default='EDIT.json');p.add_argument('--batch',default='post-actual-v1');p.add_argument('--task',default='Actual short-drama editorial and sound finishing')
    p.add_argument('--source-kind',choices=['original','reference']);p.add_argument('--source-shot-table',type=Path);p.add_argument('--source-shot-context',type=Path);p.add_argument('--execution-packet',type=Path)
    p.add_argument('--ffmpeg');p.add_argument('--ffprobe');a=p.parse_args()
    try:
        data=prepare(a.media,a.output,start=a.start,end=a.end,context=a.context,ffmpeg=a.ffmpeg,ffprobe=a.ffprobe)
        if a.writing_request:
            if not a.project:raise ValueError('Writing request needs an existing project root')
            save(a.writing_request,writing_request(a.output/'evidence.json',a.project,a.edit_file,a.batch,a.task,
                                                  inputs=[{'file':str(a.context.resolve()),'kind':'current-edit-intent-and-scope'}] if a.context else [],
                                                  source_kind=a.source_kind,source_shot_table=a.source_shot_table,
                                                  source_shot_context=a.source_shot_context,execution_packet=a.execution_packet))
        print(json.dumps({'evidence':str((a.output/'evidence.json').resolve()),'duration':data['actual_duration'],'word_status':data['word_timing']['status'],'artistic_accepted':False},ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,RuntimeError) as exc:print('POST_REVIEW_PREPARE_FAILED: '+str(exc));return 1
if __name__=='__main__':raise SystemExit(main())
