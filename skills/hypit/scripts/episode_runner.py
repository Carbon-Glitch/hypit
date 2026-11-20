"""Reusable block preparation and bounded H3 queue; creative/visual adoption stays with the executor."""
from __future__ import annotations
import argparse,copy,json,os,re,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runninghub_h3 as rh
from shot_packet import build
from write_drama_documents import read,save,record


def path(value,root):
    return (root/(value['file'] if isinstance(value,dict) else value)).resolve()


def actual(value,root):
    p=path(value,root)
    if not p.is_file():raise FileNotFoundError(str(p))
    result=record(p)
    if isinstance(value,dict) and value.get('sha256')!=result['sha256']:
        raise ValueError('Input changed; revise the affected recipe: '+str(p))
    return result


def store(p,value):
    if p.exists() and read(p)==value:return
    save(p,value)


def manifest(file):
    file=Path(file).resolve();data=read(file);root=file.parent
    if data.get('version')!=1 or not data.get('blocks'):raise ValueError('Use version=1 and actual blocks')
    capacity=data.get('concurrency',1)
    if type(capacity)!=int or not 1<=capacity<=32:raise ValueError('concurrency must match the known account capacity')
    ids=[b['id'] for b in data['blocks']]
    if len(set(ids))!=len(ids):raise ValueError('Block IDs must be distinct')
    jobs=[path(b['job'],root) for b in data['blocks']]
    if len(set(jobs))!=len(jobs) or any(not p.is_relative_to(root) for p in jobs):
        raise ValueError('Use distinct job directories inside the episode project')
    graph={b['id']:set(b.get('after',[])) for b in data['blocks']};done=set()
    if any(not edges<=set(ids) for edges in graph.values()):raise ValueError('Unknown block dependency')
    while len(done)<len(ids):
        ready={k for k,v in graph.items() if k not in done and v<=done}
        if not ready:raise ValueError('Block dependencies contain a cycle')
        done.update(ready)
    return data,root


def packet_spec(value,root):
    spec=copy.deepcopy(value)
    for name in ('storyboard','source_table','source_context'):
        if name in spec:spec[name]=actual(spec[name],root)
    for name in ('owners','dependencies'):
        spec[name]=[actual(v,root) for v in spec.get(name,[])]
    spec['adoptions']={k:actual(v,root) for k,v in spec.get('adoptions',{}).items()}
    for scene,values in spec.get('shared_state',{}).items():
        spec['shared_state'][scene]={k:actual(v,root) for k,v in values.items()}
    for item in spec.get('owner_slices',[]):item['artifact']=actual(item['artifact'],root)
    spec.setdefault('version',1)
    return spec


def stage_block(block,data,root):
    job=path(block['job'],root);job.mkdir(parents=True,exist_ok=True)
    if (job/'receipt.json').exists() or (job/'submit-started.json').exists():
        return {'id':block['id'],'status':'submitted_preserved','job':str(job)}
    if 'packet' not in block:
        if (job/'prepared.json').exists():return {'id':block['id'],'status':'prepared','job':str(job)}
        raise ValueError('Unprepared block needs its existing packet selection data')
    spec=packet_spec(block['packet'],root)
    store(job/'packet-selection.json',spec)
    store(job/'SHOT_PACKET.json',build(job/'packet-selection.json'))
    media=copy.deepcopy(block['media'])
    for item in media:
        for key in ('asset','review','source_clip'):
            if key in item:item[key]=actual(item[key],root)
    selection={'version':1,'route':actual(data['route'],root),'packet':record(job/'SHOT_PACKET.json'),
               'media':media,'instance_type':'default'}
    store(job/'reference-selection.json',selection)
    store(job/'REFERENCE_PLAN.json',rh.reference_plan(job/'reference-selection.json'))
    return {'id':block['id'],'status':'staged','job':str(job)}


def writing(file,output,batch,selected=None):
    data,root=manifest(file);units=[];outputs=[];waiting=[]
    for block in data['blocks']:
        if selected and block['id'] not in selected:continue
        job=path(block['job'],root)
        if (job/'receipt.json').exists() or (job/'submit-started.json').exists():continue
        try:stage_block(block,data,root)
        except FileNotFoundError:
            waiting.append(block['id']);continue
        prompt=job/block.get('prompt','H3_PROMPT.txt')
        task=block.get('task')
        if not task:raise ValueError('Batched writing needs the authored directing task for each block')
        name=prompt.relative_to(root).as_posix()
        units.append({'id':block['id'],'reference_plan':str(job/'REFERENCE_PLAN.json'),'output_files':[name]})
        outputs.append({'file':name,'role':'h3_prompt','coverage':block['id'],
                        'instruction':task+' Duration '+str(block['duration'])+' seconds. Use this unit\'s exact image/audio labels and full selected rows. Return the six official Ref2VA sections.'})
    if not outputs:raise ValueError('No unsent blocks selected for writing')
    request={'version':1,'project_root':str(root),'scope':data.get('scope','Current scene H3 prompts'),
             'batch':batch,'source_kind':data.get('source_kind','reference'),'h3_mode':'Ref2VA','execution_units':units,
             'task':'Write the complete requested H3 prompts. Each execution unit owns its output files, rows and reference labels. Reuse common facts supplied once.',
             'inputs':data.get('writing_inputs',[]),'outputs':outputs,
             'max_output_tokens':data.get('writing_max_output_tokens',min(24000,4000*len(outputs)))}
    save(output,request);return {'request':str(Path(output).resolve()),'blocks':[u['id'] for u in units],'waiting_input':waiting}


def compile_prompt(block,job):
    source=job/block.get('prompt','H3_PROMPT.txt');text=source.read_text(encoding='utf-8-sig')
    rh.check_prompt_sections(text,'Ref2VA');rh.generation_policy(text)
    plan=read(job/'REFERENCE_PLAN.json');packet=read(job/'SHOT_PACKET.json')
    clauses={}
    # Reuse one authored reference line when its declared scopes are already present.
    for reference in plan['references']:
        control=reference['control_intent'];label=reference['label']
        scopes=control['allow']+control['deny']
        existing=next((line.strip() for line in text.splitlines() if label in line and
                       all(scope.casefold() in line.casefold() for scope in scopes)),None)
        clause=label+': use for '+' / '.join(control['allow'])
        if control['deny']:clause+='; exclude '+' / '.join(control['deny'])
        clauses[reference['id']]=existing or clause+'.'
    additions=[v for v in clauses.values() if v not in text]
    for shot in packet.get('continuity',{}).get('shots',[]):
        pieces=[]
        if shot['camera']['view'] not in text:pieces.append('camera: '+shot['camera']['view'])
        for label,key in (('entry','required_entry'),('planned changes','planned_changes')):
            missing=[k+' = '+v for k,v in shot[key].items() if v not in text]
            if missing:pieces.append(label+': '+'; '.join(missing))
        if pieces:additions.append(shot['shot']+' '+'. '.join(pieces)+'.')
    if additions:
        marker=re.search(r'(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?retention_analysis(?:\*\*)?(?:[ \t]*:[ \t]*|[ \t]*(?=\r?$))',text)
        if marker is None:raise ValueError('Cannot locate the official retention_analysis section')
        text=text[:marker.end()]+'\n'+'\n'.join(additions)+'\n'+text[marker.end():]
    rh.check_prompt_sections(text,'Ref2VA')
    target=job/'H3_PROMPT.compiled.txt'
    if not target.exists() or target.read_text(encoding='utf-8-sig')!=text:target.write_text(text,encoding='utf-8')
    store(job/'PROMPT_COMPILATION.json',{'version':1,'source':record(source),'compiled':record(target),
          'operation':'Exact reference-control/state strings only; no rewriting of authored words','additions':additions})
    selection={'version':1,'reference_plan':record(job/'REFERENCE_PLAN.json'),'prompt':record(target),
               'duration':block['duration'],'instance_type':'default','reference_quotes':{k:[v] for k,v in clauses.items()}}
    store(job/'execution-selection.json',selection)
    return job/'execution-selection.json'


def task_id(job):
    if not (job/'receipt.json').exists():return None
    receipt=read(job/'receipt.json');return receipt.get('taskId') or receipt.get('data',{}).get('taskId')


def downloaded(job):
    if not (job/'download.json').exists():return False
    value=read(job/'download.json');rows=value.get('files',[])
    if not rows:return False
    for row in rows:actual(row['artifact'],job)
    return True


def tick(file,*,client=None,ffprobe=None,now=None):
    data,root=manifest(file);now=time.time() if now is None else now
    folder=root/'.hypit-run';folder.mkdir(exist_ok=True);state_file=folder/'state.json'
    state=read(state_file) if state_file.exists() else {'version':1,'jobs':{}}
    if state.get('route') and state['route']!=record(path(data['route'],root)):
        raise ValueError('Queue route changed; recover existing tasks with their original route')
    current={b['id'] for b in data['blocks']}
    if any(k not in current and v.get('status') not in {'downloaded','failed','failure','canceled','cancelled','error'} for k,v in state['jobs'].items()):
        raise ValueError('Keep outstanding tasks in the manifest until their original outcome is recovered')
    states=state['jobs'];events=[];active=[];held=[]
    for block in data['blocks']:
        job=path(block['job'],root);row=states.setdefault(block['id'],{})
        if row.get('job') and row['job']!=str(job):raise ValueError('Existing task ID cannot move to another job directory')
        row['job']=str(job)
        if downloaded(job):row['status']='downloaded'
        elif task_id(job):
            prior=read(job/'status.json') if (job/'status.json').exists() else {}
            if prior.get('status') in {'FAILED','FAILURE','CANCELED','CANCELLED','ERROR'}:row['status']='failed'
            else:active.append(block)
        elif (job/'submit-started.json').exists() or (job/'receipt.json').exists():
            row['status']='submission_uncertain';held.append(block)
        else:row['status']='pending'
    if active:
        client=client or rh.HttpClient()
        def query(block):
            try:return block,rh.query(path(block['job'],root),path(data['route'],root),client=client,ffprobe=ffprobe),None
            except (OSError,ValueError,RuntimeError) as exc:return block,None,str(exc)
        with ThreadPoolExecutor(max_workers=data.get('concurrency',1)) as pool:
            for block,result,error in pool.map(query,active):
                row=states[block['id']]
                if error:row.update(status='query_pending',finding=error)
                else:
                    status='downloaded' if downloaded(path(block['job'],root)) else str(result['status']).lower()
                    if status=='pending':status='pending_remote'
                    row.update(status=status);row.pop('finding',None)
    occupying=sum(r['status'] in {'submission_uncertain','query_pending','running','queued','queue','submitted','pending_remote'} for r in states.values())
    # Unknown live provider status occupies its slot too; only explicit terminal states release it.
    occupying=max(occupying,len(held)+sum(states[b['id']]['status'] not in {'downloaded','failed','failure','canceled','cancelled','error'} for b in active))
    for block in data['blocks']:
        row=states[block['id']]
        if row['status']!='pending' or task_id(path(block['job'],root)) or occupying>=data.get('concurrency',1):continue
        if not all(states[k].get('status')=='downloaded' for k in block.get('after',[])):
            row['status']='waiting_dependency';continue
        job=path(block['job'],root)
        try:
            for value in block.get('requires',[]):actual(value,root)
            if block.get('packet') or not (job/'prepared.json').exists():
                stage_block(block,data,root)
                if not (job/block.get('prompt','H3_PROMPT.txt')).exists():row['status']='needs_authored_prompt';continue
                spec=compile_prompt(block,job)
                prepared=read(job/'prepared.json') if (job/'prepared.json').exists() else {}
                if prepared.get('selection')!=record(spec):
                    client=client or rh.HttpClient()
                    rh.prepare(spec,job,client=client,ffprobe=ffprobe,upload_cache=root/'.hypit-runninghub/uploads')
            client=client or rh.HttpClient()
            result=rh.submit(job=job,route_path=path(data['route'],root),client=client)
            row.update(status='submitted',task_id=result['task_id']);occupying+=1
            events.append({'id':block['id'],'status':'submitted','task_id':result['task_id']})
        except FileNotFoundError as exc:row.update(status='waiting_input',finding=str(exc))
        except (OSError,ValueError,RuntimeError) as exc:
            # A proved 421 rejection has no accepted task. Preserve it and retry only after backoff.
            receipt=read(job/'receipt.json') if (job/'receipt.json').exists() else {}
            code=receipt.get('errorCode') or receipt.get('code')
            if not task_id(job) and str(code) in {'421','TASK_QUEUE_MAXED'}:
                archive=job/('queue-rejection-'+str(time.time_ns()));archive.mkdir()
                for name in ('receipt.json','submit-started.json'):
                    if (job/name).exists():(job/name).replace(archive/name)
                row.update(status='queue_full',finding='Provider explicitly rejected a full queue; no task accepted')
                break
            status='pending_remote' if task_id(job) else 'submission_uncertain' if (job/'submit-started.json').exists() else 'needs_repair'
            row.update(status=status,finding=str(exc))
    state.update(route=record(path(data['route'],root)),updated_at=now,events=events,artistic_accepted=False)
    save(state_file,state)
    return {'state':str(state_file),'jobs':states,'events':events,'artistic_accepted':False}


def finish(file,*,ffprobe=None):
    from finish_drama import render
    data,root=manifest(file);outputs=[]
    if not data.get('finishing'):raise ValueError('finishing needs the already authored edit/output pairs')
    for item in data['finishing']:
        plan=path(item['edit'],root);output=path(item['output'],root)
        if not output.is_relative_to(root):raise ValueError('Delivery output must stay in this production')
        result=render(plan,output,ffprobe=ffprobe)
        captions=result['compiled']['captions']
        def clock(seconds):
            ms=round(seconds*1000);hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
            return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'
        subtitle=None
        if captions:
            srt=output.with_suffix('.srt')
            text='\n\n'.join(f'{n}\n{clock(c["start"])} --> {clock(c["end"])}\n{c["text"]}' for n,c in enumerate(captions,1))+'\n'
            if srt.exists() and srt.read_text(encoding='utf-8-sig')!=text:
                raise ValueError('Subtitle output already has different content; preserve it and choose a new output version')
            if not srt.exists():srt.write_text(text,encoding='utf-8')
            subtitle=record(srt)
        music=[];seen=set()
        for audio in result['compiled']['audio']:
            if audio.get('bus')!='music' or audio['file']['file'] in seen:continue
            seen.add(audio['file']['file']);source=Path(audio['file']['file'])
            receipt=source.with_suffix(source.suffix+'.asset.json')
            if not receipt.exists():continue
            asset=read(receipt)
            if not asset.get('license',{}).get('credit'):continue
            if asset.get('asset')!=audio['file']:raise ValueError('Music asset receipt differs from the rendered audio')
            if asset.get('license',{}).get('credit'):
                music.append({'asset':audio['file'],'record':record(receipt),'credit':asset['license']['credit']})
        credits=None
        if music:
            credit_file=output.with_suffix('.music-credits.txt');text='\n\n'.join(item['credit'] for item in music)+'\n'
            if credit_file.exists() and credit_file.read_text(encoding='utf-8-sig')!=text:
                raise ValueError('Music credits changed; preserve existing delivery and choose a new version')
            if not credit_file.exists():credit_file.write_text(text,encoding='utf-8')
            credits=record(credit_file)
        outputs.append({'output':result['output'],'status':result['status'],'subtitle':subtitle,'music_credits':credits,'music_assets':music,
                        'post_receipt':record(output.with_suffix(output.suffix+'.post.json')),'artistic_accepted':False})
    result={'version':1,'outputs':outputs,'artistic_accepted':False,
            'next':'Review the actual encoded files and retain their findings in existing DELIVERY; rendering alone is not artistic acceptance.'}
    save(root/'.hypit-run/outputs.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['stage','writing','run','finish']);p.add_argument('manifest',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--batch');p.add_argument('--blocks');p.add_argument('--watch',type=float,default=0);p.add_argument('--poll',type=float,default=20);p.add_argument('--ffprobe')
    a=p.parse_args();lock=None
    try:
        data,root=manifest(a.manifest)
        if a.action=='finish':
            print(json.dumps(finish(a.manifest,ffprobe=a.ffprobe),ensure_ascii=False));return 0
        if a.action=='stage':
            result=[]
            for block in data['blocks']:
                try:result.append(stage_block(block,data,root))
                except FileNotFoundError as exc:result.append({'id':block['id'],'status':'waiting_input','finding':str(exc)})
            print(json.dumps(result,ensure_ascii=False));return 0
        if a.action=='writing':
            if not a.output or not a.batch:raise ValueError('writing needs --output and --batch')
            print(json.dumps(writing(a.manifest,a.output,a.batch,a.blocks.split(',') if a.blocks else None),ensure_ascii=False));return 0
        folder=root/'.hypit-run';folder.mkdir(exist_ok=True);lock=folder/'runner.lock'
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
        deadline=time.monotonic()+max(0,a.watch);previous=None;client=rh.HttpClient()
        while True:
            result=tick(a.manifest,client=client,ffprobe=a.ffprobe)
            summary={k:v['status'] for k,v in result['jobs'].items()}
            if summary!=previous:print(json.dumps(result,ensure_ascii=False),flush=True);previous=summary
            live=any(s in {'running','queued','queue','submitted','query_pending','pending_remote','queue_full'} for s in summary.values())
            if not live or time.monotonic()>=deadline:break
            time.sleep(min(30,max(5,a.poll),max(0,deadline-time.monotonic())))
        return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print('EPISODE_RUN_FAILED: '+str(exc));return 1
    finally:
        if lock is not None and lock.exists() and lock.read_text()==str(os.getpid()):lock.unlink()


if __name__=='__main__':raise SystemExit(main())
