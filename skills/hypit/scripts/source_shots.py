"""Mechanical source-table projection; no model calls or artistic judgments."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from check_request_bindings import file_record, object_value, read_json, require, text_value, unique_object, reject_constant

from shot_tables import read_table, field_value, expanded_fields, content_fields

INDEX = '制作贡献索引'
FAMILIES = {'plot', 'dialogue', 'shot_language', 'director_intent', 'audience_experience'}
DIMENSIONS = {'action', 'interaction', 'performance', 'camera', 'editing', 'dialogue', 'sound', 'look',
              'atmosphere', 'appearance', 'continuity', 'plot', 'director_intent', 'experience'}

def ref(path):
    path = Path(path).resolve()
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def clock(value):
    try:
        parts = [float(x) for x in str(value).strip().split(':')]
    except ValueError as exc:
        raise ValueError('Source time must be seconds or hh:mm:ss') from exc
    require(1 <= len(parts) <= 3 and all(math.isfinite(x) and x >= 0 for x in parts), 'Invalid source time')
    require(len(parts) == 1 or all(x < 60 for x in parts[1:]), 'Invalid source time components')
    return sum(x * 60 ** (len(parts)-i-1) for i, x in enumerate(parts))

def load_table(path):
    rows, headers = read_table(path, 'source')
    seen = set()
    for row in rows:
        sid = row['镜头ID'].strip()
        require(sid not in seen, 'Duplicate source shot ID'); seen.add(sid)
        start, end = clock(row['入点']), clock(row['出点'])
        require(start < end and ('时长' not in row or abs(clock(row['时长'])-(end-start)) <= .002), 'Source interval/duration mismatch')
    return rows, headers

def selection(row, fields, records):
    require(isinstance(fields, list) and bool(fields) and len(fields) == len(set(fields)), 'Missing/distinct source field pointers')
    require(all(isinstance(f,str) and f != INDEX for f in fields), 'Invalid source field pointer')
    result = []
    for field in fields:
        try:value = field_value(row,field)
        except KeyError:raise ValueError('Unknown source field pointer: '+field) from None
        for token in re.findall(r'@([A-Za-z0-9_.:-]+)', value):
            require(token in records, 'Unresolved common/event/EX record: ' + token)
            value += '\n@' + token + ': ' + json.dumps(records[token], ensure_ascii=False)
        result.append(field + ': ' + value)
    return '\n'.join(result)

def compile_table(table, context):
    table, context = Path(table).resolve(strict=True), Path(context).resolve(strict=True)
    rows, headers = load_table(table)
    meta = object_value(read_json(context), 'source context')
    require(meta.get('version') == 1, 'Unsupported source context version')
    records = object_value(meta.get('records', {}), 'source records')
    source = {'version': 3, 'baseline_kind': 'reference',
              'media': ref(file_record(meta.get('media'), context.parent, 'original media')),
              'review': ref(file_record(meta.get('review'), context.parent, 'actual source reading')),
              'source_shots': {'table': ref(table), 'context': ref(context), 'dependencies': [
                  ref(file_record(r, context.parent, 'linked source context')) for r in meta.get('dependencies', [])]},
              'details': [], 'inventories': {f: [] for f in sorted(FAMILIES)}, 'observed_absence': {}}
    all_details, all_obligations, all_entries = set(), set(), set()
    for row in rows:
        sid = row['镜头ID'].strip()
        try:
            index = object_value(json.loads(row[INDEX], object_pairs_hook=unique_object, parse_constant=reject_constant), 'row index')
        except json.JSONDecodeError as exc:
            raise ValueError(sid + ': 制作贡献索引 must contain JSON') from exc
        specs, entries = index.get('details'), index.get('inventories')
        require(isinstance(specs, list) and bool(specs) and isinstance(entries, list) and bool(entries),
                sid + ': each shot needs indexed contributions')
        local, conserved = set(), set()
        for spec in specs:
            ident = text_value(spec.get('id'), 'detail ID')
            require(ident not in all_details, 'Duplicate detail ID'); all_details.add(ident); local.add(ident)
            fields = spec.get('fields'); description = selection(row, fields, records)
            require(spec.get('dimension') in DIMENSIONS and spec.get('importance') in {'critical', 'supporting', 'incidental'},
                    'Unknown detail dimension/importance')
            require(all(type(spec.get(k)) is bool for k in ('temporal', 'requires_generation')), 'Explicit source temporal/generation flags required')
            raw = spec.get('obligations'); require(isinstance(raw, list) and bool(raw), 'Detail needs separate obligations')
            obligations = []
            for item in raw:
                oid = text_value(item.get('id'), 'obligation ID')
                require(oid not in all_obligations, 'Duplicate obligation ID'); all_obligations.add(oid)
                selected = item.get('fields'); observed = selection(row, selected, records); conserved.update(expanded_fields(row,selected))
                checks = item.get('checks')
                require(isinstance(checks, list) and bool(checks) and set(checks) <= {'visual', 'motion', 'audio'}
                        and len(checks) == len(set(checks)), 'Invalid obligation modalities')
                obligations.append({'id': oid, 'description': observed, 'checks': checks,
                                    'source_shot': sid, 'source_fields': selected})
            source['details'].append({'id': ident, 'event': spec.get('event', sid), 'dimension': spec['dimension'],
                'description': description, 'importance': spec['importance'], 'temporal': spec['temporal'],
                'requires_generation': spec['requires_generation'], 'start': clock(row['入点']), 'end': clock(row['出点']),
                'evidence': ref(table), 'source_shot': sid, 'source_fields': fields, 'obligations': obligations})
        for item in entries:
            family = item.get('family'); require(family in FAMILIES, 'Unknown contribution family')
            ident = text_value(item.get('id'), 'inventory ID')
            require(ident not in all_entries, 'Duplicate inventory ID'); all_entries.add(ident)
            ids = item.get('details'); require(isinstance(ids, list) and bool(ids) and set(ids) <= local, 'Inventory references unknown row detail')
            fields = item.get('fields'); description = selection(row, fields, records)
            entry = {'id': ident, 'details': ids, 'description': description, 'source_shot': sid, 'source_fields': fields}
            if family == 'director_intent': entry['basis'] = 'observed_interpretation'
            if family == 'dialogue':
                for key in ('text', 'speaker', 'language'): entry[key] = text_value(item.get(key), 'source dialogue.' + key)
                require(entry['text'] in row['逐字台词与文字依据'], 'Indexed dialogue differs from source table')
            source['inventories'][family].append(entry)
        shared = object_value(index.get('context_fields', {}), 'shared context classification')
        for field, reason in shared.items():
            text_value(reason, 'shared context reason'); selection(row, [field], records)
        core = {'入镜承接状态', '出镜承接状态', '叙事任务', '注意力转移路径', '主体动作阶段', '表情身体与反应延迟',
                '听者旁观者同步行为', '目标策略与潜台词', '关系权力与状态变化', '道具接触与转移', '逐字台词与文字依据',
                '声桥与声画同步', '画面文字与片名过程', '特效与时间处理', '知情差与揭示顺序', '观众体验展开',
                '切点触发与匹配', '节奏与停顿职责', '导演作用推断与备选解释', '保真义务与损失信号'}
        core.update({'叙事任务与知情变化','起终状态与连续性','运镜与注意路径','行动接触与物理过程',
                     '表演与同步反应','角色策略与关系变化','画面文字与特效过程','转场切点与节奏','导演作用与体验机制'})
        shared_fields=expanded_fields(row,shared)
        require(not (shared_fields & core), 'Dramatic process/experience fields belong to contribution evidence')
        substantive = content_fields(row,headers)
        require(substantive <= conserved | shared_fields, sid + ': unindexed observed source fields: ' + ', '.join(sorted(substantive-conserved-shared_fields)))
        for field in headers:
            if field != INDEX: selection(row, [field], records)
    for family, entries in source['inventories'].items():
        if not entries:
            source['observed_absence'][family] = ref(file_record(meta.get('observed_absence', {}).get(family), context.parent, 'observed absence: ' + family))
    scope = meta.get('source_interval')
    require(isinstance(scope, list) and len(scope) == 2, 'Source context needs full source_interval')
    require(clock(scope[0]) == clock(rows[0]['入点']) and clock(scope[1]) == clock(rows[-1]['出点']), 'Source table misses commissioned beginning/end')
    for previous, current in zip(rows, rows[1:]):
        require(abs(clock(previous['出点'])-clock(current['入点'])) <= .002, 'Source boundaries contain a gap or overlap')
    return source

def validate_projection(source, root):
    binding = object_value(source.get('source_shots'), 'canonical source binding')
    table = file_record(binding.get('table'), root, 'canonical source table')
    context = file_record(binding.get('context'), root, 'source context')
    require(source == compile_table(table, context), 'Source catalogue differs from canonical table; recompile, do not hand-edit')

def validate_target_table(path, source):
    rows, headers = read_table(path, 'target')
    expected = {o['id']: d['source_shot'] for d in source['details'] for o in d['obligations']}
    known_shots = {d['source_shot'] for d in source['details']}
    covered, seen = set(), set()
    def ids(value):
        return set() if value.strip().startswith('N/A:') else set(x.strip() for x in value.split(';') if x.strip())
    for row in rows:
        sid = row['目标镜头ID'].strip()
        require(sid not in seen, 'Duplicate target shot ID'); seen.add(sid)
        shot_ids, obligation_ids = ids(row['源镜头ID']), ids(row['源义务ID'])
        require(shot_ids <= known_shots and obligation_ids <= set(expected), 'Target storyboard invents source IDs')
        require(all(expected[o] in shot_ids for o in obligation_ids), 'Target obligation points to a different source shot')
        require(bool(obligation_ids) or not shot_ids and '新增' in row['源镜头ID'],
                'A source-derived target shot has no specific source contribution')
        covered.update(obligation_ids)
    require(covered == set(expected), 'Target storyboard omitted source obligations: ' + ', '.join(sorted(set(expected)-covered)))
    return {'shots': len(rows), 'source_obligations': len(covered)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table', type=Path); parser.add_argument('context', type=Path); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        source = compile_table(args.table, args.context)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'catalogue': str(args.output.resolve()), 'details': len(source['details']), 'artistic_acceptance': False})); return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print('SOURCE_SHOTS_FAILED: ' + str(exc)); return 1

if __name__ == '__main__': raise SystemExit(main())
