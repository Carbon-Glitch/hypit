"""Remember real selected music/SFX ranges and recall them without another catalog search.

The local index stores references and directing notes, never audio or artistic acceptance.
"""
from __future__ import annotations
import hashlib,json,math,re
from pathlib import Path
from post_timeline import read,save,ref
from inspect_finishing import ffmpeg_path,metadata

CONTEXT_FIELDS=('theme','variant','function','ending','tags','basis','review')


def index_path(value=None):
    return Path(value).resolve() if value else Path.home()/'.hypit/music-libraries/segments.json'


def remember(selection,*,index=None,ffmpeg=None):
    selection=Path(selection).resolve(strict=True);chosen=read(selection)
    tracks=chosen.get('tracks',[])
    if not isinstance(tracks,list) or not tracks:raise ValueError('Remember selected actual tracks/ranges')
    path=index_path(index);saved=read(path) if path.exists() else {'version':1,'cues':[]}
    if saved.get('version')!=1 or not isinstance(saved.get('cues'),list):raise ValueError('Unsupported local cue index')
    cues={c['id']:c for c in saved['cues']};binary=ffmpeg_path(ffmpeg);measured={};added=[]
    for item in tracks:
        source=(selection.parent/item['file']).resolve(strict=True)
        if source not in measured:measured[source]=(ref(source),metadata(source,binary))
        source_ref,data=measured[source];start=item.get('start',0);end=item.get('end',data['duration'])
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (start,end)) or not 0<=start<end<=data['duration']+.001:
            raise ValueError('Remember an actual finite audio range')
        if not data['streams']['audio']:raise ValueError('Remembered source has no actual audio')
        start,end=float(start),float(end)
        notes={k:item[k] for k in CONTEXT_FIELDS if k in item}
        if notes.get('review'):
            review=notes['review'];review={'file':review} if isinstance(review,str) else review
            review_ref=ref((selection.parent/review['file']).resolve(strict=True))
            if review.get('sha256') and review['sha256']!=review_ref['sha256']:raise ValueError('Cue review reference changed')
            notes['review']=review_ref
        identity={'sha256':source_ref['sha256'],'start':start,'end':end,
                  **{k:item.get(k,'') for k in ('theme','variant','function')}}
        identifier='cue-'+hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
        sidecar=source.with_suffix(source.suffix+'.asset.json')
        asset=read(sidecar) if sidecar.exists() else {}
        # References preserve the selected asset's existing provenance, without granting new rights.
        asset_record=ref(sidecar) if asset.get('asset')==source_ref else None
        cue={'id':identifier,'source':source_ref,'start':start,'end':end,
             'title':item.get('title') or asset.get('title') or source.stem,
             'label':item.get('label','Selected audio range'),'context':notes,'asset_record':asset_record,
             'selection':ref(selection),'artistic_accepted':False}
        cues[identifier]=cue;added.append(identifier)
    save(path,{'version':1,'cues':list(cues.values()),
               'note':'Saved directing notes and source ranges; recall is not a listening or licensing verdict.'})
    return {'index':str(path),'saved_ids':added,'total_cues':len(cues),'audio_copied':False,'artistic_accepted':False}


def recall(query,*,index=None,limit=4):
    if not 1<=limit<=20:raise ValueError('Recall a small candidate set, limit1..20')
    terms=re.findall(r'[\w-]+',str(query).casefold())
    if not terms:raise ValueError('Recall by theme, variant, function or descriptive keywords')
    path=index_path(index);data=read(path) if path.exists() else {'version':1,'cues':[]}
    if data.get('version')!=1:raise ValueError('Unsupported local cue index')
    ranked=[]
    for cue in data['cues']:
        text=json.dumps({k:cue[k] for k in ('title','label','context')},ensure_ascii=False).casefold()
        hits=[word for word in terms if word in text]
        if hits:ranked.append((len(hits),cue))
    ranked.sort(key=lambda pair:(-pair[0],pair[1]['id']))
    tracks=[];unavailable=[];checked={}
    for score,cue in ranked:
        if len(tracks)>=limit:break
        source=Path(cue['source']['file'])
        if source not in checked:
            try:checked[source]=ref(source)
            except OSError:checked[source]=None
        if checked[source]!=cue['source']:
            unavailable.append({'id':cue['id'],'reason':'Source missing or changed'});continue
        item={'id':cue['id'],'file':str(source),'start':cue['start'],'end':cue['end'],
              'label':cue['label'],'title':cue['title'],**cue['context'],'retrieval_score':score}
        asset=cue.get('asset_record')
        if asset:
            try:valid=ref(asset['file'])==asset
            except OSError:valid=False
            if valid:item['asset_record']=asset
            else:item['provenance_note']='Saved asset sidecar changed or is missing; inspect current source record'
        tracks.append(item)
    return {'version':1,'intent':query,'tracks':tracks,'unavailable':unavailable,'listened':False,
            'note':'Real retained ranges and prior notes; confirm current scene fit, timing and use basis. Empty results fall back to existing search.'}
