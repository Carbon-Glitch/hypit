"""Render declared drama edit decisions, layered sound, grades and graphic assets locally."""
from __future__ import annotations
import argparse,hashlib,json,math,shutil,subprocess,time,html
from pathlib import Path
from post_timeline import compile_plan,save,read,ref,number
from inspect_finishing import ffmpeg_path,metadata,sha
from retime_finish import speed_chain
from dialogue_guard import transcribe,compare_lines

_caption_helper=Path(__file__).resolve().with_name('caption_layout.py')
ENGINE=hashlib.sha256((''.join(sha(Path(__file__).with_name(name)) for name in
    ('finish_drama.py','post_timeline.py','music_envelope.py','retime_finish.py','dialogue_guard.py','inspect_finishing.py'))+
    (sha(_caption_helper) if _caption_helper.exists() else '')).encode()).hexdigest()[:16]

def signature(value):return hashlib.sha256(json.dumps({'engine':ENGINE,'value':value},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
def bounded(value,label,lo,hi):
    value=number(value,label,lo)
    if value>hi:raise ValueError(label+' exceeds supported range')
    return value
BASE_ENGINE=ENGINE
STAGES=[]
_FILTER_FILE_OPTION={}

def cached(path):
    receipt=path.with_suffix(path.suffix+'.cache.json')
    if not path.exists() or not receipt.exists():return False
    try:valid=read(receipt).get('sha256')==sha(path)
    except (OSError,ValueError):valid=False
    if valid:STAGES.append({'stage':path.stem,'cache_hit':True,'seconds':0})
    return valid

def cache_done(path):
    save(path.with_suffix(path.suffix+'.cache.json'),{'sha256':sha(path)})


def run(binary,args,root,log):
    if '-filter_complex_script' in args:
        if binary not in _FILTER_FILE_OPTION:
            help_text=subprocess.run([binary,'-h','full'],capture_output=True,text=True,errors='replace').stdout
            _FILTER_FILE_OPTION[binary]='-filter_complex_script' if '-filter_complex_script ' in help_text else '-/filter_complex'
        args=[_FILTER_FILE_OPTION[binary] if a=='-filter_complex_script' else a for a in args]
    started=time.perf_counter();logs=[]
    for attempt in range(2):
        result=subprocess.run([binary,'-hide_banner','-loglevel','error','-nostdin','-y',*map(str,args)],cwd=root,
                              capture_output=True,text=True,encoding='utf-8',errors='replace')
        logs.append(f'Attempt {attempt+1}\n'+result.stderr)
        Path(log).write_text('\n'.join(logs),encoding='utf-8')
        transient=any(term in result.stderr.lower() for term in ('resource temporarily unavailable','device or resource busy','being used by another process'))
        if result.returncode==0 or not transient or attempt:break
    STAGES.append({'stage':Path(log).stem,'cache_hit':False,'attempts':attempt+1,'seconds':round(time.perf_counter()-started,4)})
    if result.returncode:raise RuntimeError('FFmpeg failed; see '+str(log)+': '+result.stderr[-1200:])
def stage_asset(path,root):
    path=Path(path);name='asset-'+sha(path)[:16]+path.suffix.lower();target=root/name
    if not target.exists():shutil.copy2(path,target)
    return name
def checked_file(record):
    path=Path(record['file'])
    if not path.is_file() or sha(path)!=record['sha256']:raise ValueError('Actual edit input changed: '+str(path))
    return path


def grade_filters(grade,root,plan_root):
    allowed={'exposure','brightness','contrast','saturation','gamma','red','green','blue','lut'}
    if set(grade)-allowed:raise ValueError('Unknown grade parameter; do not silently ignore it')
    filters=[]
    if 'exposure' in grade:
        gain=2**bounded(grade['exposure'],'exposure',-3,3)
        filters.append(f'colorchannelmixer=rr={gain}:gg={gain}:bb={gain}')
    keys={'brightness':(-1,1,0),'contrast':(.1,3,1),'saturation':(0,3,1),'gamma':(.2,3,1)}
    values=[f'{key}={bounded(grade[key],key,lo,hi)}' for key,(lo,hi,default) in keys.items() if key in grade]
    if values:filters.append('eq='+':'.join(values))
    balance=[f'{key[0]}m={bounded(grade[key],key,-1,1)}' for key in ('red','green','blue') if key in grade]
    if balance:filters.append('colorbalance='+':'.join(balance))
    if grade.get('lut'):
        record=grade['lut'];file=checked_file(record) if isinstance(record,dict) else (plan_root/record).resolve(strict=True)
        filters.append("lut3d=file='"+stage_asset(file,root)+"'")
    return filters


def picture_effects(effects,duration,canvas):
    result=[];w,h,fps=canvas['width'],canvas['height'],canvas['fps']
    for effect in effects:
        kind=effect['type']
        if kind=='blur':result.append('gblur=sigma='+str(bounded(effect.get('sigma',1),'blur',.1,30)))
        elif kind=='vignette':result.append('vignette=angle='+str(bounded(effect.get('angle',.55),'vignette',.01,1.4)))
        elif kind=='zoom':
            amount=bounded(effect.get('amount',.05),'zoom',-.35,.5);cx=bounded(effect.get('x',.5),'zoom x',0,1);cy=bounded(effect.get('y',.5),'zoom y',0,1)
            result.append(f"zoompan=z='1+({amount})*on/{max(1,duration*fps)}':x='max(0,min(iw-iw/zoom,iw*{cx}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,ih*{cy}-ih/zoom/2))':d=1:s={w}x{h}:fps={fps}")
        elif kind=='shake':
            margin=bounded(effect.get('pixels',4),'shake pixels',1,min(w,h)*.05);frequency=bounded(effect.get('hz',8),'shake frequency',.1,30)
            result.append(f"crop=w=iw-{2*margin}:h=ih-{2*margin}:x='{margin}+{margin}*sin(n*{frequency}*2*PI/{fps})':y='{margin}+{margin}*cos(n*{frequency}*2*PI/{fps})',scale={w}:{h}")
        else:raise ValueError('Unsupported picture effect '+kind+'; render a real overlay asset for complex effects')
    return result


def volume_expression(points):
    if not points:return None
    ordered=sorted((number(p['time'],'envelope time'),bounded(p['db'],'envelope dB',-96,18)) for p in points)
    if len({p[0] for p in ordered})!=len(ordered):raise ValueError('Volume envelope times must be distinct')
    expr=str(ordered[-1][1])
    for (t0,v0),(t1,v1) in reversed(list(zip(ordered,ordered[1:]))):
        line=f'({v0}+({v1-v0})*(t-{t0})/{t1-t0})';expr=f'if(lt(t,{t1}),{line},{expr})'
    expr=f'if(lt(t,{ordered[0][0]}),{ordered[0][1]},{expr})'
    return 'pow(10,('+expr+')/20)'


def audio_effects(row,duration):
    result=[];gain=bounded(row.get('gain_db',0),'gain dB',-96,24)
    result.append(f'volume={gain}dB')
    expr=volume_expression(row.get('volume',[]))
    if expr:result.append("volume='"+expr+"':eval=frame")
    fade_in=bounded(row.get('fade_in',0),'fade in',0,duration);fade_out=bounded(row.get('fade_out',0),'fade out',0,duration)
    if fade_in:result.append(f'afade=t=in:st=0:d={fade_in}')
    if fade_out:result.append(f'afade=t=out:st={max(0,duration-fade_out)}:d={fade_out}')
    if 'pan' in row:
        pan=bounded(row['pan'],'pan',-1,1);result.append(f'pan=stereo|c0={min(1,1-pan)}*c0|c1={min(1,1+pan)}*c1')
    for effect in row.get('fx',[]):
        kind=effect['type']
        if kind=='highpass':result.append('highpass=f='+str(bounded(effect['hz'],'highpass',20,18000)))
        elif kind=='lowpass':result.append('lowpass=f='+str(bounded(effect['hz'],'lowpass',20,20000)))
        elif kind=='eq':result.append(f"equalizer=f={bounded(effect['hz'],'EQ frequency',20,18000)}:t=q:w={bounded(effect.get('q',1),'EQ Q',.1,10)}:g={bounded(effect['db'],'EQ gain',-24,24)}")
        elif kind=='denoise':result.append('afftdn=nf='+str(bounded(effect.get('noise_floor',-30),'noise floor',-80,-20)))
        elif kind=='compressor':result.append(f"acompressor=threshold={bounded(effect.get('threshold',.2),'compressor threshold',.001,1)}:ratio={bounded(effect.get('ratio',2),'compression ratio',1,20)}:attack={bounded(effect.get('attack_ms',15),'attack',.01,2000)}:release={bounded(effect.get('release_ms',150),'release',.01,9000)}")
        elif kind=='delay':result.append(f"aecho=0.8:0.8:{bounded(effect.get('ms',60),'delay ms',1,1000)}:{bounded(effect.get('decay',.15),'delay decay',.001,.9)}")
        else:raise ValueError('Unsupported audio effect '+kind)
    return result


def render_clip(clip,canvas,binary,root,plan_root):
    file=checked_file(clip['file'])
    recipe={k:clip[k] for k in ('file','native_audio','native_gain_db','grade','effects')}
    recipe['segments']=[{k:s[k] for k in ('start','end','speed')} for s in clip['segments']]
    recipe['muted_ranges']=[{k:d[k] for k in ('start','end')} for d in clip.get('discarded_speech',[])]
    key=signature({'clip':recipe,'canvas':canvas});out=root/('clip-'+key+'.mkv')
    if cached(out):return out
    w,h,fps=canvas['width'],canvas['height'],canvas['fps'];graph=[];parts=[];aparts=[]
    for index,part in enumerate(clip['segments']):
        start,end,speed=part['start'],part['end'],part['speed'];tag='v'+str(index)
        graph.append(f'[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/{speed},fps={fps},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[{tag}]');parts.append('['+tag+']')
        if clip['native_audio']:
            tag='a'+str(index)
            mute=','.join(f"volume=0:enable='between(t,{max(0,d['start']-start)},{min(end-start,d['end']-start)})'" for d in clip.get('discarded_speech',[]) if d['end']>start and d['start']<end)
            graph.append(f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,'+(mute+',' if mute else '')+f'{speed_chain(speed)},aresample=48000,aformat=channel_layouts=stereo[{tag}]');aparts.append('['+tag+']')
    filters=grade_filters(clip['grade'],root,plan_root)+picture_effects(clip['effects'],clip['duration'],canvas)
    graph.append(''.join(parts)+f'concat=n={len(parts)}:v=1:a=0'+(','+','.join(filters) if filters else '')+'[v]')
    if aparts:graph.append(''.join(aparts)+f'concat=n={len(aparts)}:v=0:a=1,volume={bounded(clip["native_gain_db"],"native gain",-96,24)}dB[a]')
    script=root/('clip-'+key+'.filters');script.write_text(';'.join(graph),encoding='utf-8')
    temporary=out.with_name(out.stem+'.pending.mkv')
    args=['-i',str(file),'-filter_complex_script',script.name,'-map','[v]']+(['-map','[a]'] if aparts else ['-an'])
    args+=['-c:v','libx264','-preset','fast','-crf','18','-c:a','pcm_s24le','-t',str(clip['duration']),str(temporary)]
    run(binary,args,root,root/('clip-'+key+'.log'));metadata(temporary,binary);checked_file(clip['file']);temporary.replace(out);cache_done(out);return out


def render_picture(edit,files,binary,root):
    if edit['overlays'] and not edit.get('_overlay_pass'):
        base=render_picture({**edit,'overlays':[]},files,binary,root)
        layer_edit={**edit,'_overlay_pass':True,'clips':[{'duration':edit['duration'],'at':0,
            'end_at':edit['duration'],'transition_in':{'type':'cut','duration':0}}]}
        return render_picture(layer_edit,[base],binary,root)
    key=signature({'files':[ref(p) for p in files], 'clips':[{k:c[k] for k in ('duration','at','end_at','transition_in')} for c in edit['clips']],
                   'overlays':edit['overlays'],'canvas':edit['canvas'],'duration':edit['duration']})
    out=root/('picture-'+key+'.mp4')
    if cached(out):return out
    w,h,fps=edit['canvas']['width'],edit['canvas']['height'],edit['canvas']['fps'];args=[];graph=[];stream=None;accum=0
    for index,(clip,file) in enumerate(zip(edit['clips'],files)):
        args+=['-i',str(file)];graph.append(f'[{index}:v]setpts=PTS-STARTPTS,fps={fps},settb=AVTB[v{index}]')
        if stream is None:stream=f'v{index}';accum=clip['duration'];continue
        tag=f'join{index}';tr=clip['transition_in']
        if tr['duration']:
            graph.append(f'[{stream}][v{index}]xfade=transition={tr["type"]}:duration={tr["duration"]}:offset={clip["at"]},fps={fps},settb=AVTB[{tag}]')
        else:graph.append(f'[{stream}][v{index}]concat=n=2:v=1:a=0,fps={fps},settb=AVTB[{tag}]')
        stream=tag;accum=clip['end_at']
    if edit['duration']>accum+.001:
        graph.append(f'[{stream}]tpad=stop_mode=clone:stop_duration={edit["duration"]-accum}[tail]');stream='tail'
    input_index=len(files)
    for index,row in enumerate(edit['overlays']):
        kind=row.get('type','image');tag='overlay'+str(index);at,duration=row['at'],row['duration'];opacity=bounded(row.get('opacity',1),'overlay opacity',0,1)
        if kind=='text':
            if not row.get('font_file') or not row.get('text'):raise ValueError('Designed text needs explicit font_file and exact text')
            font=stage_asset(row['font_file'],root);text=root/('text-'+signature(row)+'.txt');text.write_text(row['text'],encoding='utf-8')
            color=row.get('color','white')
            if not __import__('re').fullmatch(r'(?:[A-Za-z]+|#[0-9A-Fa-f]{6}|0x[0-9A-Fa-f]{6})',color):raise ValueError('Use a simple text color or RGB hex')
            x=number(row.get('x',w*.1),'text x');y=number(row.get('y',h*.1),'text y');size=bounded(row.get('size',h*.07),'font size',8,h)
            alpha=str(opacity);fi=row.get('fade_in',0);fo=row.get('fade_out',0)
            if fi:alpha+=f'*min(1,max(0,(t-{at})/{bounded(fi,"text fade in",.001,duration)}))'
            if fo:alpha+=f'*min(1,max(0,({row["until"]}-t)/{bounded(fo,"text fade out",.001,duration)}))'
            graph.append(f"[{stream}]drawtext=fontfile='{font}':textfile='{text.name}':expansion=none:fontsize={size}:fontcolor={color}:x={x}:y={y}:borderw={bounded(row.get('border',0),'text border',0,12)}:alpha='{alpha}':enable='between(t,{at},{row['until']})'[{tag}]")
        else:
            if kind=='color':
                color=row.get('color','white')
                if not __import__('re').fullmatch(r'(?:[A-Za-z]+|#[0-9A-Fa-f]{6}|0x[0-9A-Fa-f]{6})',color):raise ValueError('Invalid layer color')
                args+=['-f','lavfi','-i',f'color=c={color}:s={w}x{h}:r={fps}:d={duration}']
            elif kind in {'image','video'}:
                file=checked_file(row['file'])
                if kind=='image':args+=['-loop','1','-framerate',str(fps),'-i',str(file)]
                else:
                    details=metadata(file,binary)['details'];codec=next(d.get('codec_name') for d in details if d['codec_type']=='video')
                    if file.suffix.lower()=='.webm' and codec=='vp9':args+=['-c:v','libvpx-vp9']
                    args+=['-i',str(file)]
            else:raise ValueError('Unsupported overlay; render a concrete image/video layer first')
            ow=int(row.get('width',w));oh=int(row.get('height',h));x=number(row.get('x',0),'overlay x');y=number(row.get('y',0),'overlay y')
            filters=[f'trim=start={row.get("source_start",0)}:duration={duration}','setpts=PTS-STARTPTS',f'fps={fps}',f'scale={ow}:{oh}','format=rgba',f'colorchannelmixer=aa={opacity}']
            if row.get('fade_in'):filters.append(f'fade=t=in:st=0:d={bounded(row["fade_in"],"layer fade",.001,duration)}:alpha=1')
            if row.get('fade_out'):filters.append(f'fade=t=out:st={duration-row["fade_out"]}:d={bounded(row["fade_out"],"layer fade",.001,duration)}:alpha=1')
            if row.get('reveal')=='wipeleft':filters.append(f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(X/W,min(1,T/{bounded(row.get('reveal_duration',.6),'reveal',.001,duration)})),alpha(X,Y),0)'")
            graph.append(f'[{input_index}:v]'+','.join(filters)+f',setpts=PTS+{at}/TB[layer{index}]')
            graph.append(f"[{stream}][layer{index}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{at},{row['until']})'[{tag}]");input_index+=1
        stream=tag
    graph.append(f'[{stream}]fps={fps},format=yuv420p[vout]')
    script=root/('picture-'+key+'.filters');script.write_text(';'.join(graph),encoding='utf-8')
    temporary=out.with_name(out.stem+'.pending.mp4')
    run(binary,args+['-filter_complex_script',script.name,'-map','[vout]','-an','-c:v','libx264','-preset','fast','-crf','18','-t',str(edit['duration']),'-movflags','+faststart',str(temporary)],root,root/('picture-'+key+'.log'))
    metadata(temporary,binary);temporary.replace(out);cache_done(out);return out


def render_captions(edit,picture,binary,root):
    grain=edit['master'].get('grain',0)
    if not edit['captions'] and not grain:return picture
    key=signature({'picture':ref(picture),'captions':edit['captions'],'style':edit.get('caption_style',{}),'canvas':edit['canvas'],'grain':grain})
    out=root/('captioned-'+key+'.mp4')
    if cached(out):return out
    filters=[]
    if edit['captions']:
        ass=root/('captions-'+key+'.ass');ass.write_text(subtitle_ass(edit),encoding='utf-8-sig');filters.append(f"ass='{ass.name}'")
    if grain:filters.append(f"noise=alls={bounded(grain,'grain',0,20)}:allf=t+u")
    temporary=out.with_name(out.stem+'.pending.mp4')
    run(binary,['-i',str(picture),'-vf',','.join(filters),'-an','-c:v','libx264','-preset','fast','-crf','18',str(temporary)],root,root/('captioned-'+key+'.log'))
    metadata(temporary,binary);temporary.replace(out);cache_done(out);return out


def subtitle_ass(edit):
    if edit.get('caption_style'):
        # Use the packaged deterministic cue layout.
        import importlib.util
        helper=Path(__file__).resolve().with_name('caption_layout.py')
        if not helper.is_file():raise ValueError('Packaged caption_layout.py is missing')
        spec=importlib.util.spec_from_file_location('hypit_caption_layout',helper)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module.cue_ass(edit['captions'],edit['canvas']['width'],edit['canvas']['height'],edit['caption_style'])
    w,h=edit['canvas']['width'],edit['canvas']['height'];size=max(18,int(h*.045))
    header=f'[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,{size},&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,30,30,30,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    def clock(t):
        cs=round(t*100);return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'
    return header+'\n'.join(f'Dialogue: 0,{clock(r["start"])},{clock(r["end"])},Default,,0,0,0,,'+str(r['text']).replace('{','').replace('}','').replace('\n',r'\N') for r in edit['captions'])+'\n'


def audio_key(edit,files):
    rows=[{k:v for k,v in r.items() if k not in {'reason','speech_evidence','no_dialogue_basis'}} for r in edit['audio']]
    return signature({'files':[ref(p) for p in files], 'clips':[{k:c[k] for k in ('native_audio','at','end_at','duration','transition_in')} for c in edit['clips']],
                      'audio':rows,'master':{k:v for k,v in edit['master'].items() if k!='grain'},'duration':edit['duration']})


def render_audio(edit,files,binary,root):
    key=audio_key(edit,files);out=root/('mix-'+key+'.wav')
    stems=bool(edit['master'].get('export_stems',False))
    stem_files={bus:root/('stem-'+key+'-'+bus+'.wav') for bus in ('native','dialogue','music','ambience','sfx')} if stems else {}
    if cached(out) and all(cached(p) for p in stem_files.values()):return out
    args=[];graph=[];buses={k:[] for k in ('dialogue','native','music','ambience','sfx')};index=0;length=edit['duration']
    def place(filters,bus,at,tag):
        # trim/tempo/resample can retain a different time base. Build the final bus on
        # the actual48k sample clock; PTS-STARTPTS alone can trim away its leading delay.
        filters+=['asettb=1/48000','asetpts=N/SR/TB',f'adelay={round(at*48000)}S:all=1',
                  'asetpts=N/SR/TB',f'apad=whole_len={round(length*48000)}',f'atrim=end_sample={round(length*48000)}']
        graph.append(f'[{index}:a]'+','.join(filters)+'['+tag+']');buses[bus].append('['+tag+']')
    for clip,file in zip(edit['clips'],files):
        if not clip['native_audio']:continue
        args+=['-i',str(file)];filters=['aresample=48000','aformat=channel_layouts=stereo']
        # Crossfade native handles where the picture intentionally overlaps.
        if clip['transition_in']['duration']:filters.append(f'afade=t=in:st=0:d={clip["transition_in"]["duration"]}')
        following=next((c for c in edit['clips'] if abs(c['at']-(clip['end_at']-c['transition_in']['duration']))<.001 and c['id']!=clip['id']),None)
        if following and following['transition_in']['duration']:filters.append(f'afade=t=out:st={clip["duration"]-following["transition_in"]["duration"]}:d={following["transition_in"]["duration"]}')
        place(filters,'native',clip['at'],'sound'+str(index));index+=1
    for row in edit['audio']:
        file=checked_file(row['file']);args+=['-i',str(file)]
        filters=[f'atrim=start={row["start"]}:end={row["end"]}','asetpts=PTS-STARTPTS']
        filters += [f"volume=0:enable='between(t,{max(0,d['start']-row['start'])},{min(row['end']-row['start'],d['end']-row['start'])})'" for d in row.get('discarded_speech',[]) if d['end']>row['start'] and d['start']<row['end']]
        filters += [speed_chain(row['speed']),'aresample=48000','aformat=channel_layouts=stereo']
        if row['loop']:filters.append('aloop=loop=-1:size='+str(round((row['end']-row['start'])/row['speed']*48000)))
        filters.append('atrim=duration='+str(row['duration']));filters+=audio_effects(row,row['duration'])
        place(filters,row['bus'],row['at'],'sound'+str(index));index+=1
    for bus,tags in buses.items():
        if tags:graph.append(''.join(tags)+f'amix=inputs={len(tags)}:duration=longest:normalize=0[{bus}]')
        else:graph.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={length}[{bus}]')
        if stems:graph.append(f'[{bus}]asplit=2[{bus}live][{bus}stem]')
    suffix='live' if stems else ''
    graph.append(f'[native{suffix}][dialogue{suffix}]amix=inputs=2:normalize=0[foreground]')
    duck=edit['master'].get('duck_music',False)
    if isinstance(duck,dict) and duck.get('mode')=='envelope':
        expression=volume_expression(edit['master'].get('music_envelope',[])) or '1'
        graph.append(f"[music{suffix}]volume='{expression}':eval=frame[score]")
        foreground,score='foreground','score'
    elif duck:
        # A mixed H3 foreground is not falsely advertised as a separated vocal stem.
        ratio=bounded(duck.get('ratio',4) if isinstance(duck,dict) else 4,'duck ratio',1,20)
        threshold=bounded(duck.get('threshold',.035) if isinstance(duck,dict) else .035,'duck threshold',.001,1)
        graph.append('[foreground]asplit=2[frontmix][sidechain]')
        graph.append(f'[music{suffix}][sidechain]sidechaincompress=threshold={threshold}:ratio={ratio}:attack=15:release=220[score]')
        foreground,score='frontmix','score'
    else:foreground,score='foreground','music'+suffix
    graph.append(f'[{foreground}][{score}][ambience{suffix}][sfx{suffix}]amix=inputs=4:duration=longest:normalize=0[premaster]')
    gain=bounded(edit['master'].get('gain_db',0),'master gain',-36,18)
    graph.append(f'[premaster]volume={gain}dB,alimiter=limit={bounded(edit["master"].get("peak_limit",.97),"peak limit",.1,1)}:level=false:latency=true,atrim=duration={length}[mix]')
    script=root/('mix-'+key+'.filters');script.write_text(';'.join(graph),encoding='utf-8')
    temporary=out.with_name(out.stem+'.pending.wav')
    command=args+['-filter_complex_script',script.name,'-map','[mix]','-c:a','pcm_s24le',str(temporary)]
    for bus,file in stem_files.items():command+=['-map','['+bus+'stem]','-c:a','pcm_s24le',str(file)]
    run(binary,command,root,root/('mix-'+key+'.log'));metadata(temporary,binary)
    if 'lufs' in edit['master']:
        target=bounded(edit['master']['lufs'],'target LUFS',-36,-9);peak=bounded(edit['master'].get('true_peak_db',-1.5),'true peak',-9,0)
        measurement=subprocess.run([binary,'-hide_banner','-nostdin','-i',str(temporary),'-af',f'loudnorm=I={target}:TP={peak}:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if measurement.returncode:raise RuntimeError('Cannot measure actual premaster loudness')
        raw=measurement.stderr;stats=json.loads(raw[raw.rfind('{'):raw.rfind('}')+1]);save(root/('loudness-'+key+'.json'),stats)
        if not all(math.isfinite(float(stats[k])) for k in ('input_i','input_tp','input_lra','input_thresh','target_offset')):raise ValueError('A silent/invalid mix cannot be normalized to a meaningful LUFS target')
        effect=f'loudnorm=I={target}:TP={peak}:LRA=11:measured_I={stats["input_i"]}:measured_TP={stats["input_tp"]}:measured_LRA={stats["input_lra"]}:measured_thresh={stats["input_thresh"]}:offset={stats["target_offset"]}:linear=true'
        run(binary,['-i',str(temporary),'-af',effect,'-ar','48000','-c:a','pcm_s24le',str(out)],root,root/('normalize-'+key+'.log'))
    else:temporary.replace(out)
    for row in edit['audio']:checked_file(row['file'])
    cache_done(out)
    for stem in stem_files.values():cache_done(stem)
    return out


def preview_report(report,output):
    page=output.with_suffix('.preview.html')
    rows=[]
    for clip in report['compiled']['clips']:
        rows.append(f'<tr><td><button data-at="{clip["at"]}">{html.escape(clip["id"])}</button></td><td>{clip["at"]:.3f}–{clip["end_at"]:.3f}s</td><td>{html.escape(clip.get("reason",""))}</td></tr>')
    page.write_text('<!doctype html><meta charset="utf-8"><title>剪辑预览</title><style>body{font:16px system-ui;background:#15181c;color:#eee;max-width:1000px;margin:30px auto}video{max-width:100%;max-height:70vh}td{padding:10px}</style><h1>剪辑预览</h1><video id="film" controls src="'+html.escape(output.name,quote=True)+'"></video><table>'+''.join(rows)+'</table><pre>'+html.escape(json.dumps(report['issues'],ensure_ascii=False,indent=2))+'</pre><script>document.querySelectorAll("button[data-at]").forEach(b=>b.onclick=()=>{film.currentTime=Number(b.dataset.at);film.play()});</script>',encoding='utf-8')
    return str(page)


def render(plan,output,*,ffmpeg=None,ffprobe=None,preview=False):
    global ENGINE
    STAGES.clear()
    plan,output=Path(plan).resolve(),Path(output).resolve();binary=ffmpeg_path(ffmpeg)
    build=subprocess.run([binary,'-version'],capture_output=True,check=True).stdout
    ENGINE=hashlib.sha256(BASE_ENGINE.encode()+build).hexdigest()[:16]
    if output==plan:raise ValueError('Preserve source plan')
    edit=compile_plan(plan,ffmpeg=binary,ffprobe=ffprobe);root=output.parent/'.hypit-post';root.mkdir(parents=True,exist_ok=True)
    if preview:
        canvas=edit['canvas'];scale=min(1,540/canvas['width'])
        canvas['width']=max(16,round(canvas['width']*scale/2)*2)
        canvas['height']=max(16,round(canvas['height']*scale/2)*2)
        edit['preview']=True
    receipt=output.with_suffix(output.suffix+'.post.json')
    if output.exists():
        previous=read(receipt) if receipt.exists() else {}
        if previous.get('plan')==ref(plan) and previous.get('output')==ref(output) and previous.get('compiled_sha256')==signature(edit):return previous
        raise ValueError('Output already belongs to another edit; use a versioned path')
    save(root/('compiled-'+signature(edit)+'.json'),edit)
    files=[render_clip(c,edit['canvas'],binary,root,plan.parent) for c in edit['clips']]
    picture=render_picture(edit,files,binary,root);mix=render_audio(edit,files,binary,root)
    base_picture=picture;picture=render_captions(edit,picture,binary,root)
    for record in edit['inputs']:checked_file(record)
    output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_name(output.stem+'.pending.mp4')
    run(binary,['-i',str(picture),'-i',str(mix),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t',str(edit['duration']),'-movflags','+faststart',str(temporary)],root,root/('export-'+signature(edit)+'.log'))
    actual=metadata(temporary,binary,ffprobe)
    if abs(actual['duration']-edit['duration'])>max(.15,2/edit['canvas']['fps']):raise ValueError('Actual final duration disagrees with compiled edit')
    temporary.replace(output)
    report={'version':1,'status':'rendered_with_findings' if edit['issues'] else 'rendered','plan':ref(plan),'compiled_sha256':signature(edit),
            'compiled':edit,'output':ref(output),'picture':ref(picture),'base_picture':ref(base_picture),'mix':ref(mix),'actual':actual,'issues':list(edit['issues']),'render_stages':list(STAGES),
            'artistic_accepted':False,'next':'Review actual final audiovisual output and repair localized findings; technical render is not artistic acceptance'}
    mix_key=audio_key(edit,files)
    report['stems']=[ref(p) for p in root.glob('stem-'+mix_key+'-*.wav')]
    report['stem_note']='native is the retained H3 mix, not a claimed clean dialogue stem; absent buses may be silent'
    if (root/('loudness-'+mix_key+'.json')).exists():report['loudness_measurement']=read(root/('loudness-'+mix_key+'.json'))
    if edit['expected_lines']:
        evidence=transcribe(output,language=read(plan).get('language'));report['dialogue_comparison']=compare_lines(edit['expected_lines'],evidence)
        if evidence.get('status')!='ok':report['status']='rendered_with_findings'
        elif report['dialogue_comparison']['status']!='matched':report['status']='needs_dialogue_review'
    report['preview_page']=preview_report(report,output)
    save(receipt,report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);p.add_argument('output',type=Path);p.add_argument('--ffmpeg');p.add_argument('--ffprobe');p.add_argument('--preview',action='store_true',help='Same edit clock, at most 540px wide');a=p.parse_args()
    try:
        result=render(a.plan,a.output,ffmpeg=a.ffmpeg,ffprobe=a.ffprobe,preview=a.preview)
        print(json.dumps({'status':result['status'],'output':result['output'],'duration':result['actual']['duration'],'issues':result['issues'],'artistic_accepted':False},ensure_ascii=False));return 0 if result['status'] in {'rendered','rendered_with_findings'} else 2
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:print('DRAMA_FINISH_FAILED: '+str(exc));return 1
if __name__=='__main__':raise SystemExit(main())
