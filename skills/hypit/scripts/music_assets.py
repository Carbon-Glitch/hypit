"""Obtain real music/sound assets, extract audition ranges and identify source music.

Recognition is a lead, not proof of original-version matching or availability.
"""
from __future__ import annotations
import argparse,asyncio,copy,hashlib,json,os,shutil,subprocess,sys,urllib.request
from pathlib import Path
from urllib.parse import urlparse,quote
from post_timeline import save,read,ref
from inspect_finishing import ffmpeg_path,metadata


def extract(media,output,start=0,end=None,*,ffmpeg=None):
    media=Path(media).resolve(strict=True);output=Path(output).resolve();binary=ffmpeg_path(ffmpeg);data=metadata(media,binary)
    end=data['duration'] if end is None else end
    if not data['streams']['audio'] or not 0<=start<end<=data['duration']+.001:raise ValueError('Extract an actual audio range')
    if output==media:raise ValueError('Preserve original source')
    sidecar=output.with_suffix(output.suffix+'.source.json');scope={'input':ref(media),'interval':[start,end],'playback_rate':1}
    if output.exists():
        prior=read(sidecar) if sidecar.exists() else {}
        if prior.get('scope')==scope and prior.get('output')==ref(output):return prior
        raise ValueError('Audio output belongs to another source/range; use a new version')
    output.parent.mkdir(parents=True,exist_ok=True)
    run=subprocess.run([binary,'-v','error','-nostdin','-n','-ss',str(start),'-i',str(media),'-t',str(end-start),
                        '-vn','-ac','2','-ar','48000','-c:a','pcm_s24le',str(output)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if run.returncode:raise RuntimeError('Cannot extract audition audio: '+run.stderr[-800:])
    result={'version':1,'scope':scope,'output':ref(output),'probe':metadata(output,binary),'listened':False};save(sidecar,result);return result


def acquire(url,output,*,page,title,kind='replacement',ffmpeg=None):
    output=Path(output).resolve();receipt=output.with_suffix(output.suffix+'.asset.json')
    if output.exists():
        old=read(receipt) if receipt.exists() else {}
        if old.get('origin_url')==url and old.get('asset')==ref(output):return old
        raise ValueError('Preserve existing music asset; use a new filename')
    if urlparse(url).scheme!='https':raise ValueError('Use an actual HTTPS audio file URL selected from a source page')
    output.parent.mkdir(parents=True,exist_ok=True);partial=output.with_suffix(output.suffix+'.part')
    request=urllib.request.Request(quote(url,safe=":/?#[]@!$&'()*+,;=%~"),headers={'User-Agent':'Hypit-Asset-Acquisition/1.0'})
    with urllib.request.urlopen(request,timeout=90) as response,partial.open('wb') as stream:
        if 'text/html' in response.headers.get('Content-Type',''):raise ValueError('A source page is not a downloadable audio file')
        shutil.copyfileobj(response,stream)
    binary=ffmpeg_path(ffmpeg);data=metadata(partial,binary)
    if not data['streams']['audio']:raise ValueError('Downloaded asset has no audio')
    partial.replace(output)
    result={'version':1,'asset':ref(output),'title':title,'origin_url':url,'source_page':page,'kind':kind,
            'actual_duration':data['duration'],'status':'candidate','listened':False,'original_match_verified':False,
            'next':'Audition the actual used range and join; original/recovered/replacement cue mapping is a separate directing decision'}
    save(receipt,result);return result


def recognize(media,output):
    media=Path(media).resolve(strict=True);output=Path(output).resolve();source=ref(media)
    if output.exists():
        previous=read(output)
        if previous.get('input')!=source:raise ValueError('Recognition cache belongs to different audio bytes')
        return previous
    python=Path.home()/'.hypit/tools/music-recognition'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        import importlib.util
        if importlib.util.find_spec('shazamio'):python=Path(sys.executable)
        else:
            value={'input':source,'status':'optional_tool_unavailable','next':'Use available song identification/web search, or provision shazamio in .hypit/tools/music-recognition; continue music selection without a new approval pause'}
            save(output,value);return value
    code='import asyncio,json,sys; from shazamio import Shazam; r=asyncio.run(Shazam().recognize(sys.argv[1])); print(json.dumps(r,ensure_ascii=False))'
    run=subprocess.run([str(python),'-c',code,str(media)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=100)
    if run.returncode:
        value={'input':source,'status':'recognition_unavailable','next':'Continue mood-based selection. Only try further original-track identification/separation when that identity is required; failure does not mean no BGM.'}
    else:
        data=json.loads(run.stdout);track=data.get('track',{})
        value={'input':source,'status':'candidate_found' if track else 'not_identified','track':track,
               'matches':data.get('matches',[]),'original_version_verified':False,
               'next':'Treat identity as an optional lead; select and audition music for the target mood, transitions and ending. Recognition is not a download or final music acceptance.'}
    save(output,value);return value


def search_queries(cue):
    mode=cue.get('mode','mood_first')
    if mode not in {'mood_first','source_match'}:raise ValueError('Music search mode must be mood_first or source_match')
    identity=' '.join(str(cue.get(k,'')) for k in ('title','artist')).strip()
    def terms(value):return ' '.join(map(str,value)) if isinstance(value,list) else str(value)
    description=' '.join(terms(cue.get(k,'')) for k in ('mood','instruments','rhythm','development','ending')).strip()
    known=[identity+' official audio',identity+' instrumental version'] if identity else []
    fitting=[description+' cinematic underscore',description+' site:mixkit.co/free-stock-music',description+' site:pixabay.com/music'] if description else []
    queries=(fitting+known if mode=='mood_first' else known+fitting)[:4]
    if not queries:raise ValueError('Provide observed identity or concrete music characteristics, not an invented song title')
    return {'mode':mode,'queries':queries,'action':'Audition real usable ranges against the target scene, including transitions and ending. Mood/fit leads by default; identification is optional unless source_match is explicitly required. Obtain the actual file and keep its source/use basis.'}


def separate(media,folder,model,executable=None):
    tool=executable or shutil.which('audio-separator')
    if not tool:
        return {'status':'optional_tool_unavailable','next':'Obtain original music, use an already available separation route, or select a functional replacement. Do not claim clean stems or stop the rest of post.'}
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    receipt=folder/'separation.json'
    scope={'input':ref(media),'model':model}
    if receipt.exists():
        old=read(receipt)
        if old.get('scope')!=scope:raise ValueError('Separation folder belongs to another input/model')
        if old.get('status')=='completed' and all(ref(r['file'])==r for r in old.get('files',[])):return old
        raise ValueError('Inspect previous separation state before starting another model job')
    save(receipt,{'scope':scope,'status':'started'})
    run=subprocess.run([str(tool),str(Path(media).resolve()),'--model_filename',model,'--output_dir',str(folder),'--output_format','WAV'],
                       capture_output=True,text=True,encoding='utf-8',errors='replace')
    (folder/'separation.log').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
    outputs=[ref(p) for p in folder.glob('*.wav')]
    value={'scope':scope,'status':'completed' if run.returncode==0 and outputs else 'failed','files':outputs,
           'clean_stems_verified':False,'next':'Listen for missing words, residual music, effects and separation artifacts before using any stem'}
    save(receipt,value);return value


def audition(media,output,start=0,end=None,*,label=None,ffmpeg=None):
    """Small real-audio MP4 for the already supported Gemini video input path."""
    media=Path(media).resolve(strict=True);output=Path(output).resolve();binary=ffmpeg_path(ffmpeg)
    info=metadata(media,binary);end=min(info['duration'],start+20) if end is None else end
    if not info['streams']['audio'] or not 0<=start<end<=info['duration']+.001:raise ValueError('Audition needs a real retained audio interval')
    if output.suffix.lower()!='.mp4' or output==media:raise ValueError('Use a separate MP4 audition output')
    scope={'source':ref(media),'source_interval':[start,end]};receipt=output.with_suffix('.audition.json')
    if output.exists():
        old=read(receipt) if receipt.exists() else {}
        if all(old.get(k)==v for k,v in scope.items()) and old.get('asset')==ref(output):return old
        raise ValueError('Audition scope changed; use a new preview filename')
    output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_name(output.stem+'.pending.mp4')
    args=[binary,'-v','error','-nostdin','-n','-f','lavfi','-i','color=c=0x111827:s=320x180:r=12',
          '-ss',str(start),'-i',str(media),'-t',str(end-start),'-map','0:v:0','-map','1:a:0',
          '-c:v','libx264','-preset','veryfast','-crf','30','-pix_fmt','yuv420p',
          '-c:a','aac','-b:a','96k','-ar','24000','-movflags','+faststart',str(temporary)]
    run=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if run.returncode:raise RuntimeError('Cannot prepare real music audition: '+run.stderr[-700:])
    actual=metadata(temporary,binary)
    if not actual['streams']['audio'] or abs(actual['duration']-(end-start))>.15:raise ValueError('Audition duration/audio differs from the chosen interval')
    temporary.replace(output)
    result={**scope,'file':str(output),'asset':ref(output),'label':label or 'Actual music candidate audio; neutral still is not scene footage',
            'duration':actual['duration'],'listened':False,'clock':'proxy0 corresponds to source_interval start; no speed/gain processing'}
    save(receipt,result);return result


def attach_music(request,selection,folder,*,batch=None):
    """Attach real audio to existing pre-score, storyboard or post requests."""
    request=Path(request).resolve();selection=Path(selection).resolve();folder=Path(folder).resolve()
    data=copy.deepcopy(read(request));chosen=read(selection);notes=[];videos=[]
    roles={o['role'] for o in data['outputs']}
    if not roles or not roles<={'design','treatment','director','screenplay','storyboard','post','sound','copy'}:
        raise ValueError('Attach audio to an existing directing/storyboard/sound/post request')
    tracks=chosen.get('tracks',[])
    if not 1<=len(tracks)<=4:raise ValueError('Select one to four useful excerpts, not a whole library')
    folder.mkdir(parents=True,exist_ok=True)
    for number,item in enumerate(tracks,1):
        source=(selection.parent/item['file']).resolve(strict=True)
        key=hashlib.sha256(json.dumps({'source':ref(source),'start':item.get('start',0),'end':item.get('end')},sort_keys=True).encode()).hexdigest()[:16]
        clip=audition(source,folder/('audition-'+key+'.mp4'),item.get('start',0),item.get('end'),label=item.get('label'))
        videos.append({k:clip[k] for k in ('file','source','source_interval','label')})
        receipt=source.with_suffix(source.suffix+'.asset.json')
        notes.append({'id':item.get('id','MUSIC-'+str(number)),'source':ref(source),'audition':clip,
                      'music_asset':read(receipt) if receipt.exists() else {'status':'existing user asset; source/use basis belongs to project'},
                      'cue_context':{k:item[k] for k in ('theme','variant','function','ending','tags','basis','review') if k in item},
                      'listened':False})
    note_file=folder/'music-candidates.json';save(note_file,{'intent':chosen.get('intent','Current target scene mood and natural transitions/ending'),'candidates':notes})
    data.setdefault('inputs',[]).append({'file':str(note_file),'kind':'actual-music-files-and-audition-clocks'})
    data.setdefault('videos',[]).extend(videos)
    identity=hashlib.sha256(json.dumps({'request':data,'selection':chosen},sort_keys=True).encode()).hexdigest()[:10]
    data['batch']=batch or data['batch'][:40]+'-music-'+identity
    data['task']+=' Actual supplied audio auditions contain real candidate sound; their neutral stills are not dramatic footage. Judge heard mood, density, musical phrase and tail with the scene/context. Proxy times map to the declared original music source intervals. For pre-production, use themes/variants and dramatic anchors to inform the existing design or detailed storyboard; for post, conform to the actual final edit clock. Cue notes are prior context, not fresh listening or a required positive verdict. Write the requested existing output, not a new music screenplay; file availability is not artistic acceptance.'
    output=folder/'writing-with-music.json';save(output,data)
    return {'request':str(output),'batch':data['batch'],'excerpts':len(videos),'paid_requests':0,'listened':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('extract');e.add_argument('media',type=Path);e.add_argument('--output',required=True,type=Path);e.add_argument('--start',type=float,default=0);e.add_argument('--end',type=float)
    a=sub.add_parser('acquire');a.add_argument('url');a.add_argument('--output',required=True,type=Path);a.add_argument('--page',required=True);a.add_argument('--title',required=True);a.add_argument('--kind',choices=['original_track','source_separation','replacement','sfx','ambience','voice'],default='replacement')
    r=sub.add_parser('recognize');r.add_argument('media',type=Path);r.add_argument('--output',required=True,type=Path)
    q=sub.add_parser('queries');q.add_argument('cue',type=Path);q.add_argument('--output',type=Path)
    s=sub.add_parser('separate');s.add_argument('media',type=Path);s.add_argument('--output',required=True,type=Path);s.add_argument('--model',required=True);s.add_argument('--executable')
    l=sub.add_parser('search');l.add_argument('query');l.add_argument('--providers',default='incompetech,scott_buckley');l.add_argument('--limit',type=int,default=6);l.add_argument('--cache');l.add_argument('--refresh',action='store_true');l.add_argument('--offline',action='store_true');l.add_argument('--output',required=True,type=Path)
    f=sub.add_parser('fetch');f.add_argument('selection',type=Path);f.add_argument('--id',required=True);f.add_argument('--output',required=True,type=Path)
    u=sub.add_parser('audition');u.add_argument('media',type=Path);u.add_argument('--output',required=True,type=Path);u.add_argument('--start',type=float,default=0);u.add_argument('--end',type=float)
    t=sub.add_parser('attach');t.add_argument('request',type=Path);t.add_argument('selection',type=Path);t.add_argument('--output',required=True,type=Path);t.add_argument('--batch')
    m=sub.add_parser('remember');m.add_argument('selection',type=Path);m.add_argument('--index',type=Path)
    c=sub.add_parser('recall');c.add_argument('query');c.add_argument('--index',type=Path);c.add_argument('--limit',type=int,default=4);c.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('beats');b.add_argument('media',type=Path);b.add_argument('--start',type=float,default=0);b.add_argument('--end',type=float);b.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='beats':
            from music_beats import analyze
            result=analyze(args.media,start=args.start,end=args.end);save(args.output,result)
        elif args.command=='extract':result=extract(args.media,args.output,args.start,args.end)
        elif args.command=='acquire':result=acquire(args.url,args.output,page=args.page,title=args.title,kind=args.kind)
        elif args.command=='recognize':result=recognize(args.media,args.output)
        elif args.command=='queries':
            result=search_queries(read(args.cue))
            if args.output:save(args.output,result)
        elif args.command=='separate':result=separate(args.media,args.output,args.model,args.executable)
        elif args.command=='search':
            from music_library import search
            result=search(args.query,providers=tuple(args.providers.split(',')),limit=args.limit,cache=args.cache,refresh=args.refresh,offline=args.offline)
            save(args.output,result)
            result={'record':str(args.output.resolve()),'providers':result['providers'],'candidates':[{k:r[k] for k in ('id','title','artist','moods','duration_hint')} for r in result['candidates']],'listened':False}
        elif args.command=='fetch':
            from music_library import fetch
            result=fetch(args.selection,args.id,args.output)
        elif args.command=='audition':result=audition(args.media,args.output,args.start,args.end)
        elif args.command=='remember':
            from music_cues import remember
            result=remember(args.selection,index=args.index)
        elif args.command=='recall':
            from music_cues import recall
            result=recall(args.query,index=args.index,limit=args.limit);save(args.output,result)
            result={'record':str(args.output.resolve()),'recalled':len(result['tracks']),'unavailable':result['unavailable'],'listened':False}
        else:result=attach_music(args.request,args.selection,args.output,batch=args.batch)
        if args.command=='recognize':
            track=result.get('track',{});result={'status':result['status'],'title':track.get('title'),'artist':track.get('subtitle'),
                                               'record':str(args.output.resolve()),'original_version_verified':False}
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,RuntimeError,subprocess.TimeoutExpired) as exc:print('MUSIC_ASSET_FAILED: '+str(exc));return 1
if __name__=='__main__':raise SystemExit(main())
