"""Compile an existing edit configuration into actual picture/audio/event clocks.

This module executes declared decisions; it never chooses an aesthetic or grants acceptance.
"""
from __future__ import annotations
import argparse,copy,json,math
from fractions import Fraction
from pathlib import Path
from inspect_finishing import ffmpeg_path,metadata,sha
from dialogue_guard import transcribe,protect_segments,missing_intervals,apply_speech_discards,align_caption_lines
from retime_finish import validate_plan,timeline_map
from scene_continuity import protect_events


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def ref(path):return {'file':str(Path(path).resolve()),'sha256':sha(path)}
def number(value,label,minimum=0):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum:raise ValueError(label+' must be finite and >= '+str(minimum))
    return float(value)
def asset(value,root):
    if isinstance(value,dict):
        path=(root/value['file']).resolve(strict=True)
        if value.get('sha256') and sha(path)!=value['sha256']:raise ValueError('Asset changed: '+str(path))
        return path
    return (root/value).resolve(strict=True)
def media_file(row,root):
    if row.get('file'):return asset(row['file'],root)
    if row.get('source_job') or row.get('job'):return (root/row.get('source_job',row.get('job'))/'output-0.mp4').resolve(strict=True)
    raise ValueError('An actual file or H3 job is required')


def editorial_metrics(clips,audio,duration,source_duration=None):
    """Cheap measured clocks for the existing edit/review, never aesthetic gates.

    Source seconds refer to selected current input windows, not untracked earlier retimes.
    Music coverage describes independent events, never absence of music in native mixes.
    """
    selected=sum(s['end']-s['start'] for c in clips for s in c['segments'])
    conformed=sum(c['duration'] for c in clips)
    accelerated=[s for c in clips for s in c['segments'] if s.get('requested_speed',s['speed'])>1.001]
    spans=[]
    for row in sorted((a for a in audio if a['bus']=='music'),key=lambda a:a['at']):
        left=max(0.,min(duration,row['at']));right=max(0.,min(duration,row['until']))
        if right<=left:continue
        if spans and left<=spans[-1][1]+1e-6:spans[-1][1]=max(spans[-1][1],right)
        else:spans.append([left,right])
    gaps=[];cursor=0.
    for left,right in spans+[[duration,duration]]:
        if left>cursor+1e-6:
            gaps.append({'start':cursor,'end':left,'clip_ids':[c['id'] for c in clips if c['at']<left and c['end_at']>cursor]})
        cursor=max(cursor,right)
    covered=sum(right-left for left,right in spans)
    metrics={'clock':'Compiled final picture frames; current selected-input windows only',
             'final_seconds':duration,'selected_source_seconds':selected,'conformed_clip_seconds':conformed,
             'retime_saved_seconds':selected-conformed,'effective_selected_speed':selected/conformed if conformed else None,
             'accelerated_segments':len(accelerated),'accelerated_selected_seconds':sum(s['end']-s['start'] for s in accelerated),
             'independent_music':{'covered_seconds':covered,'coverage_ratio':covered/duration if duration else 0,
                                  'intervals':spans,'uncovered':gaps,
                                  'basis':'Scheduled independent music events before gain/ducking; native mix may contain music. No loudness, emotion or silence verdict.'}}
    if source_duration is not None:
        source_duration=number(source_duration,'pacing source_duration',.001)
        metrics.update(reference_seconds=source_duration,reference_delta_seconds=duration-source_duration,
                       reference_duration_ratio=duration/source_duration)
    return metrics


def point(value,clips):
    if isinstance(value,(int,float)):return number(value,'timeline point')
    if not isinstance(value,dict) or value.get('clip') not in clips:raise ValueError('Event needs seconds or {clip, source_time/edge}')
    clip=clips[value['clip']]
    offset=number(abs(value.get('offset',0)),'offset')*(1 if value.get('offset',0)>=0 else -1)
    if value.get('edge') in {'start','end'}:return clip['at' if value['edge']=='start' else 'end_at']+offset
    source_time=number(value.get('source_time'),'event source time')
    for part in clip['mapping']:
        if part['source_start']-1e-6<=source_time<=part['source_end']+1e-6:
            return clip['at']+part['target_start']+(source_time-part['source_start'])/part['speed']+offset
    raise ValueError('Event source point was trimmed away: '+value['clip'])


def compile_plan(path,*,ffmpeg=None,ffprobe=None):
    path=Path(path).resolve();root=path.parent;plan=read(path)
    if plan.get('version')!=1 or not plan.get('clips'):raise ValueError('Edit requires version=1 and nonempty clips')
    if 'audio_segments' in plan or any('audio_segments' in c for c in plan['clips']):
        raise ValueError('Legacy audio_segments is not rendered here; migrate its actual source windows and timeline positions to audio[], and explicitly set native_audio before finishing')
    binary=ffmpeg_path(ffmpeg);inputs={};info_cache={};clips=[];lookup={};issues=[]
    def info(file):
        key=str(file)
        if key not in info_cache:info_cache[key]=metadata(file,binary,ffprobe);inputs[key]=ref(file)
        return info_cache[key]
    def speech(file,row):
        original=transcribe(file,language=row.get('language',plan.get('language')))
        selected=apply_speech_discards(original,row.get('discarded_speech',[]),root)
        return original,selected
    first=info(media_file(plan['clips'][0],root))
    first_video=next((d for d in first['details'] if d['codec_type']=='video'),{})
    try:native_fps=float(Fraction(first_video.get('r_frame_rate','24/1')))
    except (ValueError,ZeroDivisionError):native_fps=24
    fps=number(plan.get('canvas',{}).get('fps',native_fps or 24),'fps',1)
    cursor=0.
    for raw in plan['clips']:
        row=copy.deepcopy(raw);identifier=str(row.get('id','')).strip()
        if not identifier or identifier in lookup:raise ValueError('Use distinct editing clip IDs')
        file=media_file(row,root);data=info(file)
        if not data['streams']['video']:raise ValueError('Picture clip has no video')
        supplied=row.get('segments',row.get('picture_segments',[{'start':row.get('start',0),'end':row.get('end',data['duration']),'speed':row.get('speed',1),'reason':row.get('reason','')}]))
        if any(s.get('source_job') or s.get('file') for s in supplied):raise ValueError('Split different picture sources into editing clips, each with its actual file')
        segments=validate_plan({'version':1,'segments':supplied},data['duration'])
        native=row.get('native_audio',True) and data['streams']['audio']
        protection={'status':'not_applicable'};evidence=None;effective=None
        if native:
            expected=row.get('dialogue_expected',True)
            if expected or row.get('discarded_speech'):
                evidence,effective=speech(file,row)
                if expected:segments,protection=protect_segments(segments,effective,data['duration'])
            elif not row.get('no_dialogue_basis'):raise ValueError('A no-dialogue decision needs an actual observation basis')
        segments,restored=protect_events(segments,row.get('anchors',[]))
        if any(s['end']>data['duration']+.001 for s in segments):raise ValueError('Protected event exceeds source media')
        for segment in segments:
            frames=max(1,round((segment['end']-segment['start'])/segment['speed']*fps))
            segment['requested_speed']=segment['speed']
            segment['speed']=(segment['end']-segment['start'])/(frames/fps)
        mapping=timeline_map(segments);duration=mapping[-1]['target_end']
        transition=row.get('transition_in',{'type':'cut','duration':0})
        kind=transition.get('type','cut');overlap=round(number(transition.get('duration',0),'transition duration')*fps)/fps
        if kind=='cut':overlap=0
        elif kind not in {'fade','fadeblack','fadewhite','wipeleft','wiperight','slideleft','slideright','dissolve','smoothleft','smoothright'}:raise ValueError('Unsupported transition')
        if overlap and (not clips or overlap>=min(duration,clips[-1]['duration'])):raise ValueError('Transition needs usable handles in both clips')
        at=cursor-overlap;cursor=at+duration
        grade=copy.deepcopy(row.get('grade',{}))
        if grade.get('lut'):
            lut=asset(grade['lut'],root);grade['lut']=ref(lut);inputs[str(lut)]=ref(lut)
        clip={'id':identifier,'file':inputs[str(file)],'segments':segments,'mapping':mapping,'at':at,'end_at':cursor,'duration':duration,
              'native_audio':bool(native),'native_music':row.get('native_music','unknown'),'native_gain_db':row.get('native_gain_db',0),'grade':grade,'effects':row.get('effects',[]),
              'transition_in':{'type':kind,'duration':overlap},'speech_protection':protection,'restored_action_intervals':restored,
              'reason':row.get('reason',''),'anchors':row.get('anchors',[])}
        if evidence:
            clip['speech_evidence']=effective;clip['discarded_speech']=row.get('discarded_speech',[])
            for discard in row.get('discarded_speech',[]):
                review=asset(discard['review'],root);inputs[str(review)]=ref(review)
        clips.append(clip);lookup[identifier]=clip
        if protection.get('status') in {'unknown_full_coverage','unverified_boundaries'}:issues.append({'kind':'speech_unknown','clip':identifier,'detail':'Selected windows retained; use current-Agent observations/waveform data. Word boundaries are not verified.'})
    duration=round(number(plan.get('duration',cursor),'edit duration',.001)*fps)/fps
    if duration<cursor-.001:raise ValueError('Final duration cannot silently truncate retained picture')
    video=next(d for d in info_cache[str(media_file(plan['clips'][0],root))]['details'] if d['codec_type']=='video')
    canvas=plan.get('canvas',{})
    width=int(canvas.get('width',video.get('width',1280)));height=int(canvas.get('height',video.get('height',720)))
    if width<16 or height<16 or width%2 or height%2:raise ValueError('Use positive even canvas dimensions')
    audio=[]
    audio_ids=set()
    for raw in plan.get('audio',[]):
        row=copy.deepcopy(raw);file=media_file(row,root);data=info(file)
        if not row.get('id') or row['id'] in audio_ids:raise ValueError('Use distinct audio event IDs')
        audio_ids.add(row['id']);audio_evidence=None
        if not data['streams']['audio']:raise ValueError('Sound asset has no actual audio stream')
        start=number(row.get('start',0),'audio source start');end=number(row.get('end',data['duration']),'audio source end',.001)
        speed=number(row.get('speed',1),'audio speed',.5)
        if end<=start or end>data['duration']+.05 or speed>2:raise ValueError('Invalid audio source range or speed')
        at=point(row.get('at',0),lookup)
        if at<0:raise ValueError('Sound starts before the film; trim its source or revise the anchor')
        wanted=(end-start)/speed;until=point(row['until'],lookup) if 'until' in row else at+wanted
        if until<=at:raise ValueError('Audio event must have positive duration')
        loop=bool(row.get('loop',False))
        if until-at>wanted+.05 and not loop:raise ValueError('Music/sound range is too short; explicitly choose a loop or another phrase')
        bus=row.get('bus','sfx')
        if bus not in {'dialogue','native','music','ambience','sfx'}:raise ValueError('Unknown audio bus')
        if until>duration+.02:
            if bus in {'dialogue','native'}:raise ValueError('Dialogue extends beyond picture; revise coverage instead of truncating voice')
            if bus=='music':issues.append({'kind':'music_tail_clipped_by_film_end','audio':row['id'],
                'requested_until':until,'actual_until':duration,'detail':'Select a compatible musical ending/tail inside the picture; a forced duration trim is not proof of a natural cadence.'})
            until=duration
        if until<=at:continue
        if bus=='music' and not row.get('fade_out') and row.get('ending') not in {'cadence','ring_out','intentional_cut'}:
            issues.append({'kind':'music_exit_unshaped','audio':row['id'],
                           'detail':'Exit has no fade or stated musical ending. Audition the phrase and tail; this is a review candidate, not an automatic failure.'})
        if row.get('discarded_speech') and bus not in {'dialogue','native'}:raise ValueError('Reviewed speech removal belongs on native/dialogue tracks')
        if bus in {'dialogue','native'} and (row.get('dialogue_expected',True) or row.get('discarded_speech')):
            evidence,effective=speech(file,row)
            audio_evidence=effective
            required=effective.get('segments',[])
            # Only the declared local selection is relevant; intersected words must remain whole.
            partial=[w for s in required for w in (s.get('words') or []) if w['end']>start and w['start']<end
                     and not (start<=w['start']+.025 and end>=w['end']-.025)]
            if partial:raise ValueError('Detached dialogue cuts an observed word; move its source boundary')
            if evidence.get('status')!='ok':issues.append({'kind':'speech_unknown','audio':row.get('id'),'detail':'Detached speech requires actual listening/word timing; no automatic artistic pass'})
        volume=[]
        for change in row.get('volume',[]):
            local=point(change['time'],lookup)-at if isinstance(change['time'],dict) else change['time']
            volume.append({**change,'time':number(local,'local volume event time')})
        audio.append({**row,'file':inputs[str(file)],'start':start,'end':end,'speed':speed,'at':at,'until':until,'duration':until-at,'bus':bus,'loop':loop,'volume':volume})
        if audio_evidence:audio[-1]['speech_evidence']=audio_evidence
        for discard in row.get('discarded_speech',[]):
            review=asset(discard['review'],root);inputs[str(review)]=ref(review)
    overlays=[]
    for row in plan.get('overlays',[]):
        item=copy.deepcopy(row);at=point(item.get('at',0),lookup)
        end=point(item['until'],lookup) if 'until' in item else at+number(item.get('duration'),'overlay duration',.001)
        if not 0<=at<end<=duration+.05:raise ValueError('Overlay outside actual edit')
        if item.get('file'):
            file=asset(item['file'],root);item['file']=ref(file);inputs[str(file)]=ref(file)
        if item.get('font_file'):
            file=asset(item['font_file'],root);item['font_file']=str(file);item['font_sha256']=sha(file);inputs[str(file)]=ref(file)
        item.update(at=at,until=end,duration=end-at);overlays.append(item)
    caption_rows=copy.deepcopy(plan.get('captions',[]));groups={}
    for index,row in enumerate(caption_rows):
        key=row.get('audio_id') or row.get('clip')
        owner=next((a for a in audio if a.get('id')==key),None) if row.get('audio_id') else lookup.get(key)
        if row.get('timing') in {'measured','reviewed','locked'}:continue
        if owner and owner.get('speech_evidence'):groups.setdefault(('audio' if row.get('audio_id') else 'clip',key),[]).append(index)
    for (kind,key),indices in groups.items():
        owner=next(a for a in audio if a['id']==key) if kind=='audio' else lookup[key]
        evidence=owner['speech_evidence']
        aligned,status=align_caption_lines([caption_rows[i] for i in indices],evidence)
        if status['status']=='aligned_estimate':
            for index,aligned_row in zip(indices,aligned):caption_rows[index]=aligned_row
        else:issues.append({'kind':'caption_word_alignment_uncertain','clip':key,'detail':status})
    captions=[]
    for row in caption_rows:
        item=copy.deepcopy(row)
        if item.get('audio_id'):
            event=next((a for a in audio if a.get('id')==item['audio_id']),None)
            if event is None:raise ValueError('Caption references missing audio event')
            if not event['start']<=item['start']<item['end']<=min(event['end'],event['start']+event['duration']*event['speed'])+.001:
                raise ValueError('Caption speech is partly outside retained sound')
            item['start']=event['at']+(item['start']-event['start'])/event['speed']
            item['end']=event['at']+(item['end']-event['start'])/event['speed']
        elif item.get('clip'):
            item['start']=point({'clip':item['clip'],'source_time':item['start']},lookup)
            item['end']=point({'clip':item['clip'],'source_time':item['end']},lookup)
        if not 0<=item['start']<item['end']<=duration+.05:raise ValueError('Caption outside actual edit')
        captions.append(item)
    for row in plan.get('protected',[]):
        if not row.get('required',True):continue
        file=media_file(row,root);channel=row.get('channel','both');kept=[]
        if channel in {'picture','both'}:
            kept=[(s['source_start'],s['source_end']) for c in clips if c['file']['file']==str(file) for s in c['mapping']]
            if missing_intervals([[row['start'],row['end']]],kept):issues.append({'kind':'protected_picture_missing','id':row.get('id'),'interval':[row['start'],row['end']]})
        if channel in {'audio','both'}:
            kept=[(s['source_start'],s['source_end']) for c in clips if c['native_audio'] and c['file']['file']==str(file) for s in c['mapping']]
            kept.extend((a['start'],min(a['end'],a['start']+a['duration']*a['speed'])) for a in audio if a['file']['file']==str(file))
            if missing_intervals([[row['start'],row['end']]],kept):issues.append({'kind':'protected_audio_missing','id':row.get('id'),'interval':[row['start'],row['end']]})
    music_map=plan.get('music_map',[]);audio_ids={a.get('id') for a in audio if a['bus']=='music'}
    for cue in music_map:
        if cue.get('match') not in {'original','recovered','replacement','silence','unresolved'}:raise ValueError('Record each source music cue disposition honestly')
        if cue['match'] not in {'silence','unresolved'} and not set(cue.get('audio_ids',[]))<=audio_ids:raise ValueError('Source music cue refers to missing actual music events')
        if cue['match'] not in {'silence','unresolved'} and not cue.get('audio_ids'):raise ValueError('Matched music needs actual audio events')
        if cue['match']=='unresolved':issues.append({'kind':'source_music_unresolved','cue':cue.get('id')})
        if cue['match'] in {'original','recovered'} and not cue.get('basis'):issues.append({'kind':'source_music_match_unverified','cue':cue.get('id'),'detail':'Original/version/phrase match needs actual evidence, not a selected filename'})
        if cue['match']=='silence' and 'at' in cue and 'until' in cue:
            left,right=point(cue['at'],lookup),point(cue['until'],lookup)
            if any(a['bus']=='music' and a['at']<right and a['until']>left for a in audio):issues.append({'kind':'music_intrudes_source_silence','cue':cue.get('id')})
    source_cues=plan.get('source_music_cues',[])
    expected_music_ids={c['id'] if isinstance(c,dict) else c for c in source_cues}
    for identifier in expected_music_ids-{c.get('id') for c in music_map}:issues.append({'kind':'source_music_cue_unmapped','cue':identifier})
    if plan.get('source_kind')=='reference' and not source_cues:issues.append({'kind':'source_music_inventory_unverified','detail':'Recreation needs source music/silence cue coverage in the existing edit config'})
    for clip in clips:
        if clip['native_audio'] and any(a['bus']=='music' and a['at']<clip['end_at'] and a['until']>clip['at'] for a in audio):
            if clip['native_music']=='present':issues.append({'kind':'possible_double_music','clip':clip['id'],'detail':'Baked native music and a new score overlap; inspect/separate/revise before final acceptance'})
            elif clip['native_music']=='unknown':issues.append({'kind':'native_music_unchecked','clip':clip['id']})
    if plan.get('grade_notes'):issues.append({'kind':'nonexecutable_grade_notes','detail':'Convert chosen corrections into clip.grade; prose alone did not alter the picture'})
    for key in ('graphics','music','ambience','foley'):
        if plan.get(key):issues.append({'kind':'legacy_cues_not_rendered','field':key,'detail':'Use actual audio assets/overlays in the executable interface; do not claim these legacy prose/type cues are realized'})
    master=copy.deepcopy(plan.get('master',{}))
    if isinstance(master.get('duck_music'),dict):
        duck=master['duck_music']
        if 'threshold_db' in duck:duck['threshold']=10**(number(duck['threshold_db'],'duck threshold dB',-90)/20)
        elif duck.get('threshold',0)<0:
            duck['threshold_db']=duck['threshold'];duck['threshold']=10**(duck['threshold_db']/20)
    if isinstance(master.get('duck_music'),dict) and master['duck_music'].get('mode')=='envelope':
        from music_envelope import speech_windows,envelope
        duck=master['duck_music'];windows,basis=speech_windows(clips,audio)
        depth=number(duck.get('depth_db',-10),'music duck depth',-40)
        if depth>0:raise ValueError('Music duck depth must be nonpositive')
        master['music_envelope']=envelope(windows,duration,depth_db=depth,
            lead=number(duck.get('lead',.12),'duck lead'),release=number(duck.get('release',.35),'duck release'),
            merge_gap=number(duck.get('merge_gap',.3),'duck merge gap'))
        master['duck_window_basis']=basis
    if master.get('proposed_validation'):
        issues.append({'kind':'master_preset_not_applied','detail':'Move accepted lufs/true_peak_db into master to execute normalization; proposed_validation is only a note'})
    return {'version':1,'kind':'compiled_drama_edit','plan':ref(path),'canvas':{'width':width,'height':height,'fps':fps},'duration':duration,
            'clips':clips,'audio':audio,'overlays':overlays,'captions':captions,'caption_style':plan.get('caption_style',{}),'inputs':list(inputs.values()),'music_map':music_map,
            'expected_lines':plan.get('expected_lines',[]),'master':master,'pacing':plan.get('pacing',{}),'source_music_cues':source_cues,
            'editorial_metrics':editorial_metrics(clips,audio,duration,plan.get('pacing',{}).get('source_duration')),
            'author_remaining_issues':plan.get('remaining_issues',[]),'observations':plan.get('observations',{}),
            'issues':issues,'artistic_accepted':False,'purpose':'Executable edit clocks and declarations, not film-quality certification'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--ffmpeg');p.add_argument('--ffprobe');a=p.parse_args()
    try:
        result=compile_plan(a.plan,ffmpeg=a.ffmpeg,ffprobe=a.ffprobe);save(a.output,result)
        print(json.dumps({'duration':result['duration'],'clips':len(result['clips']),'issues':result['issues'],'artistic_accepted':False},ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:print('EDIT_COMPILE_FAILED: '+str(exc));return 1
if __name__=='__main__':raise SystemExit(main())
