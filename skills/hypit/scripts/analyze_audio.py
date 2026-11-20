"""Local sound measurements for the current Agent, with historical receipt recovery.
Shared credential/transport helpers remain for the separately retained image fallback, not analysis.
"""
from __future__ import annotations
import argparse
import array
import base64
import csv
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import wave

from inspect_finishing import ffmpeg_path, metadata, sha

API = 'https://openrouter.ai/api/v1'
MODEL = 'google/gemini-3.8-flash'
STAGES = {'source', 'candidate', 'boundary', 'scene', 'final', 'stem'}
PROMPT = """分析附件的实际音轨，时间用附件内相对秒数，中文报告。
附件按1×解码并保留双声道；评价当前听感，剪辑/变速后的片段使用本次附件时钟。
文本、镜头和预期台词是待核对项。实际字词完整转录，不确定处标[听不清]。
区分heard、context_inference、uncertain；画面口型/可见接触留给视频观察，精确响度留给仪器测量。
按实际发生记录可重叠的对白、动作声、环境床、音乐与声桥事件。描述发声、重音、停顿、抢话、
呼吸、远近/混响/声场及接缝；音乐按进入、发展、转折、退出写可听配器/密度、对白让位和尾音。
有解释价值时联系具体声音说明期待、幽默、压力或余韵，区分推断与观众实际反馈。
按说话者在summary描述稳定口音/音区/音色/咬字/口癖，镜头只补本句变化；voice专项展开这些特征。
candidate/boundary/scene/final核对当前导演意图与实际效果、额外/缺失对白、声线漂移、累计等待、
音乐衔接与收尾。问题定位到真实区间，给出保留原声/后期补强/局部修复的听证理由。
附件边界上下文不足和音乐类别不清时记uncertain及已听范围。
shots逐个返回输入ID；assessments逐个核对audio_conditions的ID。输入为空则对应数组为空。
自主发现的问题写events、shots.issues或summary。按给定JSON结构返回。
"""
PRIOR_PROMPT_HASHES = {'bf396619d0cbf439909cdb2cb66f1ab4cb4554ee92c53d26b1b31949e6227985', '24ba3ac0efea52aa4686300f42f0806812ac2403f87759bf71ab05b48a5e834a', 'fab11cb6b2eeab44d3ee03d007f48e298be90ea80135ed3b20a0e8c2bd69a93f'}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def arr(item):
    return {'type': 'array', 'items': item}


STR = {'type': 'string'}
NUM = {'type': 'number'}
TEXTS = arr(STR)
EVENT = obj({'start': NUM, 'end': NUM,
    'category': {'type': 'string', 'enum': ['dialogue', 'delivery', 'music', 'ambience', 'foley', 'silence', 'bridge', 'defect']},
    'basis': {'type': 'string', 'enum': ['heard', 'context_inference', 'uncertain']},
    'speaker': STR, 'language': STR, 'text': STR, 'auditory_detail': STR,
    'interpretation': STR, 'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']}})
SHOT = obj({'id': STR, 'delivery': STR, 'synchronous_sounds': STR, 'ambience_space': STR,
    'music_silence': STR, 'bridges': STR, 'observations': TEXTS, 'interpretations': TEXTS,
    'unknowns': TEXTS, 'issues': TEXTS,
    'native_recommendation': {'type': 'string', 'enum': ['retain', 'augment_post', 'repair_h3', 'replace', 'unknown']},
    'recommendation_basis': STR})
ASSESSMENT = obj({'condition_id': STR, 'status': {'type': 'string', 'enum': ['observed', 'failed', 'unknown']},
    'start': NUM, 'end': NUM, 'observation': STR, 'limitations': STR})
SCHEMA = obj({'events': arr(EVENT), 'shots': arr(SHOT), 'assessments': arr(ASSESSMENT),
    'summary': obj({'observations': TEXTS, 'interpretations': TEXTS, 'unknowns': TEXTS,
                    'rhythm_findings': TEXTS, 'repair_priorities': TEXTS})})


def unit_schema(shot_ids, condition_ids):
    """Constrain the actual unit IDs before the paid request, including empty lists."""
    schema = copy.deepcopy(SCHEMA)
    for name, key, identifiers in (('shots', 'id', shot_ids), ('assessments', 'condition_id', condition_ids)):
        if len(identifiers) != len(set(identifiers)) or any(not isinstance(x, str) or not x for x in identifiers):
            raise ValueError('Requested audio IDs must be distinct nonempty strings')
        field = schema['properties'][name]
        field.update(minItems=len(identifiers), maxItems=len(identifiers))
        if identifiers:
            # SCHEMA shares STR objects among fields; replace this leaf rather than mutating aliases.
            field['items']['properties'][key] = {'type': 'string', 'enum': list(identifiers)}
    return schema


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def ref(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def default_config():
    return Path.home() / '.hypit/openrouter-audio/config.json'


def config(path=None):
    path = Path(path or default_config()).resolve()
    data = load(path) if path.is_file() else {'version': 1, 'model': MODEL}
    if data.get('model') != MODEL:
        raise ValueError('This integration is fixed to the user-selected ' + MODEL)
    data['_path'] = path
    return data


def credential(cfg):
    key = os.environ.get('OPENROUTER_API_KEY')
    if key:
        return key.strip()
    encrypted = cfg['_path'].parent / cfg.get('credential_file', 'credential.dpapi')
    if os.name != 'nt' or not encrypted.is_file():
        raise ValueError('No OpenRouter credential: configure local DPAPI or OPENROUTER_API_KEY')
    env = dict(os.environ, HYPIT_AUDIO_CREDENTIAL_FILE=str(encrypted.resolve()))
    # A parent PowerShell 7 module path prevents Windows PowerShell Security autoload.
    for name in list(env):
        if name.lower() == 'psmodulepath':
            del env[name]
    command = ('$s=ConvertTo-SecureString ((Get-Content -Raw -LiteralPath $env:HYPIT_AUDIO_CREDENTIAL_FILE).Trim()); '
               '$c=New-Object System.Management.Automation.PSCredential("hypit",$s); '
               '[Console]::Write($c.GetNetworkCredential().Password)')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            env=env, capture_output=True, text=True)
    if result.returncode or not result.stdout.strip():
        raise ValueError('Cannot decrypt user-bound OpenRouter credential')
    return result.stdout.strip()


def request(route, key=None, payload=None, timeout=180, *, title='Hypit Audio Inspection'):
    headers = {'Content-Type': 'application/json', 'X-OpenRouter-Title': title}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(API + route, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print provider bodies, headers, requests or credentials.
        raise RuntimeError('OpenRouter HTTP ' + str(exc.code) + '; credentials/quota/provider need inspection') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError('OpenRouter transport failure; submission may have completed, do not auto-resubmit') from None
    if not isinstance(value, dict) or 'error' in value:
        raise RuntimeError('OpenRouter returned an API error; no listening evidence created')
    return value


def doctor(cfg=None):
    return {'status':'ok','analysis_route':'current_agent_and_local_signal','requires_analysis_api_key':False}


def seconds(value):
    parts = [float(x) for x in str(value).split(':')]
    if not 1 <= len(parts) <= 3 or any(not math.isfinite(x) or x < 0 for x in parts):
        raise ValueError('Invalid timestamp')
    return sum(x * 60 ** (len(parts)-i-1) for i, x in enumerate(parts))


def shot_rows(path, duration):
    if not path:
        return []
    # Both source schemas and the final edit's three-column boundary view share these fields.
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader=csv.DictReader(handle)
        if not {'镜头ID','入点','出点'} <= set(reader.fieldnames or []):
            raise ValueError('Audio shot view needs 镜头ID, 入点, 出点')
        rows=list(reader)
    seen = set()
    for row in rows:
        sid = row['镜头ID']; start = seconds(row['入点']); end = seconds(row['出点'])
        if not sid or sid in seen or not 0 <= start < end <= duration + .05:
            raise ValueError('Invalid/duplicate source shot ID or media interval')
        seen.add(sid); row['_interval'] = [start, min(end, duration)]
    return rows


def units(duration, start=0, end=None, segment=120, overlap=2):
    end = duration if end is None else end
    if not all(math.isfinite(x) for x in (duration, start, end, segment, overlap)):
        raise ValueError('Non-finite media interval')
    if not 0 <= start < end <= duration + .001 or segment <= 0 or not 0 <= overlap < segment:
        raise ValueError('Invalid analysis interval/segment/overlap')
    result = []; cursor = start
    while cursor < end - .001:
        finish = min(cursor + segment, end)
        result.append([round(cursor, 6), round(finish, 6)])
        if finish >= end - .001:
            break
        cursor = finish - overlap
    return result


def extract(media, span, path, executable):
    args = [executable, '-hide_banner', '-v', 'error', '-y', '-i', str(media),
            '-ss', str(span[0]), '-t', str(span[1]-span[0]), '-map', '0:a:0', '-vn',
            '-ar', '24000', '-ac', '2', '-c:a', 'pcm_s16le', str(path)]
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise ValueError('Actual audio extraction failed; no model listening declared')
    with wave.open(str(path), 'rb') as handle:
        actual = handle.getnframes() / handle.getframerate()
        channels = handle.getnchannels()
    if abs(actual - (span[1]-span[0])) > .075 or channels != 2:
        raise ValueError('Extracted audio duration/channel mismatch')
    return {'file': str(path.resolve()), 'sha256': sha(path), 'duration': actual,
            'format': 'wav', 'sample_rate': 24000, 'channels': channels, 'speed': 1,
            'processing': 'first audio stream; original rate/gain; stereo PCM resample; no normalization/effects'}


def signal_anchors(path):
    """Measured amplitude candidates; no speaker/music/emotional judgments."""
    tracks = [[], []]; cursor = 0
    with wave.open(str(path), 'rb') as w:
        rate = w.getframerate(); step = max(1, int(rate * .05))
        duration = w.getnframes()/rate
        while raw := w.readframes(step):
            values = array.array('h', raw)
            if sys.byteorder != 'little': values.byteswap()
            for channel in range(2):
                samples = values[channel::2]
                rms = math.sqrt(sum(x*x for x in samples)/len(samples))/32768
                if rms > 10 ** (-55/20):
                    start, end = cursor/rate, min(duration, (cursor+len(samples))/rate)
                    if tracks[channel] and start-tracks[channel][-1][1] < .151:
                        tracks[channel][-1][1] = end
                    else: tracks[channel].append([start,end])
            cursor += len(values)//2
    return {'method': 'PCM RMS in 50ms windows above -55 dBFS; gaps under 150ms merged; diagnostic candidates only',
            'left_activity': tracks[0], 'right_activity': tracks[1]}


def signal_warnings(analysis, signal):
    activity = signal['left_activity'] + signal['right_activity']; warnings=[]
    for event in analysis['events']:
        if event['basis'] == 'heard' and event['category'] in {'dialogue','foley','music','delivery'}:
            if not any(a < event['end'] and b > event['start'] for a,b in activity):
                warnings.append({'event_interval':[event['start'],event['end']],
                    'reason':'Estimated heard-event time has no measured signal above diagnostic threshold; verify actual anchor, not an automatic content verdict.'})
    return warnings


def validate_shape(value, schema=SCHEMA):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError('Audio result has missing/extra JSON fields')
        for k, sub in schema['properties'].items():
            validate_shape(value[k], sub)
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError('Audio result expected array')
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', math.inf):
            raise ValueError('Audio result array does not match requested count')
        for item in value:
            validate_shape(item, schema['items'])
    elif kind == 'string':
        if not isinstance(value, str) or ('enum' in schema and value not in schema['enum']):
            raise ValueError('Audio result invalid string/enum')
    elif kind == 'number':
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Audio result invalid finite number')


def validate_analysis(value, duration, shot_ids, condition_ids):
    validate_shape(value)
    for row in value['events'] + value['assessments']:
        if not 0 <= row['start'] < row['end'] <= duration + .075:
            raise ValueError('Model event/condition timestamp outside actual uploaded audio')
    ids = [x['id'] for x in value['shots']]
    if len(ids) != len(set(ids)) or set(ids) != set(shot_ids):
        raise ValueError('Model omitted/invented a requested shot')
    ids = [x['condition_id'] for x in value['assessments']]
    if len(ids) != len(set(ids)) or set(ids) != set(condition_ids):
        raise ValueError('Model omitted/invented an audio condition')


def normalize_analysis(value, duration, shot_ids, condition_ids):
    """Preserve unexpected conditions separately; never invent or rename required IDs."""
    validate_shape(value)
    for row in value['events'] + value['assessments']:
        if not 0 <= row['start'] < row['end'] <= duration + .075:
            raise ValueError('Model event/condition timestamp outside actual uploaded audio')
    known = set(condition_ids)
    extras = [copy.deepcopy(row) for row in value['assessments'] if row['condition_id'] not in known]
    result = copy.deepcopy(value)
    result['assessments'] = [row for row in result['assessments'] if row['condition_id'] in known]
    validate_analysis(result, duration, shot_ids, condition_ids)
    return result, {'version': 1, 'unrequested_assessments': extras,
                    'evidence_kind': 'model_unsolicited_diagnostics',
                    'artistic_accepted': False,
                    'limitations': ['Extra model observations/inferences are not requested-condition verdicts; verify their content before adoption.']}


def input_context(paths):
    result = []
    for path in paths:
        path = Path(path).resolve(strict=True)
        result.append({'artifact': ref(path), 'content': path.read_text(encoding='utf-8-sig')})
    return result


def reusable_unit(output, source, span, context, schema):
    """A syntax-only contract upgrade must not charge for identical saved evidence."""
    for path in sorted(Path(output).glob('*/receipt.json')):
        saved = load(path)
        if saved.get('input') != source or saved.get('stage') != context['stage'] or saved.get('interval') != span:
            continue
        if saved.get('prompt_sha256') not in ({digest(PROMPT)} | PRIOR_PROMPT_HASHES):
            continue
        if saved.get('schema_sha256') not in {digest(SCHEMA), digest(schema)} or 'context' not in saved:
            continue
        previous = load(checked_ref(saved['context']))
        previous.pop('signal_anchors', None)
        if previous == context:
            return path
    return None


def observation_context(stage, offset, shots, conditions, contexts, mode, focus=None):
    """Keep expected words out of the independent audio observation payload."""
    if mode == 'blind':
        shots = [{'id': row['id'], 'interval': row['interval']} for row in shots]
        conditions, contexts = [], []
    result={'stage': stage, 'source_offset': offset, 'shots': shots,
            'audio_conditions': conditions, 'reference_only': contexts, 'observation_mode': mode}
    if focus is not None:
        if focus!='voice':raise ValueError('Unsupported audio inspection focus')
        result['inspection_focus']='voice'
    return result


def analyze(args, cfg=None):
    """Measure sound locally for the current Agent; no audio-understanding service."""
    from audio_signal import measure
    result=measure(args.media,args.output,start=getattr(args,'start',0),end=getattr(args,'end',None),
                   ffmpeg=getattr(args,'ffmpeg',None),ffprobe=getattr(args,'ffprobe',None))
    return {k:result[k] for k in ('status','duration','report','waveform','semantic_audio_verified','external_model_calls')}


def checked_ref(record):
    path = Path(record['file']).resolve(strict=True)
    if sha(path) != record['sha256']:
        raise ValueError('Audio evidence artifact bytes changed')
    return path


def recovery_payload(original):
    if original.get('status') != 'failed' or original.get('error') != 'Model omitted/invented an audio condition':
        raise ValueError('Only a complete response rejected for extra condition IDs is recoverable')
    checked_ref(original['input']); checked_ref(original['audio'])
    raw = load(checked_ref(original['response']))
    context = load(checked_ref(original['context']))
    if digest(context) != original['context_sha256']:
        raise ValueError('Recovery context bytes changed')
    if raw.get('id') != original.get('generation_id') or raw.get('model') != MODEL or original.get('model_actual') != MODEL:
        raise ValueError('Recovery provider/model receipt mismatch')
    if raw['choices'][0].get('finish_reason') != 'stop':
        raise ValueError('Truncated or incomplete audio reports cannot be recovered')
    value = json.loads(raw['choices'][0]['message']['content'])
    analysis, diagnostics = normalize_analysis(value, original['audio']['duration'],
        [row['id'] for row in context['shots']], [row['id'] for row in context['audio_conditions']])
    if not diagnostics['unrequested_assessments']:
        raise ValueError('No unexpected condition IDs to recover')
    return analysis, diagnostics


def recover_unit(path, output=None):
    """Make a derivative receipt; original failures/response/usage remain byte-identical."""
    path = Path(path).resolve()
    original = load(path)
    if original.get('status') == 'ok':
        verify_receipt(path, original['input'], original['interval'], original['stage'])
        return path
    analysis, diagnostics = recovery_payload(original)
    folder = Path(output).resolve() if output else path.parent / 'recovered-id-contract-v1'
    if folder == path.parent:
        raise ValueError('Recovery must preserve the original unit directory')
    target = folder / 'receipt.json'
    if target.exists():
        existing = load(target)
        if existing.get('normalization', {}).get('original_receipt') != ref(path):
            raise ValueError('Existing recovery belongs to different original evidence')
        verify_receipt(target, original['input'], original['interval'], original['stage'])
        return target
    folder.mkdir(parents=True, exist_ok=True)
    save(folder / 'analysis.json', analysis); save(folder / 'diagnostics.json', diagnostics)
    recovered = copy.deepcopy(original)
    recovered.pop('error', None)
    recovered.update(status='ok', analysis=ref(folder / 'analysis.json'), observer='OpenRouter/' + MODEL,
        evidence_kind='actual_audio_model_inspection', artistic_accepted=False,
        normalization={'version': 1, 'rule': 'separate-unrequested-assessments-v1',
                       'original_receipt': ref(path), 'diagnostics': ref(folder / 'diagnostics.json')})
    recovered['signal_warnings'] = signal_warnings(analysis, load(checked_ref(original['signal']))) if 'signal' in original else []
    save(target, recovered)
    verify_receipt(target, original['input'], original['interval'], original['stage'])
    return target


def recover(path, output=None):
    path = Path(path).resolve(); saved = load(path)
    if 'units' not in saved:
        result = recover_unit(path, output)
        return {'status': 'ok', 'receipt': ref(result), 'remote_calls': 0, 'artistic_accepted': False}
    result = copy.deepcopy(saved)
    result.update(units=[], calls_this_run=0, recovered_units=0, unrecovered_units=0, cache_hits=0,
                  artistic_accepted=False, recovery_source=ref(path), recovery_failures=[])
    for record in saved['units']:
        unit = checked_ref(record)
        try:
            recovered = recover_unit(unit)
            if recovered != unit: result['recovered_units'] += 1
            else: result['cache_hits'] += 1
            result['units'].append(ref(recovered))
        except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
            result['units'].append(record); result['unrecovered_units'] += 1
            result['recovery_failures'].append({'receipt': record, 'error': str(exc) if isinstance(exc, ValueError) else 'Evidence unavailable'})
    result['status'] = 'ok' if result['unrecovered_units'] == 0 else 'partial'
    result['technical_status'] = result['status']
    if result.get('stage') == 'final' and result.get('dialogue_verification', {}).get('status') != 'matched':
        result['status'] = 'needs_dialogue_review'
    result['failed_cached_units'] = result['unrecovered_units']
    recovered_ids = {load(record['file'])['signature'][:24] for record in result['units'] if load(record['file'])['status'] == 'ok'}
    result['limitations'] = [text for text in saved.get('limitations', []) if not (
        text.startswith('Audio unit failed: ') and any(identifier in text for identifier in recovered_ids))]
    result['limitations'].append('Recovered extra condition IDs into separate diagnostics without new listening or artistic acceptance.')
    # All paid provider calls count, including rejected responses; recovery is not a second charge.
    result['usage'] = [load(record['file']).get('usage') for record in result['units']]
    result['diagnostics'] = [load(record['file'])['normalization']['diagnostics'] for record in result['units']
                             if load(record['file']).get('normalization')]
    destination = Path(output).resolve() if output else path.parent / 'recovered-id-contract-v1' / 'report.json'
    if destination == path:
        raise ValueError('Recovery report must preserve the original report')
    save(destination, result)
    return {'status': result['status'], 'report': ref(destination), 'recovered_units': result['recovered_units'],
            'unrecovered_units': result['unrecovered_units'], 'remote_calls': 0, 'artistic_accepted': False}


def verify_receipt(path, media, span, stage=None):
    r = load(path)
    if r.get('version') != 1 or r.get('status') != 'ok' or r.get('evidence_kind') != 'actual_audio_model_inspection':
        raise ValueError('Audio receipt is not a successful actual inspection')
    if r.get('model_actual') != MODEL or r.get('model_requested') != MODEL:
        raise ValueError('Unexpected audio evidence model')
    if r['input']['sha256'] != media['sha256'] or abs(r['input']['duration']-media['duration']) > .001:
        raise ValueError('Audio inspection belongs to another media version')
    checked_ref(r['input'])
    if stage and r['stage'] != stage:
        raise ValueError('Audio inspection stage mismatch')
    if not r['interval'][0] <= span[0] < span[1] <= r['interval'][1] + .001:
        raise ValueError('Requested audio evidence range was not inspected')
    checked_ref(r['audio']); analysis = load(checked_ref(r['analysis'])); raw = load(checked_ref(r['response']))
    if 'context' in r and digest(load(checked_ref(r['context']))) != r['context_sha256']:
        raise ValueError('Audio context evidence was changed')
    if 'signal' in r: checked_ref(r['signal'])
    if r['audio'].get('speed') != 1 or abs(r['audio']['duration']-(r['interval'][1]-r['interval'][0])) > .075:
        raise ValueError('Audio evidence was retimed or duration mismatched')
    if raw.get('id') != r.get('generation_id') or raw.get('model') != MODEL or raw['choices'][0].get('finish_reason') != 'stop':
        raise ValueError('Audio provider receipt does not match analysis')
    if 'normalization' in r:
        normalization = r['normalization']
        if normalization.get('version') != 1 or normalization.get('rule') != 'separate-unrequested-assessments-v1':
            raise ValueError('Unsupported audio normalization rule')
        original = load(checked_ref(normalization['original_receipt']))
        expected, diagnostics = recovery_payload(original)
        if analysis != expected or load(checked_ref(normalization['diagnostics'])) != diagnostics:
            raise ValueError('Normalized audio analysis/diagnostics was edited')
        for key in ('signature', 'stage', 'input', 'interval', 'audio', 'context', 'response',
                    'context_sha256', 'generation_id', 'model_actual', 'model_requested', 'provider', 'usage'):
            if r.get(key) != original.get(key):
                raise ValueError('Normalized receipt differs from original provider evidence')
        if 'signal' in original and r.get('signal') != original['signal']:
            raise ValueError('Normalized signal evidence differs')
    elif json.loads(raw['choices'][0]['message']['content']) != analysis:
        raise ValueError('Audio analysis was edited after provider response')
    validate_shape(analysis)
    return r


def coverage(args):
    report_path = Path(args.report).resolve(); report = load(report_path)
    plan = load(args.plan); media = next((m for m in plan['media'] if m['id'] == args.media_id), None)
    if media is None:
        raise ValueError('Audio coverage target is absent from acceptance plan')
    target = dict(media['file'], duration=media['duration'])
    target['file'] = str((Path(args.plan).resolve().parent / target['file']).resolve()); checked_ref(target)
    if report['input']['sha256'] != target['sha256']:
        raise ValueError('Audio report is not this adopted/final media')
    allowed = {'candidate': {'single'}, 'boundary': {'boundary'}, 'scene': {'scene'}, 'final': {'scene', 'export'}}
    if args.pass_name not in allowed.get(report['stage'], set()) or args.pass_name not in media['passes']:
        raise ValueError('Audio evidence stage cannot certify requested acceptance pass')
    result = []
    seen = set()
    for reference in report['units']:
        path = checked_ref(reference); r = load(path)
        if r['status'] != 'ok':
            continue
        span = [max(media['interval'][0], r['interval'][0]), min(media['interval'][1], r['interval'][1])]
        if span[0] >= span[1]:
            continue
        if tuple(span) in seen:
            continue
        seen.add(tuple(span))
        verify_receipt(path, target, span, report['stage'])
        result.append({'media': args.media_id, 'pass': args.pass_name, 'checks': ['audio'], 'interval': span,
            'speed': 1, 'audio_inspection': ref(path),
            'evidence': 'Actual audio model inspection: '+MODEL+'; original-rate extracted audio; '+str(path)+
                        '; observe analysis.json events/unknowns; GPT did not personally hear playback.'})
    save(args.output, {'version': 1, 'coverage': result, 'artistic_accepted': False,
                       'dialogue_verification': report.get('dialogue_verification', {'status': 'unverified'}),
                       'limitations': report['limitations']})
    return {'coverage_rows': len(result), 'output': str(Path(args.output).resolve())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor'); d.add_argument('--output')
    r = sub.add_parser('recover'); r.add_argument('evidence'); r.add_argument('--output')
    a = sub.add_parser('analyze'); a.add_argument('media'); a.add_argument('--stage', choices=sorted(STAGES), required=True)
    a.add_argument('--output', required=True); a.add_argument('--shots'); a.add_argument('--context', action='append', default=[])
    a.add_argument('--conditions'); a.add_argument('--start', type=float, default=0); a.add_argument('--end', type=float)
    a.add_argument('--segment-seconds', type=float); a.add_argument('--overlap', type=float, default=2)
    a.add_argument('--shots-per-unit', type=int, default=8)
    a.add_argument('--ffmpeg'); a.add_argument('--ffprobe')
    a.add_argument('--observation-mode', choices=['blind', 'directed'], default='blind')
    a.add_argument('--focus', choices=['voice'], help='Scoped special-voice inspection; general old evidence does not satisfy this focus')
    a.add_argument('--dialogue-lines', help='Existing target captions/dialogue_lines JSON, compared offline and never fed as blind-hearing answers')
    a.add_argument('--language', help='Known actual speech language for local ASR, such as zh or en')
    c = sub.add_parser('coverage'); c.add_argument('report'); c.add_argument('--plan', required=True)
    c.add_argument('--media-id', required=True); c.add_argument('--pass', dest='pass_name', required=True,
                                                                choices=['single', 'boundary', 'scene', 'export'])
    c.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'recover':
            result = recover(args.evidence, args.output)
        elif args.command == 'coverage':
            result = coverage(args)
        elif args.command == 'doctor':
            result = {'status':'ok','analysis_route':'current_agent_and_local_signal','requires_analysis_api_key':False}
            if args.output: save(args.output, result)
        else:
            result = analyze(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        # Safe failure output; no traceback that could expose transport/request internals.
        print(json.dumps({'status': 'failed', 'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Local input/config unavailable'}, ensure_ascii=False))
        return 1
    return 0 if result.get('status', 'ok') in {'ok','measured'} else 1


if __name__ == '__main__':
    sys.exit(main())
