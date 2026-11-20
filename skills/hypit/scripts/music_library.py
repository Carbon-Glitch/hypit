"""Search two public author catalogs and acquire selected CC-BY music; no bulk audio mirroring."""
from __future__ import annotations
import copy,hashlib,html,json,re,time,urllib.request,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote,urlencode,urlparse
from post_timeline import read,save,ref

UA='Hypit-Music/1.0 (public music metadata; selected project downloads)'
CC='https://creativecommons.org/licenses/by/4.0/'
PROVIDERS=('incompetech','scott_buckley')
ALIASES={'悬疑':'suspense mystery dark','紧张':'tense tension suspense','史诗':'epic orchestral','玄幻':'fantasy epic',
         '温情':'warm heartfelt emotional','悲伤':'sad melancholic','轻松':'light relaxing','搞笑':'comedy humorous playful',
         '治愈':'gentle calm hopeful','压抑':'dark somber','反转':'dramatic suspense','弦乐':'strings','钢琴':'piano','低音':'bass low'}


def cache_root(value=None):
    return Path(value).resolve() if value else Path.home()/'.hypit/music-libraries'


def get(url,*,timeout=30):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/html;q=0.9'})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        body=response.read();return body,{'url':url,'final_url':response.url,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)}


def clean(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>',' ',str(value))).split())


def seconds(value):
    if not value:return None
    try:
        parts=[float(v) for v in str(value).split(':')]
        total=0
        for part in parts:total=total*60+part
        return total
    except ValueError:return None


def words(query):
    expanded=str(query)
    for key,value in ALIASES.items():expanded=expanded.replace(key,value)
    return list(dict.fromkeys(re.findall(r'[a-z0-9]{3,}',expanded.casefold())))


def incompetech():
    catalog='https://incompetech.com/music/royalty-free/pieces.json'
    body,origin=get(catalog);data=json.loads(body)
    genres={}
    try:
        raw,_=get('https://incompetech.com/music/royalty-free/genre.json')
        genres={str(x['id']):x['genre'] for x in json.loads(raw)}
    except (OSError,ValueError,KeyError):pass # The actual song catalog remains usable without genre labels.
    tracks=[]
    for row in data:
        name=row.get('filename','');title=row.get('title','')
        if not title or not name or '/' in name or '\\' in name or not name.lower().endswith('.mp3'):continue
        identifier=row.get('isrc') or row.get('uuid') or hashlib.sha256(name.encode()).hexdigest()[:16]
        page='https://incompetech.com/music/royalty-free/index.html?'+urlencode({'isrc':row['isrc']}) if row.get('isrc') else 'https://incompetech.com/music/royalty-free/'
        credit=f'"{title}" Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 4.0\n{CC}\nSource: {page}'
        tracks.append({'id':'incompetech:'+str(identifier),'provider':'incompetech','title':title,'artist':'Kevin MacLeod',
            'description':clean(row.get('description','')),'moods':clean(row.get('feel','')),
            'genre':genres.get(str(row.get('genre')),str(row.get('genre') or '')),
            'instruments':clean(row.get('instruments','')),'bpm':row.get('bpm'),'duration_hint':seconds(row.get('length')),
            'page_url':page,'download_url':'https://incompetech.com/music/royalty-free/mp3-royaltyfree/'+quote(name,safe=''),
            'license':{'name':'CC BY 4.0','url':CC,'attribution_required':True,'credit':credit,
                       'basis_url':'https://incompetech.com/agent-section/','verification':'Author-published catalog-wide license; confirm the selected page when acquiring'}})
    if not tracks:raise ValueError('Incompetech catalog had no usable music records')
    return tracks,origin


def scott_buckley(query):
    # The public library advertises this REST root via rel=https://api.w.org/.
    terms=words(query);search=terms[0] if terms else ''
    endpoint='https://www.scottbuckley.com.au/library/wp-json/wp/v2/posts?'+urlencode(
        {'search':search,'per_page':30,'_fields':'id,link,title,content,excerpt'})
    body,origin=get(endpoint);tracks=[]
    for row in json.loads(body):
        content=html.unescape(row.get('content',{}).get('rendered',''))
        urls=list(dict.fromkeys(re.findall(r'https?://[^\s"\'<>]+\.mp3(?:\?[^\s"\'<>]*)?',content)))
        urls=[u for u in urls if urlparse(u).hostname in {'www.scottbuckley.com.au','scottbuckley.com.au'}]
        if not urls or not re.search(r'creativecommons\.org/licenses/by/4\.0',content,re.I):continue
        plain=clean(content)
        attribution=re.search(r'Attribution format:\s*(.*?)(?:Can.t provide attribution|This track was supported|$)',plain,re.I)
        title=clean(row['title']['rendered']);credit=attribution.group(1).strip() if attribution else f'"{title}" by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au'
        tracks.append({'id':'scott_buckley:'+str(row['id']),'provider':'scott_buckley','title':title,'artist':'Scott Buckley',
            'description':clean(row.get('excerpt',{}).get('rendered','')),'moods':'','instruments':'','genre':'','bpm':None,'duration_hint':None,
            'page_url':row['link'],'download_url':urls[0],
            'license':{'name':'CC BY 4.0','url':CC,'attribution_required':True,'credit':credit+'\n'+CC+'\nSource: '+row['link'],
                       'basis_url':row['link'],'verification':'CC BY 4.0 and the download link observed in this individual author post'}})
    return tracks,origin


def catalog(provider,query,*,cache=None,refresh=False,offline=False):
    if provider not in PROVIDERS:raise ValueError('Unsupported live catalog: '+provider)
    root=cache_root(cache);root.mkdir(parents=True,exist_ok=True)
    key='all' if provider=='incompetech' else hashlib.sha256(' '.join(words(query)).encode()).hexdigest()[:16]
    target=root/(provider+'-'+key+'.json');previous=read(target) if target.exists() else None
    if previous and (offline or (not refresh and time.time()-previous['fetched_at']<86400)):
        return previous,ref(target),'cached'
    if offline:raise ValueError('No offline catalog cached for '+provider+' / '+query)
    try:
        tracks,origin=incompetech() if provider=='incompetech' else scott_buckley(query)
        value={'version':1,'provider':provider,'query_scope':key,'fetched_at':time.time(),'origin':origin,'tracks':tracks}
        temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(target)
        return value,ref(target),'live'
    except (OSError,ValueError,KeyError) as exc:
        if previous:return previous,ref(target),'cached_stale: '+type(exc).__name__
        raise


def score(track,terms):
    weights={'title':5,'moods':7,'instruments':4,'genre':3,'description':2};total=0;matched=[]
    for term in terms:
        hit=False
        for field,weight in weights.items():
            if term in str(track.get(field,'')).casefold():total+=weight;hit=True
        if hit:matched.append(term)
    return total,matched


def search(query,*,providers=PROVIDERS,limit=6,cache=None,refresh=False,offline=False):
    terms=words(query)
    if not terms:raise ValueError('Provide concrete music mood/instrument keywords (English or supported Chinese terms)')
    if not 1<=limit<=20:raise ValueError('Select a small candidate set: limit1..20')
    if not providers or not set(providers)<=set(PROVIDERS):raise ValueError('Choose the implemented public catalogs')
    def fetch(provider):
        try:return provider,catalog(provider,query,cache=cache,refresh=refresh,offline=offline),None
        except (OSError,ValueError,KeyError) as exc:return provider,None,type(exc).__name__+': '+str(exc)
    candidates=[];status=[]
    with ThreadPoolExecutor(max_workers=min(2,len(providers))) as pool:
        for provider,result,error in pool.map(fetch,providers):
            if error:status.append({'provider':provider,'status':'unavailable','detail':error});continue
            value,source,mode=result;status.append({'provider':provider,'status':mode,'records':len(value['tracks']),'catalogue':source})
            ranked=[]
            for track in value['tracks']:
                points,hits=score(track,terms)
                if points:ranked.append({**track,'retrieval_score':points,'matched_keywords':hits,'catalogue':source})
            ranked.sort(key=lambda r:(-r['retrieval_score'],r['title']))
            # Keep both available providers represented, rather than returning only one giant catalog.
            candidates.extend(ranked[:limit])
    candidates.sort(key=lambda r:(-r['retrieval_score'],r['title']))
    chosen=[]
    for provider in providers:
        first=next((r for r in candidates if r['provider']==provider),None)
        if first and len(chosen)<limit:chosen.append(first)
    chosen.extend(r for r in candidates if r['id'] not in {c['id'] for c in chosen})
    return {'version':1,'query':query,'keywords':terms,'providers':status,'candidates':chosen[:limit],
            'listened':False,'note':'Metadata retrieval only. Audition actual files with the scene before choosing music; no automatic artistic acceptance.'}


def fetch(selection,identifier,output,*,ffmpeg=None):
    selection=Path(selection).resolve();data=read(selection)
    candidate=next((r for r in data.get('candidates',[]) if r['id']==identifier),None)
    if candidate is None:raise ValueError('Choose an actual candidate ID from this search')
    output=Path(output).resolve();receipt=output.with_suffix(output.suffix+'.asset.json')
    if output.exists() and receipt.exists():
        prior=read(receipt)
        if prior.get('track_id')==identifier and prior.get('asset')==ref(output) and prior.get('credits') and ref(prior['credits']['file'])==prior['credits']:
            if prior.get('license_page') and ref(prior['license_page']['file'])==prior['license_page']:return prior
    origin=Path(candidate['catalogue']['file'])
    if ref(origin)!=candidate['catalogue']:raise ValueError('Catalog changed; repeat the metadata search before acquiring')
    track=next((r for r in read(origin)['tracks'] if r['id']==identifier),None)
    if track is None or any(candidate.get(k)!=v for k,v in track.items()):raise ValueError('Candidate differs from its author catalog')
    page,evidence=get(track['page_url']);text=page.decode('utf-8',errors='replace')
    if not re.search(r'creativecommons\.org/licenses/by/4\.0',html.unescape(text),re.I):
        raise ValueError('Selected page no longer shows the supported CC BY 4.0 license; inspect before using')
    from music_assets import acquire
    result=acquire(track['download_url'],output,page=track['page_url'],title=track['title'],kind='replacement',ffmpeg=ffmpeg)
    evidence_path=output.with_suffix(output.suffix+'.source-page.html')
    if not evidence_path.exists() or evidence_path.read_bytes()!=page:evidence_path.write_bytes(page)
    result.update(provider=track['provider'],track_id=track['id'],artist=track['artist'],license=track['license'],
                  catalogue=candidate['catalogue'],license_page=ref(evidence_path),license_page_fetch=evidence,
                  listened=False,original_match_verified=False)
    credits=output.with_suffix('.credits.txt');credit=track['license']['credit']+'\n'
    if credits.exists() and credits.read_text(encoding='utf-8-sig')!=credit:raise ValueError('Existing attribution differs; preserve it and use a new asset name')
    if not credits.exists():credits.write_text(credit,encoding='utf-8')
    result['credits']=ref(credits);save(output.with_suffix(output.suffix+'.asset.json'),result)
    return result
