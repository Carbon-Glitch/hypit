"""Optional current-Agent writing context and read-only recovery of historical author receipts."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import time

from source_shots import compile_table, load_table
from analyze_audio import validate_shape

MODEL = "google/gemini-3.8-flash"
PROVIDER = "openrouter"
ENDPOINT = "https://openrouter.ai/api/v1"
ROLES = {"design","treatment","world","characters","visual","screenplay","storyboard","director",
         "sound","post","asset_prompt","h3_prompt","copy"}
BASE = """You are the short-drama writer/director. Complete the requested files and coverage.
Canonical source rows/shared/E/EX records own source facts. Preserve their action, dialogue, listener
response, reveals and audience experience. Distinguish observations, inferences and target choices.
Reuse accepted content and keep stable IDs. Ordinary recreation uses STORYBOARD for action/dialogue
and DESIGN for needed choices; substantial new story uses a full literary body.
Use actual target assets and the current adopted state. Report genuine unresolved dependencies.
Write the requested UTF-8 bodies, including raw CSV when requested, into the structured response.
"""

ROLE_GUIDANCE = (
    ({"design", "visual", "storyboard", "director", "h3_prompt", "post"},
     """Direct boldly for audience emotion and a distinctive cinematic experience. Actively select and
combine viewpoint, composition, blocking, camera movement, light, sound, transitions and editing.
Sensory pleasure, atmosphere, spectacle and formal rhythm are valid creative aims. Develop contrasting
viewing approaches for important passages and choose the strongest within the commissioned direction.
Design shot groups and transition pairs before generation; carry exit/entry geometry, action phases,
sound bridges and post-production requirements through the actual deliverables. The director owns
new choices in DESIGN/STORYBOARD; H3 realizes those choices and EDIT realizes the cut.
"""),
    ({"design","treatment","world","characters","visual","screenplay","director","storyboard","sound"},
     """Use supplied selling points as scene priorities: promise, concrete carriers, setup/escalation/payoff
and loss signal. Preserve consequential observed vocal traits;
stable identity is separate from this line's tactic. Unknown voice features remain unknown.
Design the emotional/music arc in existing owners. Reuse source timing; rehearse only uncertain
changed-language, contact, spatial or reveal passages.
"""),
    ({"storyboard"},
     """Use the supplied target headers: 26 columns for new files, current headers for existing owners. Leave inapplicable optional cells empty; mark real unknowns explicitly. CSV-escape commas/quotes including embedded JSON.
Original additions use N/A:新增 source IDs. Each shot has a readable start, main state-change chain,
credible end, information-release boundary and cut purpose. Fit complete speech plus actions that
cannot overlap and needed reactions; restructure overloaded blocks. A frozen start image depicts the visible starting instant. Recheck visible entities against actual asset bindings.
Use @continuity only for consequential dependencies, per the spatial guide; initial state omits
predecessor. Preserve anatomical hands, world relations and offscreen state;
screen coordinates are camera-relative. Stable keys need actual accepted unchanged-span evidence.
"""),
    ({"asset_prompt"},
     """Classify identity, look/state variant and shot transient before creating an asset. Each new image
needs a real shot consumer. Keep reusable four-panel character masters and actual palette/look facts;
use a recurring location overview and camera/state images with actual consumers. Persistent body-object-space relations continue across cuts.
Preserve accepted identity and unrelated details in variants. Reference inputs control only their
declared identity/look/geography/composition duties.
"""),
    ({"h3_prompt"},
     """Apply the supplied H3 mode guide and direction-depth guidance to the selected complete rows,
current state and reference roles. Use the actual image/audio labels for this unit. Check which
established environmental activities continue, how listeners behave, and how physical reactions settle.
Shape their attention hierarchy, motion contrast and sound perspective. Carry the accepted
composition, performance/listener, camera/focus, light/material, sound and exit decisions into the
visible/audible timeline. Expand their causal coordination before removing repetition; one dramatic
change may involve several compatible concurrent channels. Preserve complete dialogue and reveals.
Adapt the examples' specificity to this production. Give detailed_description the full performed
process; resolve missing directing choices in the owning stage and carry them back into the prompt.
Size batches to preserve every unit's expression.
"""),
    ({"post"},
     """Inspect actual scoped footage/rough cut and blind word clocks. Identify usable source bands and
defects before choosing expressive in/out points. Shape performance, reactions, montage, match cuts,
J/L bridges, transitions, sound and speed changes into an emotional progression. Compare meaningful
alternate cuts of key passages using available footage; preserve the commissioned words and beats.
Write executable EDIT JSON with important reasons/observations in its existing fields.
Measured word timing outranks model clock guesses. Re-conform music/captions/cues after cuts/speeds.
Use supplied editorial_metrics to locate cumulative waits and uncovered music spans, not as quotas:
native music/effects or purposeful quiet may fill them. Examine actual sound and ducking; automatic
processing is not proof of a good mix. Reconcile adjacent scenes and preserve the final musical tail.
"""),
    ({"sound","post"},
     """Select actual music for dramatic mood and continuity, not mandatory source-track identity.
Carry source music's staged function/density, dialogue support and release; unknown song is not silence.
Use existing themes with meaningful variants. Cue actual assets, entries, bridges, exits and musical
tails in EDIT; avoid doubling effective H3 impacts or restarting a theme at every generation boundary.
Purposeful quiet has a trigger/span/function. A fade alone does not establish a natural ending.
"""),
)

GENERAL_BASE = """You are the writer/director for the commissioned video. Use the supplied Brief,
reference observations and selected format/craft to develop the requested viewing experience.
The work may be UGC, conversation, interview, ranking, explainer, independent narration, screen
demonstration, motion graphics or a hybrid. Choose its actual organizing relationship and write
the requested owners. Preserve settled facts, identity, wording and useful existing material.
Use the project's requested document shape: do not impose short-drama source rows, 26-column
storyboards or a dramatic plot when this work does not need them. Keep supplied reference facts
distinct from interpretation and newly authored choices. Carry semantic events, picture, captions,
sound and handoffs through the deliverables. Describe what the audience will actually see/hear.
Writing and analysis stay in the current Agent; existing image and video choices remain in force. An upstream Kit example
does not select a new provider or account. Return the requested UTF-8 file bodies in the schema.
"""


def creative_mode(data):
    mode=data.get('creative_mode','drama')
    if mode not in {'drama','general'}:raise ValueError('creative_mode must be drama or general')
    return mode


def writer_instructions(data):
    roles={item['role'] for item in data['outputs']}
    if creative_mode(data)=='general':
        guidance=[]
        if roles & {'design','treatment','director','visual','storyboard'}:
            guidance.append('Choose a clear attitude, useful visual hierarchy and expressive motion. '
                            'Match picture, demonstration, performance and sound to the current argument or experience; '
                            'write actual scene/shot relationships and useful editable controls, not a compulsory drama template.')
        if 'copy' in roles:
            guidance.append('Write the commissioned spoken or displayed wording. Keep factual claims accurate; '
                            'separate narration, captions and independent screen labels by their role.')
        if 'h3_prompt' in roles:
            guidance.extend(text for selected,text in ROLE_GUIDANCE if selected=={'h3_prompt'})
        if roles & {'post','sound'}:
            guidance.append('Use actual supplied footage and sound to decide retained windows, voice/picture handoffs, '
                            'music development and cue timing. Keep authored meaning through actual output clocks. '
                            'Use the requested existing edit or native production format; observe rather than invent media results.')
        return GENERAL_BASE+'\n'+'\n'.join(guidance)
    return BASE+"\n"+"\n".join(text for selected,text in ROLE_GUIDANCE if roles & selected)

def writer_contract(data):
    text=writer_instructions(data)
    return {'writer_system':text,'writer_contract_sha256':hashlib.sha256(text.encode()).hexdigest()}

OUTPUT_SCHEMA = {"type":"object","properties":{
    "documents":{"type":"array","items":{"type":"object","properties":{
        "file":{"type":"string"},"role":{"type":"string"},"coverage":{"type":"string"},"markdown":{"type":"string"}},
        "required":["file","role","coverage","markdown"],"additionalProperties":False}},
    "unresolved":{"type":"array","items":{"type":"string"}}},
    "required":["documents","unresolved"],"additionalProperties":False}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_shot_table(path, skill):
    """Validate and return the canonical source-shot table record."""
    path = Path(path).resolve(strict=True)
    rows, headers = load_table(path)
    return {**record(path), "kind": "source-shot-analysis", "canonical": True,
            "columns": len(headers), "rows": len(rows),
            "text": path.read_text(encoding="utf-8-sig")}

def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)

def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def record(path):
    return {"file": str(Path(path).resolve()), "sha256": digest(path)}

def target(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Output must be a production-relative file: " + name)
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or resolved.is_relative_to(root / ".hypit-writing"):
        raise ValueError("Output leaves document owners: " + name)
    return resolved

def packet(path):
    data = read(path)
    if data.get("version") != 1:
        raise ValueError("Unsupported writing request")
    creative_mode(data)
    root = Path(data["project_root"]).resolve(strict=True)
    if not root.is_dir() or not all(isinstance(data.get(k), str) and data[k].strip()
                                  for k in ("scope", "batch", "task")):
        raise ValueError("Missing production, scope, batch or task")
    batch = data["batch"]
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in batch):
        raise ValueError("Batch ID must contain only letters, numbers, dash and underscore")
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("No requested creative document outputs")
    names = set()
    for item in outputs:
        name = item["file"]
        key = os.path.normcase(str(target(root, name)))
        if key in names or item.get("role") not in ROLES:
            raise ValueError("Duplicate output or unsupported creative role")
        names.add(key)
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("coverage", "instruction")):
            raise ValueError("Each output requires coverage and writing instruction")
    data["project_root"] = str(root)
    return data, root, root / ".hypit-writing", root / ".hypit-writing" / "batches" / batch

def model_inputs(rows):
    """Keep exact source rows; replace only an identical already-supplied context body."""
    result=copy.deepcopy(rows)
    packets={str(Path(r['file']).resolve()):r for r in result if r.get('kind')=='shot-execution-packet'}
    for row in result:
        if row.get('kind')!='actual-reference-plan':continue
        value=json.loads(row['text']);owner=value.get('packet',{})
        packet=packets.get(str(Path(owner.get('file','')).resolve()))
        if not packet or packet['sha256']!=owner.get('sha256'):continue
        body=json.loads(packet['text']);context=value.get('continuity',{}).get('context')
        if context is None or context!=body.get('continuity'):continue
        value['continuity']['context']={'supplied_body':{'file':packet['file'],'field':'continuity'},
                                       'instruction':'Use the full continuity body already supplied in this request.'}
        row['text']=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
        row['text_projection']='Exact duplicate continuity is supplied once in the identified shot-execution-packet; original file/hash remains the version authority.'
    return result


def freeze_units(data,root,skill):
    """One scoped author call for several prepared H3 blocks, without merging their labels."""
    units=data['execution_units']
    if not isinstance(units,list) or not units:raise ValueError('execution_units must contain actual prepared blocks')
    ids=[u.get('id') for u in units]
    if not all(isinstance(k,str) and k.strip() for k in ids) or len(set(ids))!=len(ids):raise ValueError('Execution units need distinct IDs')
    if {x['role'] for x in data['outputs']}!={'h3_prompt'}:raise ValueError('execution_units is for a batch of H3 prompts')
    expected={x['file'] for x in data['outputs']};claimed=[];rows=[];images=[];videos=[];baselines=[]
    for unit in units:
        names=unit.get('output_files',[])
        if not names or not set(names)<=expected:raise ValueError('Execution unit needs its exact output_files')
        claimed.extend(names)
        single={k:v for k,v in data.items() if k!='execution_units'}
        for key in ('execution_packet','reference_plan','source_shot_table','source_shot_context'):
            single.pop(key,None)
            if unit.get(key):single[key]=unit[key]
        single['outputs']=[x for x in data['outputs'] if x['file'] in names]
        if not single.get('reference_plan'):raise ValueError('Every batched H3 unit needs its actual reference plan')
        part=freeze_inputs(single,root,skill,compact=False)
        rows.extend(part['inputs']);images.extend(part['images']);videos.extend(part['videos']);baselines.extend(part['baselines'])
    if len(claimed)!=len(set(claimed)) or set(claimed)!=expected:raise ValueError('Each H3 output belongs to exactly one execution unit')
    def unique(items):
        seen={};ordered=[]
        for item in items:
            key=item['file']
            if key in seen:
                if item!=seen[key]:raise ValueError('Batched inputs disagree on the same file/version: '+key)
            else:seen[key]=item;ordered.append(item)
        return ordered
    return {'request':data,'inputs':model_inputs(unique(rows)),'images':unique(images),'videos':unique(videos),
            'baselines':unique(baselines),**writer_contract(data)}


def freeze_inputs(data, root, skill, *, compact=True):
    if data.get('execution_units'):return freeze_units(data,root,skill)
    rows = []
    source_catalogue = None
    roles = {item["role"] for item in data["outputs"]}
    execution_packet = None
    reference_plan = None
    if data.get("reference_plan"):
        from runninghub_h3 import check_reference_plan
        plan_path = (root / data["reference_plan"]).resolve(strict=True)
        reference_plan = check_reference_plan(plan_path)
        rows.append({**record(plan_path), "kind": "actual-reference-plan",
                     "text": plan_path.read_text(encoding="utf-8-sig")})
    packet_name = data.get("execution_packet") or (reference_plan["packet"]["file"] if reference_plan else None)
    if packet_name:
        from shot_packet import validate as packet_check
        packet_path = (root / packet_name).resolve(strict=True)
        execution_packet = packet_check(packet_path)
        if reference_plan and record(packet_path) != reference_plan["packet"]:
            raise ValueError("Writer reference assignment points to a different shot packet")
        if not roles <= {"h3_prompt", "asset_prompt", "post", "sound"}:
            raise ValueError("Scoped execution packet is for prompt compilation; full story development reads the full source")
        rows.append({**record(packet_path), "kind": "shot-execution-packet",
                     "text": packet_path.read_text(encoding="utf-8-sig")})
    if execution_packet:
        # Stateless calls need actual owner facts, not hashes or a fictitious remote memory.
        sliced={Path(row["artifact"]["file"]).resolve() for row in execution_packet.get("owner_slices",[])}
        explicit={(root/item["file"]).resolve() for item in data.get("inputs",[])}
        for owner in execution_packet.get("owners",[]) + execution_packet.get("dependencies",[]):
            path=verify_ref(owner)
            if path not in sliced|explicit and not any(row["file"] == str(path) for row in rows) and path.suffix.lower() in {".md",".txt",".json",".csv",".yaml",".yml"}:
                rows.append({**record(path),"kind":"needed-owner-context","text":path.read_text(encoding="utf-8-sig")})
    canonical = data.get("source_shot_table") or (
        execution_packet.get("source", {}).get("table", {}).get("file") if execution_packet else None)
    if canonical:
        table = (root / canonical).resolve(strict=True)
        context_name = data.get("source_shot_context") or (
            execution_packet.get("source", {}).get("context", {}).get("file") if execution_packet else None)
        context = (root / (context_name or str(table.with_name("SOURCE_CONTEXT.json")))).resolve(strict=True)
        source = compile_table(table, context)
        from check_content_conservation import source_contract
        source_contract(source, root, {r['id']: r for r in source['details']})
        source_key=hashlib.sha256((digest(table)+'\n'+digest(context)).encode()).hexdigest()
        snapshot = root / ".hypit-writing" / "sources" / source_key / "source.json"
        save(snapshot, source)
        source_catalogue = record(snapshot)
        if execution_packet:
            if execution_packet.get("source", {}).get("table") != record(table) or execution_packet["source"]["context"] != record(context):
                raise ValueError("Execution packet and writer refer to different canonical source versions")
            common=read(context).get('records',{})
            priorities={key:common[key] for key in ('selling_points','voice_profiles') if common.get(key)}
            if priorities and not any(row['file']==str(context) for row in rows):
                rows.append({**record(context),'kind':('source-directing-priorities' if 'voice_profiles' in priorities else 'source-selling-points'),
                             'projection':','.join('records.'+key for key in priorities),
                             'text':json.dumps(priorities,ensure_ascii=False)})
        else:
            rows.append(source_shot_table(table, skill))
            rows.append({**record(context), 'kind': 'source-common-events',
                         'text': context.read_text(encoding='utf-8-sig')})
        for dependency in ([] if execution_packet else source['source_shots']['dependencies']):
            path = Path(dependency['file'])
            if path.suffix.lower() not in {'.md', '.txt', '.json', '.csv', '.yaml', '.yml'}:
                raise ValueError('Source context dependencies must be readable text; media belongs in evidence/images')
            rows.append({**dependency, 'kind': 'source-linked-context',
                         'text': path.read_text(encoding='utf-8-sig')})
    elif creative_mode(data)!='general' and (data.get('source_kind') == 'reference' or any(
            item.get('kind') in {'source-observation', 'source-shot-analysis'} for item in data.get('inputs', []))):
        raise ValueError('Source-led writing requires source_shot_table; SCRIPT links are not a source master')
    for item in data.get("inputs", []):
        path = (root / item["file"]).resolve(strict=True)
        if any(row['file'] == str(path) for row in rows):
            continue
        if item.get("sha256") and item["sha256"] != digest(path):
            raise ValueError("Supplied input hash changed: " + str(path))
        text = path.read_text(encoding="utf-8-sig")
        rows.append({**record(path), "kind": item["kind"], "text": text})
    references = set(data.get("skill_references", []))
    if creative_mode(data)=='general':
        references.add('general/local-overrides.md')
        if roles & {'design','treatment','director','world','characters','visual','screenplay','storyboard'}:
            references.add('general/references/creation/brief.md')
        if roles & {'copy','screenplay','storyboard'}:
            references.add('general/references/creation/script-and-time.md')
        if roles & {'visual','asset_prompt'}:
            references.add('general/references/playbooks/craft/image-direction.md')
        if roles & {'post','sound'}:
            references.add('general/references/playbooks/craft/sound-mix.md')
            references.add('production/music-selection.md')
        if 'post' in roles:references.add('production/editing-and-finishing.md')
        formats={'talking-head','two-person-podcast','street-interview','ranking-listicle',
                 'presenter-led-explainer','narration-led-demo','short-drama'}
        if data.get('format') in formats:
            references.add('general/references/playbooks/formats/'+data['format']+'.md')
        if execution_packet:
            references.add('production/shot-execution-packet.md')
            if execution_packet.get('continuity'):references.add('production/spatial-continuity.md')
    else:
        if roles & {'design','treatment','world','characters','visual','screenplay','storyboard','director','sound'}:
            references.add("production/short-drama-production.md")
        if roles & {'design', 'visual', 'storyboard', 'director', 'h3_prompt'}:
            references.add("creation/audiovisual-orchestration.md")
        if roles & {'design', 'visual', 'storyboard', 'director', 'h3_prompt', 'post'}:
            references.add("creation/aesthetic-direction.md")
        if execution_packet:
            references.add("production/shot-execution-packet.md")
            if execution_packet.get('continuity'):
                references.add('production/spatial-continuity.md')
        else:
            if roles & {"design", "world", "characters", "visual", "screenplay"}:
                references.add("creation/drama-document-templates.md")
        if 'storyboard' in roles:
            references.add('production/spatial-continuity.md')
            template = skill / 'assets/target-storyboard-template.csv'
            template_text = template.read_text(encoding='utf-8-sig')
            from shot_tables import read_table
            for output in data['outputs']:
                current=target(root,output['file'])
                if output['role']=='storyboard' and current.exists():
                    _,current_headers=read_table(current,'target')
                    template_text+='\nExisting owner '+output['file']+' uses these headers:\n'+','.join(current_headers)+'\n'
            rows.append({**record(template),'kind':'target-storyboard-template','text':template_text})
        if roles & {"treatment", "screenplay"}:
            references.update({"creation/brief.md", "creation/adaptation-and-dialogue.md"})
        if 'sound' in roles:
            references.add('creation/sound-direction.md')
        if roles & {'design','characters','sound'}:
            references.add('playbooks/craft/voice-direction.md')
        if 'post' in roles and not data.get('videos'):
            references.add('production/post-design.md')
        if 'post' in roles:
            references.add('production/editing-and-finishing.md')
        if roles & {'post','sound'} or any(row.get('kind')=='actual-music-files-and-audition-clocks' for row in rows):
            references.add('production/music-selection.md')
        if roles & {'design','treatment','director','screenplay','storyboard','sound','post'}:
            references.add('creation/selling-points-and-score.md')
        if roles & {'storyboard','post'}:
            references.add('production/drama-editing.md')
    if "h3_prompt" in roles:
        mode = data.get("h3_mode")
        if mode not in {"Ref2VA", "T2VA", "I2VA", "FL2VA", "L2VA"}:
            raise ValueError("H3 writing requires the real selected h3_mode")
        references.update({"playbooks/craft/h3-prompts.md",
                           "playbooks/craft/h3-dense-direction.md"})
        if mode == "Ref2VA":
            references.update({"playbooks/craft/h3-prompts/ref-en.md",
                               "playbooks/craft/examples/director-dense-ref2va.txt"})
        else:
            references.add("playbooks/craft/h3-prompts/base-en.md")
    for name in sorted(references):
        path = (skill / "references" / name).resolve(strict=True)
        if not path.is_relative_to((skill / "references").resolve()):
            raise ValueError("Skill reference is outside references")
        rows.append({**record(path), "kind": "skill-contract", "text": path.read_text(encoding="utf-8-sig")})
    # Current outputs are baseline evidence, never silently overwritten.
    baselines = []
    for item in data["outputs"]:
        path = target(root, item["file"])
        baseline = {"file": str(path), "sha256": digest(path) if path.exists() else None}
        baselines.append(baseline)
        if path.exists():
            rows.append({**record(path), "kind": "current-target-baseline",
                         "text": path.read_text(encoding="utf-8-sig")})
    images = []
    image_names = list(data.get("images", []))
    if reference_plan:
        image_names.extend(row["asset"]["file"] for row in reference_plan["references"] if row["media"] == "image")
    for name in dict.fromkeys(image_names):
        path = (root / name).resolve(strict=True)
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("Images must be inspectable PNG/JPEG/WebP")
        images.append(record(path))
    videos=[]
    for item in data.get('videos',[]):
        item={'file':item} if isinstance(item,str) else dict(item)
        path=(root/item['file']).resolve(strict=True)
        if path.suffix.lower() not in {'.mp4','.webm','.mov'}:raise ValueError('Use actual supported video evidence')
        record_item={**record(path),'label':item.get('label',path.name)}
        if item.get('source'):
            source=dict(item['source']);source['file']=str((root/source['file']).resolve(strict=True));verify_ref(source)
            record_item.update(source=source,source_interval=item.get('source_interval'))
        videos.append(record_item)
    bundle = {"request": data, "inputs": model_inputs(rows) if compact else rows, "images": images, "videos":videos, "baselines": baselines,
              **writer_contract(data)}
    if source_catalogue:
        bundle['source_catalogue'] = source_catalogue
    return bundle

def parse_output(messages, bundle):
    result = None
    for message in reversed(messages):
        try:
            candidate = json.loads(message)
            if isinstance(candidate, dict) and "documents" in candidate:
                result = candidate
                break
        except ValueError:
            continue
    if not isinstance(result, dict) or set(result) != {"documents", "unresolved"}:
        raise ValueError("No complete structured writing response")
    expected = {item["file"]: item for item in bundle["request"]["outputs"]}
    received = {}
    if not isinstance(result["unresolved"], list) or not all(isinstance(x, str) for x in result["unresolved"]):
        raise ValueError("Invalid unresolved list")
    for item in result["documents"]:
        name = item.get("file")
        if name in received or name not in expected or item.get("role") != expected[name]["role"]:
            raise ValueError("Writer returned duplicate, unrequested or mismatched document")
        if item.get("coverage") != expected[name]["coverage"] or not isinstance(item.get("markdown"), str) or not item["markdown"].strip():
            raise ValueError("Empty or wrong-scope document")
        received[name] = item
    if set(received) != set(expected):
        raise ValueError("Writer omitted commissioned document outputs; do not auto retry")
    return result

def verify_ref(ref):
    if digest(ref["file"]) != ref["sha256"]:
        raise ValueError("Writing artifact changed: " + ref["file"])
    if ref.get('source') and digest(ref['source']['file'])!=ref['source']['sha256']:
        raise ValueError('Observed video source changed: '+ref['source']['file'])
    return Path(ref["file"])

def adopt(args):
    data, root, store, batch_dir = packet(args.packet)
    receipt_path = batch_dir / "receipt.json"
    receipt = read(receipt_path)
    bundle = read(verify_ref(receipt["bundle"]))
    if bundle["request"] != data:
        raise ValueError("Request changed since writing began")
    roles={r['role'] for r in data['outputs']}
    retain=bool(getattr(args,'retain_findings',False)) and roles <= {'post','sound','copy'}
    autonomous=bool(data.get('autonomous_finish')) and roles <= {'post','sound'}
    if receipt.get('unresolved') and not (retain or autonomous):
        raise ValueError('Unresolved creative questions remain; post/observation findings may be retained within the authorized finishing scope')
    result = read(verify_ref(receipt["response"]))
    assessment_path = Path(args.assessment) if args.assessment else batch_dir / "adoption.json"
    if not args.assessment:
        save(assessment_path, {"decision":"adopt", "documents":[{"file":x["file"], "basis":"Executor installs unchanged draft; artistic acceptance is separate"} for x in data["outputs"]]})
    assessment = read(assessment_path)
    rows = assessment.get("documents", [])
    if assessment.get("decision") != "adopt" or {r["file"] for r in rows} != {x["file"] for x in data["outputs"]}:
        raise ValueError("Actual adoption assessment must cover this batch's complete output set")
    if len(rows) != len(data["outputs"]) or not all(isinstance(r.get("basis"), str) and r["basis"].strip() for r in rows):
        raise ValueError("Missing per-document content assessment")
    owners = {item["file"]: item for item in result["documents"]}
    # Re-adopting exactly the same completed batch is idempotent.
    if receipt.get("status") == "adopted":
        for row in receipt["outputs"]:
            if digest(target(root, row["file"])) != row["draft"]["sha256"]:
                raise ValueError("Adopted owner changed; do not overwrite it")
    else:
        for row in bundle["inputs"] + bundle["images"] + bundle.get('videos',[]):
            if row.get("kind") in {"skill-contract", "target-storyboard-template"}:
                continue  # Preserve the actual frozen instruction text; documentation upgrades do not rewrite drafts.
            # An interrupted adoption may already have installed one of its own outputs.
            if receipt.get("status") == "adopting" and row.get("kind") == "current-target-baseline":
                continue
            verify_ref(row)
        drafts = {str(target(root, row["file"])): row["draft"]["sha256"] for row in receipt["outputs"]}
        for row in bundle["baselines"]:
            current = digest(row["file"]) if Path(row["file"]).exists() else None
            allowed = {row["sha256"]}
            if receipt.get("status") == "adopting":
                allowed.add(drafts[row["file"]])
            if current not in allowed:
                raise ValueError("Owner changed since writing began: " + row["file"])
    for row in receipt["outputs"]:
        draft = verify_ref(row["draft"])
        if draft.read_text(encoding="utf-8") != owners[row["file"]]["markdown"]:
            raise ValueError("Draft no longer equals original model output")
    if bundle.get('source_catalogue'):
        from source_shots import validate_projection, validate_target_table
        catalogue_path = verify_ref(bundle['source_catalogue'])
        source = read(catalogue_path)
        validate_projection(source, catalogue_path.parent)
        for row in receipt['outputs']:
            if row['role'] == 'storyboard':
                if Path(row['file']).suffix.lower() != '.csv':
                    raise ValueError('Source-led storyboard must use the detailed CSV master')
                validate_target_table(Path(row['draft']['file']), source)
    # Check all artifacts before replacing any owner. Backups support recovery of an interrupted adoption.
    receipt["status"] = "adopting"
    save(receipt_path, receipt)
    index_path = store / "writing.json"
    index = read(index_path) if index_path.exists() else {"version": 1, "project_root": str(root), "documents": []}
    for row in receipt["outputs"]:
        destination = target(root, row["file"])
        if destination.exists() and digest(destination) != row["draft"]["sha256"]:
            backup = target((batch_dir / "before").resolve(), row["file"])
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copyfile(destination, backup)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".hypit-writing-tmp")
        shutil.copyfile(row["draft"]["file"], temporary)
        os.replace(temporary, destination)
    receipt.update(status="adopted", assessment=record(assessment_path), findings_retained=list(receipt.get('unresolved',[])))
    save(receipt_path, receipt)
    for row in receipt["outputs"]:
        owner = target(root, row["file"])
        index["documents"] = [x for x in index["documents"] if Path(x["artifact"]["file"]).resolve() != owner]
        index["documents"].append({"role": row["role"], "artifact": record(owner),
                                  "origin": "openrouter_gemini" if receipt["route"].get("provider") == "openrouter" else "doubao",
                                  "receipt": record(receipt_path), "output_file": row["file"]})
    save(index_path, index)
    return {"status": "adopted", "writing_index": record(index_path), "documents": len(receipt["outputs"])}

def existing(args):
    data, root, store, _ = packet(args.packet)
    acceptance = read(args.acceptance)
    rows = acceptance.get("documents", [])
    if not rows or any(not r.get("basis") or not r.get("accepted_by") for r in rows):
        raise ValueError("Existing documents need actual acceptance evidence and accepting party")
    index_path = store / "writing.json"
    index = read(index_path) if index_path.exists() else {"version": 1, "project_root": str(root), "documents": []}
    for row in rows:
        owner = target(root, row["file"])
        if row.get("role") not in ROLES or row.get("sha256") != digest(owner):
            raise ValueError("Existing acceptance does not match the current document")
        index["documents"] = [x for x in index["documents"] if Path(x["artifact"]["file"]).resolve() != owner]
        index["documents"].append({"role": row["role"], "artifact": record(owner), "origin": "existing_accepted",
                                  "acceptance": record(args.acceptance)})
    save(index_path, index)
    return {"status": "existing_accepted", "writing_index": record(index_path)}


def response_schema(data):
    schema=copy.deepcopy(OUTPUT_SCHEMA)
    documents=schema["properties"]["documents"]
    documents.update(minItems=len(data["outputs"]),maxItems=len(data["outputs"]))
    for key in ("file","role","coverage"):
        documents["items"]["properties"][key]={"type":"string","enum":sorted({row[key] for row in data["outputs"]})}
    return schema


def messages(bundle):
    """Every call contains complete scoped evidence; no fictitious remote conversation state."""
    stable=[row for row in bundle["inputs"] if row["kind"]=="skill-contract"]
    current=[row for row in bundle["inputs"] if row["kind"]!="skill-contract"]
    system=bundle.get("writer_system", writer_instructions(bundle["request"]))+"\n"+"\n".join(Path(row["file"]).name+"\n"+row["text"] for row in stable)
    commission={k:v for k,v in bundle["request"].items() if k not in {"images","inputs","skill_references","project_root"}}
    supplied=[{"file":row["file"],"kind":row["kind"],"text":row["text"]} for row in current]
    content=[{"type":"text","text":json.dumps({"commission":commission,"inputs":supplied},ensure_ascii=False)}]
    labels={}
    for row in current:
        if row["kind"]=="actual-reference-plan":
            for reference in json.loads(row["text"])["references"]:
                if reference["media"]=="image":
                    labels.setdefault(str(Path(reference["asset"]["file"]).resolve()),[]).append(reference["label"])
    for row in bundle["images"]:
        path=verify_ref(row)
        content.append({"type":"text","text":"Target reference image "+
                        ", ".join(labels.get(str(path),[]))+" — "+path.name})
        content.append({"type":"image_url","image_url":{"url":"data:"+
            (mimetypes.guess_type(path.name)[0] or "image/png")+";base64,"+
            base64.b64encode(path.read_bytes()).decode()}})
    for row in bundle.get('videos',[]):
        path=verify_ref(row)
        content.append({'type':'text','text':'Actual 1x audiovisual evidence: '+row['label']+
                        '. Inspect the real performance, cuts and sound; descriptions are targets, not observations.'})
        content.append({'type':'video_url','video_url':{'url':'data:'+(mimetypes.guess_type(path.name)[0] or 'video/mp4')+
                                                       ';base64,'+base64.b64encode(path.read_bytes()).decode()}})
    return [{"role":"system","content":system},{"role":"user","content":content}]


def finish(data,root,store,batch_dir):
    raw_path=batch_dir/"api-response.json";raw=read(raw_path)
    receipt={"version":1,"status":"needs_revision",
        "route":{"model":MODEL,"provider":PROVIDER,"base_url":ENDPOINT,"upstream_provider":raw.get("provider")},
        "model_actual":raw.get("model"),"generation_id":raw.get("id"),"usage":raw.get("usage"),
        "provider_response":record(raw_path),"bundle":record(batch_dir/"bundle.json"),
        "artistic_status":"not_assessed","global_provider_switches":0}
    try:
        if raw.get("model")!=MODEL:raise ValueError("Writer returned a different model")
        choice=raw["choices"][0]
        if choice.get("finish_reason")!="stop":raise ValueError("Writing output is truncated/incomplete; preserve it and revise a bounded scope")
        value=json.loads(choice["message"]["content"])
        validate_shape(value,response_schema(data))
        bundle=read(batch_dir/"bundle.json")
        value=parse_output([json.dumps(value,ensure_ascii=False)],bundle)
        save(batch_dir/"response.json",value)
        artifacts=[]
        for row in value["documents"]:
            destination=target((batch_dir/"drafts").resolve(),row["file"])
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(row["markdown"],encoding="utf-8")
            artifacts.append({k:row[k] for k in ("file","role","coverage")}|{"draft":record(destination)})
        receipt.update(status="draft",response=record(batch_dir/"response.json"),outputs=artifacts,
                       unresolved=value["unresolved"])
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        receipt["error"]=str(exc) if isinstance(exc,ValueError) else "Incomplete provider response"
        save(batch_dir/"receipt.json",receipt)
        raise ValueError(receipt["error"]) from None
    save(batch_dir/"receipt.json",receipt)
    save(store/"state-gemini.json",{"version":1,"route":receipt["route"],"batch":data["batch"],
        "status":"draft","generation_id":raw.get("id"),"conversation_mode":"complete_scoped_requests"})
    return receipt


def run(args):
    """Prepare optional context for the current Agent; never submit a model request."""
    data,root,store,batch_dir=packet(args.packet)
    store.mkdir(parents=True,exist_ok=True);batch_dir.mkdir(parents=True,exist_ok=True)
    receipt_path=batch_dir/'receipt.json'
    if receipt_path.exists():
        previous=read(batch_dir/'bundle.json')
        if previous['request']!=data:raise ValueError('Batch ID already belongs to another request')
        return read(receipt_path)
    if (batch_dir/'api-response.json').exists():return finish(data,root,store,batch_dir)
    bundle=freeze_inputs(data,root,Path(__file__).resolve().parent.parent)
    save(batch_dir/'agent-context.json',bundle)
    return {'status':'ready_for_agent','context':str(batch_dir/'agent-context.json'),
            'outputs':data['outputs'],'external_model_calls':0,
            'next':'Current Agent reads context and writes the requested owner files directly; no API key or remote author.'}


def recover(args):
    data,root,store,batch_dir=packet(args.packet)
    if (batch_dir/"receipt.json").exists():return read(batch_dir/"receipt.json")
    if not (batch_dir/"api-response.json").exists():
        raise ValueError("No saved complete response; no inference was resubmitted")
    return finish(data,root,store,batch_dir)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["run","recover","inspect","adopt","register-existing"])
    p.add_argument("packet",type=Path);p.add_argument("--config");p.add_argument("--timeout",type=int)
    p.add_argument("--assessment",type=Path);p.add_argument("--acceptance",type=Path)
    p.add_argument('--retain-findings',action='store_true',help='Keep unresolved post/sound/observation findings while installing the complete returned file; never grants artistic acceptance')
    p.add_argument("--profile",help=argparse.SUPPRESS);p.add_argument("--codex",help=argparse.SUPPRESS)
    args=p.parse_args();lock=None
    try:
        data,root,store,batch_dir=packet(args.packet)
        if args.command=="inspect":
            result={"status":"idle","receipt":read(batch_dir/"receipt.json") if (batch_dir/"receipt.json").exists() else None}
        else:
            store.mkdir(parents=True,exist_ok=True);lock=store/"writer.lock"
            descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(descriptor,str(os.getpid()).encode());os.close(descriptor)
            if args.command=="run":result=run(args)
            elif args.command=="recover":result=recover(args)
            elif args.command=="adopt":result=adopt(args)
            elif args.command=="register-existing" and args.acceptance:result=existing(args)
            else:raise ValueError("register-existing requires --acceptance")
        print(json.dumps({k:v for k,v in result.items() if k not in {"bundle","response"}},ensure_ascii=False,indent=2))
        return 0 if result.get("status") not in {"needs_revision","failed"} else 1
    except (ValueError,OSError,RuntimeError,TimeoutError,KeyError,TypeError) as exc:
        print("DOCUMENT_WRITING_FAILED: "+(str(exc) if isinstance(exc,(ValueError,RuntimeError)) else "Local input/config unavailable"))
        return 1
    finally:
        if lock is not None and lock.exists() and lock.read_text()==str(os.getpid()):lock.unlink()


if __name__=="__main__":raise SystemExit(main())
