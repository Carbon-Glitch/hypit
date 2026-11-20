"""Read-only source-shot review: paired sheets, native frames and motion review candidates.

Reads the canonical SOURCE_SHOTS/context. Never renumbers, writes creative facts or grants a pass.
Uses the installed PyAV/Pillow runtime; no model requests or video re-encoding.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,statistics,time
from pathlib import Path
from source_shots import load_table,clock
from post_timeline import read,save,ref

METHOD='native-pairs-gray-difference-v1'


def key(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()[:24]


def valid_asset(value):
    try:return ref(value['file'])==value
    except (OSError,KeyError,TypeError):return False


def movement_claim(text):
    """A conservative keyword cue, never a semantic camera-motion classifier."""
    if text.lstrip().startswith(('UNKNOWN:','N/A:')):return False
    pattern=r'推近|推入|前推|缓推|推镜|拉远|后拉|平移|摇镜|跟拍|环绕|升降|甩镜|航拍移动|\b(?:push|pull|zoom|pan|tracking|dolly|orbit|truck)\b'
    for match in re.finditer(pattern,text,re.I):
        prefix=text[max(0,match.start()-16):match.start()]
        if not re.search(r'(?:不|无|未|没有|避免|禁止|无需)\s*$|\b(?:no|not|without)\s*$',prefix,re.I):return True
    return False


def motion_summary(samples,start,end,claim,threshold):
    edge=min(.4,max(.1,(end-start)*.15))
    values=[v for left,right,v in samples if left>=start+edge-1e-7 and right<end-edge+1e-7]
    value=statistics.median(values) if len(values)>=2 else None
    candidate=bool(end-start>=1 and value is not None and value<threshold and movement_claim(claim))
    return {'value':value,'samples':len(values),'low_motion_threshold':threshold,'review_candidate':candidate,
            'reason':('文字含明显运镜词，但内部采样变化较低；回看实际运动。低纹理、缓动、主体运动和曝光变化都可能影响指标。' if candidate else ''),
            'basis':'Sampled grayscale pixel difference; not optical flow, movement direction or artistic acceptance.'}


def frame_image(frame):
    image=frame.to_image()
    rotation=getattr(frame,'rotation',0)
    if rotation:image=image.rotate(rotation,expand=True)
    return image


def decode(media,targets,*,measure,hz,width):
    """One native decode for all missing frames and, when needed, the motion curve."""
    import av
    from PIL import Image
    pending=sorted(targets,key=lambda t:t['requested']);found={};samples=[]
    prev_frame=None;prev_time=None;last_gray=None;last_sample=None;next_sample=0.;position=0
    limit=max(t['end'] for t in targets) if targets else math.inf
    with av.open(str(media)) as container:
        if not container.streams.video:raise ValueError('Source review needs an actual video stream')
        stream=container.streams.video[0]
        origin=float(stream.start_time*stream.time_base) if stream.start_time is not None else None
        for frame in container.decode(video=0):
            if frame.pts is None:continue
            absolute=float(frame.pts*frame.time_base)
            if origin is None:origin=absolute
            stamp=absolute-origin
            if stamp<0:continue
            if measure and stamp>=next_sample-1e-7:
                gray=bytes(frame_image(frame).convert('L').resize((64,36),Image.Resampling.BILINEAR).tobytes())
                if last_gray is not None:samples.append([last_sample,stamp,sum(abs(a-b) for a,b in zip(gray,last_gray))/len(gray)])
                last_gray,last_sample=gray,stamp
                next_sample=(math.floor((stamp+1e-7)*hz)+1)/hz
            while position<len(pending) and pending[position]['requested']<=stamp+1e-7:
                target=pending[position]
                options=[(t,f) for t,f in ((prev_time,prev_frame),(stamp,frame))
                         if t is not None and target['start']-1e-7<=t<target['end']-1e-7]
                if options:
                    actual,chosen=min(options,key=lambda p:abs(p[0]-target['requested']))
                    image=frame_image(chosen);image.thumbnail((width,10000),Image.Resampling.LANCZOS)
                    path=Path(target['file']);path.parent.mkdir(parents=True,exist_ok=True);image.save(path,quality=88)
                    found[target['key']]={'requested':target['requested'],'actual':actual,'image':ref(path)}
                position+=1
            prev_frame,prev_time=frame,stamp
            if not measure and position>=len(pending) and stamp>=limit:break
        # A requested late point can be after the last native frame but still inside the source span.
        for target in pending[position:]:
            if prev_time is not None and target['start']-1e-7<=prev_time<target['end']-1e-7:
                image=frame_image(prev_frame);image.thumbnail((width,10000),Image.Resampling.LANCZOS)
                path=Path(target['file']);path.parent.mkdir(parents=True,exist_ok=True);image.save(path,quality=88)
                found[target['key']]={'requested':target['requested'],'actual':prev_time,'image':ref(path)}
    return found,samples


def contact_sheets(shots,output):
    from PIL import Image,ImageOps,ImageDraw,ImageFont
    sheets=[]
    try:font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    except OSError:font=ImageFont.load_default()
    for start in range(0,len(shots),16):
        group=shots[start:start+16]
        for phase in ('a','b'):
            identity=[(s['id'],s['start'],s['end'],s['frames'].get(phase)) for s in group]
            target=output/'sheets'/('sheet-'+key(['paired-sheet-layout-v2',identity])+'-'+phase+'.jpg')
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                sheet=Image.new('RGB',(4*320,math.ceil(len(group)/4)*240),'#151c29');draw=ImageDraw.Draw(sheet)
                for index,shot in enumerate(group):
                    x=(index%4)*320;y=(index//4)*240;info=shot['frames'].get(phase)
                    if info:
                        with Image.open(info['image']['file']) as image:
                            image=ImageOps.contain(image.convert('RGB'),(312,194))
                            sheet.paste(image,(x+(320-image.width)//2,y+(194-image.height)//2))
                    draw.text((x+8,y+196),shot['id'],font=font,fill='white')
                    draw.text((x+8,y+214),f"{shot['start']:.3f}–{shot['end']:.3f}s  {phase}",font=font,fill='#b4c5da')
                sheet.save(target,quality=88)
            sheets.append({'phase':phase,'page':start//16+1,'shot_ids':[s['id'] for s in group],'image':ref(target)})
    return sheets


def build(table,output,*,context=None,media=None,motion=True,hz=5,width=640,threshold=1.5):
    import av
    table=Path(table).resolve(strict=True);output=Path(output).resolve()
    if not 1<=hz<=30 or not 160<=width<=1920 or not math.isfinite(threshold) or threshold<0:
        raise ValueError('Use motion Hz1..30, frame width160..1920 and a finite nonnegative threshold')
    rows,columns=load_table(table)
    context=Path(context).resolve(strict=True) if context else table.with_name('SOURCE_CONTEXT.json')
    meta=read(context) if context.exists() else {};reference=meta.get('media',{})
    if not media and not reference.get('file'):raise ValueError('Supply --media or a canonical context.media file')
    media=Path(media).resolve(strict=True) if media else (context.parent/reference['file']).resolve(strict=True)
    source=ref(media)
    if reference.get('sha256') and source['sha256']!=reference['sha256']:raise ValueError('Source media differs from canonical context')
    with av.open(str(media)) as container:
        if not container.streams.video:raise ValueError('Source review needs an actual video stream')
        media_duration=float(container.duration/av.time_base) if container.duration is not None else None
    bindings={'table':ref(table),'context':ref(context) if context.exists() else None,'media':source}
    output.mkdir(parents=True,exist_ok=True)
    if table.is_relative_to(output) or (context.exists() and context.is_relative_to(output)) or media.is_relative_to(output):
        raise ValueError('Keep the derived report folder separate from canonical input files')
    runtime={'method':METHOD,'decoder':av.__version__}
    frames_file=output/'.cache/frames.json';old=read(frames_file) if frames_file.exists() else {};cached=old.get('frames',{})
    track_file=output/'.cache'/('motion-'+key([source,runtime,hz])+'.json')
    track=read(track_file) if motion and track_file.exists() else None
    targets=[];shots=[];reused=0;generated=0
    for row in rows:
        sid=row['镜头ID'];start,end=clock(row['入点']),clock(row['出点'])
        shot={'id':sid,'start':start,'end':end,'frames':{},'row':row};shots.append(shot)
        for phase,fraction in (('a',.15),('b',.85)):
            cache_key=key([source['sha256'],runtime,start,end,fraction,width])
            if cache_key in cached and Path(cached[cache_key]['image']['file']).is_relative_to(output) and valid_asset(cached[cache_key]['image']):
                shot['frames'][phase]=cached[cache_key];reused+=1
            else:targets.append({'key':cache_key,'id':sid,'phase':phase,'start':start,'end':end,
                                 'requested':start+(end-start)*fraction,'file':str(output/'frames'/(cache_key+'.jpg'))})
    if targets or (motion and track is None):
        found,samples=decode(media,targets,measure=motion and track is None,hz=hz,width=width)
        generated=len(found)
        cached.update(found)
        save(frames_file,{'method':METHOD,'frames':cached})
        if motion and track is None:
            track={'media':source,'hz':hz,'runtime':runtime,'samples':samples,'basis':'Native video frames sampled at up to requested Hz; grayscale64x36 mean absolute differences.'}
            save(track_file,track)
    for shot in shots:
        for phase,fraction in (('a',.15),('b',.85)):
            cache_key=key([source['sha256'],runtime,shot['start'],shot['end'],fraction,width])
            if cache_key in cached and Path(cached[cache_key]['image']['file']).is_relative_to(output) and valid_asset(cached[cache_key]['image']):shot['frames'][phase]=cached[cache_key]
        shot['motion']=(motion_summary(track['samples'],shot['start'],shot['end'],shot['row'].get('运镜与注意路径',shot['row'].get('摄影机运动过程','')),threshold)
                        if track else {'value':None,'samples':0,'review_candidate':False,'basis':'Motion measurement skipped'})
    sheets=contact_sheets(shots,output)
    notes=[]
    for shot in shots:
        if len(shot['frames'])<2:notes.append({'shot_id':shot['id'],'kind':'missing_native_pair','detail':'No in-range native frame found; inspect source boundary, do not invent a frame.'})
        if shot['motion']['review_candidate']:notes.append({'shot_id':shot['id'],'kind':'claimed_motion_low_pixel_change','detail':shot['motion']['reason']})
    for previous,current in zip(shots,shots[1:]):
        if abs(current['start']-previous['end'])>.002:notes.append({'shot_id':current['id'],'kind':'source_boundary_review','detail':'Canonical rows have a gap/overlap; derived view leaves their IDs and boundaries unchanged.'})
    manifest={'version':1,'method':METHOD,'inputs':bindings,'runtime':runtime,'shots':[{
        k:v for k,v in shot.items() if k!='row'} for shot in shots],'sheets':sheets,'motion_track':ref(track_file) if track else None,
        'review_candidates':notes,'frames_reused':reused,'frames_generated':generated,
        'artistic_accepted':False,'note':'Read-only derived view. Candidates are not failures; no model calls, cut changes or source renumbering.'}
    for name,path in (('table',table),('media',media)):
        if ref(path)!=bindings[name]:raise ValueError('Canonical input changed during view generation')
    if bindings['context'] and ref(context)!=bindings['context']:raise ValueError('Canonical context changed during view generation')
    payload={'title':media.stem,'inputs':bindings,'media_url':media.as_uri(),'media_duration':media_duration,'records':meta.get('records',{}),
             'columns':columns,'shots':shots,'sheets':sheets,'notes':notes,'generated':time.strftime('%Y-%m-%d %H:%M:%S')}
    for shot in payload['shots']:
        for frame in shot['frames'].values():frame['href']=Path(frame['image']['file']).relative_to(output).as_posix()
    for sheet in sheets:sheet['href']=Path(sheet['image']['file']).relative_to(output).as_posix()
    assets=Path(__file__).resolve().parent.parent/'assets'
    data=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    page=(assets/'source-review.html').read_text(encoding='utf-8').replace('/*SOURCE_REVIEW_CSS*/',(assets/'source-review.css').read_text(encoding='utf-8'))
    page=page.replace('/*SOURCE_REVIEW_JS*/',(assets/'source-review.js').read_text(encoding='utf-8')).replace('SOURCE_REVIEW_DATA',data)
    target=output/'index.html';target.write_text(page,encoding='utf-8');save(output/'source-review.json',manifest)
    return {'report':str(target),'manifest':str(output/'source-review.json'),'shots':len(shots),'frames_reused':reused,
            'frames_generated':generated,'review_candidates':len(notes),'paid_requests':0,'artistic_accepted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('table',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--context',type=Path);p.add_argument('--media',type=Path);p.add_argument('--no-motion',action='store_true')
    p.add_argument('--motion-hz',type=float,default=5);p.add_argument('--frame-width',type=int,default=640);p.add_argument('--low-motion',type=float,default=1.5)
    args=p.parse_args()
    try:
        print(json.dumps(build(args.table,args.output,context=args.context,media=args.media,motion=not args.no_motion,
                               hz=args.motion_hz,width=args.frame_width,threshold=args.low_motion),ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,ImportError) as exc:
        print('SOURCE_REVIEW_FAILED: '+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
