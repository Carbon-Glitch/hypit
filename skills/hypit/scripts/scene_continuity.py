"""Carry observed scene state into shot packets, image selection and actual H3 requests.

Checks declarations and provenance, never certifies what pixels depict or artistic quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from check_request_bindings import file_record, read_json, require, text_value
from inspect_finishing import ffmpeg_path, metadata, sha

MARKER = '@continuity'
FIELD = '跨镜依赖与补拍风险'


def ref(path):
    path = Path(path).resolve()
    return {'file': str(path), 'sha256': sha(path)}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def facts(value, name):
    require(isinstance(value, dict), name+' must be a fact dictionary')
    result = {}
    for key, item in value.items():
        text_value(key, name+' key'); text_value(item, name+' value')
        require(not re.search(r'(?:^|\.)(?:screen_side|screen_x|frame_side|screen_position)$', key),
                'Screen projection belongs to camera.screen_positions, not persistent world facts')
        result[key] = item
    return result


def inspect_record(path):
    """Read an existing JSON review or its one continuity fence, not another review chain."""
    path = Path(path)
    text = path.read_text(encoding='utf-8-sig')
    try:
        value = json.loads(text)
    except ValueError:
        match = re.search(r'```continuity\s*\n(.*?)\n```', text, re.S)
        return json.loads(match.group(1)) if match else {}
    return value.get('continuity', value) if isinstance(value, dict) else {}


def checked_manifest(path):
    path = Path(path).resolve()
    value = read_json(path)
    require(value.get('kind') == 'continuity_frames', 'Not an actual continuity frame manifest')
    file_record(value['media'], path.parent, 'observed media')
    start, end = value['interval']
    require(0 <= start < end, 'Invalid adopted interval')
    require(value.get('frames'), 'Actual frame observations need readable frames')
    for frame in value['frames']:
        file_record(frame['asset'], path.parent, 'observed frame')
        require(start <= frame['time'] < end, 'Frame is outside the adopted interval, possibly a discarded tail')
    return value


def checked_observation(path):
    path = Path(path).resolve()
    value = inspect_record(path)
    require(value.get('kind') == 'continuity_observation', 'Predecessor needs an actual observed state')
    manifest_path = file_record(value['manifest'], path.parent, 'state frame manifest')
    manifest = checked_manifest(manifest_path)
    require(value['media'] == manifest['media'] and value['interval'] == manifest['interval'],
            'Observed state does not match its adopted media/interval')
    facts(value['facts'], 'observed state')
    require(set(value.get('fact_sources', {})) == set(value['facts']),
            'Every carried fact needs its actual observation source')
    if value.get('previous'):
        file_record(value['previous'], path.parent, 'inherited state owner')
    seen = set()
    for origin in value.get('fact_sources', {}).values():
        file_record(origin['observation_spec'], path.parent, 'actual observation statement')
        marker = (origin['manifest']['file'], origin['manifest']['sha256'])
        if marker not in seen:
            source = file_record(origin['manifest'], path.parent, 'inherited fact frame source')
            checked_manifest(source)
            seen.add(marker)
    return value


def capture(media, start, end, times, output, *, ffmpeg=None, ffprobe=None):
    media, output = Path(media).resolve(), Path(output).resolve()
    binary = ffmpeg_path(ffmpeg)
    info = metadata(media, binary, ffprobe)
    require(info['streams']['video'] and 0 <= start < end <= info['duration']+.001,
            'Capture actual video inside the adopted interval')
    require(times and all(start <= t < end for t in times), 'Capture times must be inside the adopted interval')
    manifest_path = output/'frames.json'
    if manifest_path.exists():
        value = checked_manifest(manifest_path)
        require(value['media'] == ref(media) and value['interval'] == [start, end]
                and [f['time'] for f in value['frames']] == times,
                'Existing observation scope changed; preserve it and use a new version')
        return value
    output.mkdir(parents=True, exist_ok=True)
    source = ref(media)
    frames = []
    for number, point in enumerate(times, 1):
        image = output/f'frame-{number:02}.png'
        require(not image.exists(), 'Frame exists without a manifest; preserve it and use a new version')
        result = subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                                 '-ss', str(point), '-i', str(media), '-frames:v', '1', str(image)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        require(result.returncode == 0 and image.is_file(), 'Cannot extract the actual adopted frame')
        frames.append({'id': f'F{number}', 'time': point, 'asset': ref(image)})
    require(ref(media) == source, 'Media changed during capture')
    value = {'version': 1, 'kind': 'continuity_frames', 'media': source, 'interval': [start, end],
             'frames': frames, 'pixel_semantics_verified': False}
    save(manifest_path, value)
    return value


def observe(spec_path, output):
    spec_path = Path(spec_path).resolve(); root = spec_path.parent
    spec = read_json(spec_path)
    manifest_path = file_record(spec['manifest'], root, 'actual viewed frames')
    manifest = checked_manifest(manifest_path)
    previous = None
    if spec.get('previous'):
        previous_path = file_record(spec['previous'], root, 'previous observed state')
        previous = checked_observation(previous_path)
        require(previous['scene'] == spec['scene'], 'Cannot inherit state from another scene')
    observed = facts(spec.get('observed_facts', {}), 'actual observed facts')
    require(observed and spec.get('observer'), 'Record who inspected which actual facts; do not copy planned exit as observation')
    evidence = spec.get('evidence', {})
    frame_ids = {f['id'] for f in manifest['frames']}
    require(set(evidence) == set(observed) and all(isinstance(ids, list) and ids and set(ids) <= frame_ids for ids in evidence.values()),
            'Every newly observed fact needs one or more actual frame IDs')
    inherited = dict(previous['facts']) if previous else {}
    inherited.update(observed)
    sources = dict(previous.get('fact_sources', {})) if previous else {}
    sources.update({key: {'manifest': ref(manifest_path), 'frames': evidence[key],
                         'observation_spec': ref(spec_path)} for key in observed})
    unknown = set(previous.get('unknown_keys', [])) if previous else set()
    unknown.difference_update(observed)
    unknown.update(spec.get('unknown_keys', []))
    value = {'version': 1, 'kind': 'continuity_observation', 'scene': text_value(spec['scene'], 'scene'),
             'shot': text_value(spec['shot'], 'observed shot'), 'media': manifest['media'],
             'interval': manifest['interval'], 'manifest': ref(manifest_path), 'facts': inherited,
             'observed_facts': observed, 'evidence': evidence, 'observer': spec['observer'],
             'fact_sources': sources,
             'unknown_keys': sorted(unknown), 'artistic_accepted': False,
             'limitation': 'Facts are supplied by actual frame inspection; code checks provenance, not pixel meaning'}
    if previous:
        value['previous'] = ref(previous_path)
    if spec.get('packet'):
        packet_path = file_record(spec['packet'], root, 'observed shot packet')
        from shot_packet import validate as packet_check
        packet = packet_check(packet_path)
        plan = next((r for r in packet.get('continuity', {}).get('shots', []) if r['shot'] == value['shot']), None)
        require(plan is not None and plan['scene'] == value['scene'], 'Observation is not a selected continuity shot')
        comparison = compare_observation(value, plan['planned_exit'])
        unobserved_changes = set(plan['planned_changes'])-set(observed)
        value['unknown_keys'] = sorted(set(value['unknown_keys']) | unobserved_changes)
        for key in unobserved_changes:
            comparison['findings'].append({'key': key, 'status': 'unknown',
                                           'expected': plan['planned_changes'][key], 'observed': None})
            comparison['status'] = 'needs_continuity_repair'
        value.update(packet=ref(packet_path), comparison=comparison, status=comparison['status'])
    save(output, value)
    return value


def row_context(row, external=None):
    text = row.get(FIELD, '')
    found = text.find(MARKER)
    embedded = None
    if found >= 0:
        embedded, _ = json.JSONDecoder().raw_decode(text[found+len(MARKER):].lstrip())
    require(not (embedded and external), 'Keep one continuity authority: row or literal legacy projection, not both')
    if external:
        basis = text_value(external.get('basis'), 'legacy continuity source quote')
        require(basis in '\n'.join(row.values()), 'Legacy projection must cite actual target-row wording')
    value = embedded or external
    if value is None:
        return None
    require(isinstance(value, dict), 'Continuity marker must contain a JSON object')
    require(value.get('scene') and isinstance(value.get('camera'), dict) and value['camera'].get('id')
            and value['camera'].get('view'), 'Continuity needs scene and actual camera/view')
    facts(value.get('entry', {}), 'required entry')
    facts(value.get('changes', {}), 'planned state changes')
    require(value.get('entry') or value.get('changes'), 'Track actual consequential facts, not an empty template')
    if value.get('reset'):
        require(value['reset'].get('kind') in {'time_jump', 'new_scene', 'authorized_transition'}
                and value['reset'].get('reason'), 'State reset needs a real editorial transition')
    return value


def shared_entry(selection,root,context,shot,all_rows):
    """Explicit invariant facts from accepted pixels, checked against the full target span."""
    keys=context.get('stable_keys',[])
    require(isinstance(keys,list) and len(keys)==len(set(keys)) and set(keys)<=set(context.get('entry',{})),
            'stable_keys must name distinct required entry facts')
    sources=selection.get('shared_state',{}).get(context['scene'],{})
    values={};dependencies=[]
    if not keys:return values,dependencies
    ids=[r['目标镜头ID'] for r in all_rows]
    predecessor=context.get('predecessor')
    require(shot in ids and predecessor in ids and ids.index(predecessor)<ids.index(shot),
            'Shared state needs the complete ordered target span including its logical predecessor')
    span=all_rows[ids.index(predecessor):ids.index(shot)+1]
    for row in span:
        other=row_context(row,selection.get('continuity',{}).get(row['目标镜头ID']))
        require(other is not None,'Shared-state span has an unclassified shot; keep the observed predecessor dependency')
        require(not other.get('reset'),'Shared facts cannot bypass a time/scene reset')
        require(not set(keys)&set(other.get('changes',{})),
                'A claimed stable fact changes in the target span; wait for the actual adopted state')
        require(all(other.get('entry',{}).get(k,context['entry'][k])==context['entry'][k] for k in keys),
                'Shared fact differs across target entries; preserve the actual state dependency')
    for key in keys:
        path=file_record(sources.get(key),root,'accepted shared-state evidence for '+key)
        record=inspect_record(path)
        require(record.get('accepted') is True and record.get('observer'),
                'Shared state needs an accepted actual image observation')
        file_record(record.get('asset'),path.parent,'observed shared-state image')
        require(record.get('state_facts',{}).get(key)==context['entry'][key] and key not in record.get('unseen_keys',[]),
                'Shared-state image did not verify the required fact')
        values[key]=context['entry'][key];dependencies.append(ref(path))
    return values,dependencies


def resolve(selection, root, rows, *, all_rows=None):
    """Mechanical state projection from current/legacy shot rows and observed adoption records."""
    external = selection.get('continuity', {})
    require(isinstance(external, dict), 'Legacy continuity projection must map shot IDs')
    selected_ids = {row['目标镜头ID'] for row in rows}
    require(set(external) <= selected_ids, 'Continuity projection refers to an unselected shot')
    adoptions = selection.get('adoptions', {})
    resolved, dependencies, internal = [], [], {}
    for row in rows:
        shot = row['目标镜头ID']; context = row_context(row, external.get(shot))
        if context is None:
            continue
        inherited, origin, unknown = {}, 'authored_initial_state', set()
        predecessor = context.get('predecessor')
        if predecessor and not context.get('reset'):
            if predecessor in internal:
                require(internal[predecessor]['scene'] == context['scene'], 'Internal predecessor is in another scene')
                inherited = dict(internal[predecessor]['planned_exit'])
                unknown = set(internal[predecessor].get('unknown_keys', []))
                origin = 'within_request_planned_transition'
            elif predecessor not in adoptions:
                shared,proof=shared_entry(selection,root,context,shot,all_rows or rows)
                required=set(context.get('entry',{}))|set(context.get('visible_keys',context.get('entry',{})))
                require(shared and required<=set(shared), 'Dependent shot must wait for its actual adopted predecessor state')
                inherited=shared;origin='accepted_unchanged_shared_state';dependencies.extend(proof)
            else:
                path = file_record(adoptions[predecessor], root, 'actual predecessor observation')
                actual = checked_observation(path)
                require(actual['shot'] == predecessor and actual['scene'] == context['scene'],
                        'Predecessor shot/scene does not match this continuation')
                required_keys = set(context.get('entry', {}))
                require(required_keys <= set(actual['facts']),
                        'Required predecessor state was not observed; inspect actual frames before continuing')
                require(not required_keys & set(actual.get('unknown_keys', [])), 'Required predecessor state is still unknown')
                inherited = dict(actual['facts']); origin = 'observed_adopted_predecessor'
                unknown = set(actual.get('unknown_keys', []))
                dependencies.append(ref(path))
        expected = dict(context.get('entry', {}))
        for key, value in expected.items():
            require(key not in inherited or inherited[key] == value,
                    f'Continuity conflict at {shot}: {key}; repair predecessor or legitimately revise the target, do not reset it')
        inherited.update(expected)
        visible = context.get('visible_keys', list(inherited))
        require(isinstance(visible, list) and set(visible) <= set(inherited), 'Visible state keys must resolve to known world facts')
        require(not set(visible) & unknown, 'Visible inherited state is still unknown; obtain an actual usable view')
        planned_exit = dict(inherited); planned_exit.update(context.get('changes', {}))
        record = {'shot': shot, 'scene': context['scene'], 'camera': context['camera'],
                  'entry': inherited, 'expected_entry': expected,
                  'required_entry': {key: inherited[key] for key in visible}, 'visible_keys': visible,
                  'planned_changes': context.get('changes', {}), 'planned_exit': planned_exit,
                  'predecessor': predecessor, 'state_origin': origin,
                  'unknown_keys': sorted(unknown-set(context.get('changes', {}))),
                  'reset': context.get('reset'), 'note': context.get('note', '')}
        internal[shot] = record; resolved.append(record)
    return {'version': 1, 'shots': resolved, 'dependencies': dependencies,
            'pixel_semantics_verified': False} if resolved else None


def check_references(spatial, references, root):
    if not spatial:
        return []
    shots = {r['shot']: r for r in spatial['shots']}
    first = spatial['shots'][0]['shot']
    result = []
    for item in references:
        review = inspect_record(file_record(item['review'], root, 'selected image inspection'))
        scope = item.get('continuity_shots', [first])
        require(scope and set(scope) <= set(shots), 'Reference state scope selects an unknown shot')
        layout_input = bool(set(item.get('roles', [])) & {'composition_reference', 'first_frame', 'last_frame'})
        if layout_input:
            require(isinstance(review.get('state_facts'), dict),
                    'Current layout image needs its existing review to declare visible state facts/unseen keys')
            required_keys = set().union(*(set(shots[shot]['required_entry']) for shot in scope))
            covered = set(review['state_facts']) | set(review.get('unseen_keys', []))
            require(required_keys <= covered,
                    'Inspect current layout pixels for required state keys; do not silently omit unknown props')
        if layout_input or review.get('state_facts'):
            actual = file_record(item['asset'], root, 'selected reference')
            require(file_record(review.get('asset'), root, 'inspected reference pixels') == actual,
                    'State facts must belong to the actual selected image')
        if not review.get('state_facts'):
            continue
        observed = facts(review['state_facts'], 'inspected reference facts')
        for shot in scope:
            entry = shots[shot]['entry']
            for key in observed.keys() & entry.keys():
                require(observed[key] == entry[key],
                        f'Stale/conflicting visible reference {item["id"]}: {key}; crop, repair or remove the image before upload')
        result.append({'binding': item['id'], 'asset': ref(actual), 'facts': observed, 'shots': scope})
    return result


def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def check_prompt(spatial, prompt):
    if not spatial:
        return {'status': 'not_applicable'}
    # Presence checks never claim that a sentence or generated pixels are semantically correct.
    body = norm(prompt)
    missing = []
    for shot in spatial['shots']:
        if norm(shot['camera']['view']) not in body:
            missing.append(shot['shot']+':camera_view')
        for phase, values in (('entry', shot['required_entry']), ('change', shot['planned_changes'])):
            for key, value in values.items():
                if norm(value) not in body:
                    missing.append(shot['shot']+':'+phase+':'+key)
    require(not missing, 'Required current state/transition did not reach actual H3 prompt: '+', '.join(missing))
    return {'status': 'carriers_present', 'pixel_semantics_verified': False,
            'limitation': 'Literal presence only; inspect polarity, camera projection and actual generated frames'}


def compare_observation(observation, expected, *, phase='exit'):
    observed = observation['facts']
    findings = []
    for key, value in expected.items():
        status = 'unknown' if key in observation.get('unknown_keys', []) or key not in observed else 'matched' if observed[key] == value else 'mismatch'
        findings.append({'key': key, 'expected': value, 'observed': observed.get(key), 'status': status})
    return {'phase': phase, 'findings': findings,
            'status': 'matched' if findings and all(r['status']=='matched' for r in findings) else 'needs_continuity_repair',
            'artistic_accepted': False}


def protect_events(segments, events):
    """Protect explicitly required, observed state-change intervals during finishing."""
    result = [dict(r) for r in segments]
    restored = []
    for event in events:
        if not (event.get('required') is True and event.get('kind') in {'state_change','action','reaction','reveal'}):
            continue
        start, end = event['start'], event['end']
        require(0 <= start < end, 'Invalid actual state-change interval')
        # Intervals are few; preserve each entire action even if a proposed cut skipped its middle.
        cursor = start
        for part in sorted(result, key=lambda r: r['start']):
            if part['end'] <= cursor or part['start'] >= end:
                continue
            if part['start'] > cursor:
                restored.append([cursor, min(part['start'], end)])
            cursor = max(cursor, min(end, part['end']))
        if cursor < end:
            restored.append([cursor, end])
    for start, end in restored:
        nearest = min(segments, key=lambda r: max(r['start']-end, start-r['end'], 0))
        result.append({'start': start, 'end': end, 'speed': nearest['speed'],
                       'reason': 'Preserve required observed state-change action', 'preserve': []})
    merged = []
    for row in sorted(result, key=lambda r: r['start']):
        if merged and row['start'] < merged[-1]['end']-1e-6:
            require(row['speed'] == merged[-1]['speed'], 'Overlapping protected actions need one consistent speed')
            merged[-1]['end'] = max(merged[-1]['end'], row['end'])
        elif merged and abs(row['start']-merged[-1]['end']) < 1e-6 and row['speed'] == merged[-1]['speed']:
            merged[-1]['end'] = row['end']
        else:
            merged.append(dict(row))
    return merged, restored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('capture'); p.add_argument('media'); p.add_argument('--start', type=float, required=True); p.add_argument('--end', type=float, required=True)
    p.add_argument('--times', required=True); p.add_argument('--output', required=True); p.add_argument('--ffmpeg'); p.add_argument('--ffprobe')
    p = sub.add_parser('observe'); p.add_argument('spec'); p.add_argument('--output', required=True)
    p = sub.add_parser('compare'); p.add_argument('observation'); p.add_argument('expected'); p.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'capture':
            value = capture(args.media, args.start, args.end, [float(t) for t in args.times.split(',')], args.output, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
        elif args.action == 'observe':
            value = observe(args.spec, args.output)
        else:
            value = compare_observation(checked_observation(args.observation), read_json(args.expected))
            save(args.output, value)
        print(json.dumps({'status': value.get('status', 'recorded'), 'artistic_accepted': False}, ensure_ascii=False))
        return 2 if value.get('status') == 'needs_continuity_repair' else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('CONTINUITY_FAILED: '+str(exc)); return 1


if __name__ == '__main__':
    raise SystemExit(main())
