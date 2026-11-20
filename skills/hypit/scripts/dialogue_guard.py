"""Blind local speech evidence, conservative edit protection, and export dialogue comparison."""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import unicodedata

from inspect_finishing import sha

_MODELS = {}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def ref(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def transcribe(media, *, model=None, cache=None, language=None):
    """Compatibility name: read existing timestamps only; no ASR model is loaded."""
    media=Path(media).resolve(strict=True);source=ref(media)
    sidecar=media.with_suffix(media.suffix+'.speech.json')
    if sidecar.is_file():
        data=read(sidecar)
        if data.get('input',{}).get('sha256')!=source['sha256']:
            raise ValueError('Provided speech timings belong to different media bytes')
        if data.get('status')!='ok' or not isinstance(data.get('segments'),list):
            raise ValueError('Speech sidecar needs status=ok and timed segments')
        return {**data,'input':source,'evidence_basis':'Existing timestamp sidecar; no new recognition or hearing'}
    return {'version':1,'status':'unavailable','input':source,'segments':[],
            'policy':'agent_measurement_fallback',
            'reason':'No provided word timing. Current Agent may inspect waveform/energy and retain chosen source windows; word boundaries remain unverified.'}


def merge(intervals):
    result = []
    for start, end in sorted(intervals):
        if not math.isfinite(start + end) or start < 0 or end <= start:
            raise ValueError('Invalid actual speech interval')
        if result and start <= result[-1][1] + 1e-6:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def protected_intervals(evidence, *, margin=.12):
    if evidence.get('status') != 'ok':
        return []
    duration = evidence['duration']
    spans = []
    for row in evidence['segments']:
        if not row.get('text', '').strip():
            continue
        # Low-confidence recognitions remain protected until inspected, never permission to cut them.
        words = [w for w in row.get('words', []) if w.get('word', '').strip() and w['end'] > w['start']]
        start = min(w['start'] for w in words) if words else row['start']
        end = max(w['end'] for w in words) if words else row['end']
        if end > start:
            left, right = max(0, start-margin), min(duration, end+margin)
            if right > left:
                spans.append([left, right])
    protected=merge(spans)
    for left,right in evidence.get('reviewed_speech_discards',{}).get('ranges',[]):
        protected=[part for a,b in protected for part in ([a,min(b,left)],[max(a,right),b]) if part[1]>part[0]
                   and not (part[0]>=left and part[1]<=right)]
    return merge(protected)


def apply_speech_discards(evidence, discards, root=None):
    """Exclude only locally reviewed extra speech from protection, never alter the blind cache."""
    if not discards:
        return evidence
    import copy
    if evidence.get('status') != 'ok':
        raise ValueError('Actual word evidence is needed before excluding generated speech')
    root=Path(root or '.').resolve();ranges=[];reviews=[]
    for row in discards:
        start,end=float(row['start']),float(row['end'])
        if not (math.isfinite(start+end) and 0<=start<end<=evidence['duration']+.001 and row.get('reason')):
            raise ValueError('Discarded speech needs an actual range and reason')
        record=row.get('review',{});path=(root/record.get('file','')).resolve()
        if not path.is_file() or record.get('sha256')!=sha(path):
            raise ValueError('Discarded speech needs unchanged actual-listening review evidence')
        review=read(path)
        if review.get('input')!=evidence['input']:
            raise ValueError('Speech discard review belongs to different source bytes')
        observed=review.get('discarded_speech',[])
        if not review.get('observer') or not any(abs(float(r['start'])-start)<.001 and abs(float(r['end'])-end)<.001
              and r.get('kind') in {'duplicate','unwanted','asr_false_positive'} and r.get('basis') for r in observed):
            raise ValueError('Speech removal must be observed as duplicate/unwanted/ASR false positive, not inferred from silence')
        ranges.append([start,end]);reviews.append(ref(path))
    result=copy.deepcopy(evidence);segments=[]
    for segment in evidence['segments']:
        words=segment.get('words') or []
        if not words:
            if any(a<=segment['start']+.025 and b>=segment['end']-.025 for a,b in ranges):continue
            if any(a<segment['end']-.025 and b>segment['start']+.025 for a,b in ranges):raise ValueError('Cannot partially discard unaligned speech')
            segments.append(segment);continue
        runs=[];kept=[]
        for word in words:
            removed=any(a<=word['start']+.025 and b>=word['end']-.025 for a,b in ranges)
            if not removed and any(a<word['end']-.025 and b>word['start']+.025 for a,b in ranges):
                raise ValueError('Reviewed removal cuts through an actual word')
            if not removed:kept.append(word)
            elif kept:runs.append(kept);kept=[]
        if kept:runs.append(kept)
        for kept in runs:
            segments.append(dict(segment,words=kept,text=''.join(w['word'] for w in kept),
                                 start=min(w['start'] for w in kept),end=max(w['end'] for w in kept)))
    result['segments']=segments;result['reviewed_speech_discards']={'ranges':ranges,'reviews':reviews}
    return result


def missing_intervals(required, kept):
    result = []
    kept = merge(kept)
    for start, end in required:
        cursor = start
        for left, right in kept:
            if right <= cursor or left >= end:
                continue
            if left > cursor:
                result.append([cursor, min(left, end)])
            cursor = max(cursor, min(right, end))
        if cursor < end-1e-6:
            result.append([cursor, end])
    return result


def protect_segments(segments, evidence, duration, *, dialogue_expected=True, margin=.12):
    original = [dict(row) for row in segments]
    if not dialogue_expected:
        return original, {'status': 'not_applicable', 'basis': 'Explicit no-dialogue shot decision'}
    required = protected_intervals(evidence, margin=margin)
    if not required:
        return original, {'status':'unverified_boundaries','evidence_status':evidence.get('status'),
                          'before':original,'reason':'Use current-Agent observations and local signal evidence; no automatic full-clip restoration or word-level claim'}
    missing = missing_intervals(required, [[r['start'], r['end']] for r in original])
    pieces = [dict(row) for row in original]
    for start, end in missing:
        nearest = min(original, key=lambda r: max(r['start']-end, start-r['end'], 0))
        pieces.append({'start': start, 'end': end, 'speed': nearest['speed'],
                       'reason': 'Restore native speech/breath boundary omitted by proposed cut', 'preserve': []})
    result = []
    for row in sorted(pieces, key=lambda r: r['start']):
        if result and abs(result[-1]['end']-row['start']) < 1e-6 and result[-1]['speed'] == row['speed']:
            result[-1]['end'] = row['end']
        else:
            result.append(dict(row))
    # Do not put a sudden speed boundary through a recognized syllable.
    words = [w for r in evidence['segments'] for w in r.get('words', [])]
    for left, right in zip(result, result[1:]):
        if left['speed'] != right['speed'] and any(w['start'] < right['start'] < w['end'] for w in words):
            return [{'start': 0.0, 'end': duration, 'speed': 1.0,
                     'reason': 'Preserve speech across unsafe speed boundary', 'preserve': []}], {
                         'status': 'protected_full_coverage', 'before': original,
                         'reason': 'Speed change fell inside an actual word; revise at a safe boundary'}
    return result, {'status': 'repaired' if missing else 'protected', 'margin_seconds': margin,
                    'protected_source_intervals': required, 'restored_source_intervals': missing,
                    'before': original}


def remap_interval(start, end, mapping):
    required = end-start
    retained, parts = 0.0, []
    for row in mapping:
        left, right = max(start, row['source_start']), min(end, row['source_end'])
        if right > left:
            retained += right-left
            parts.append({'start': row['target_start']+(left-row['source_start'])/row['speed'],
                          'end': row['target_start']+(right-row['source_start'])/row['speed']})
    if not parts or retained < required-1e-5:
        raise ValueError('Caption/dialogue interval is partly cut; do not display the full sentence over a fragment')
    return {'start': parts[0]['start'], 'end': parts[-1]['end']}


def normalize(text):
    value = unicodedata.normalize('NFKC', str(text))
    try:
        from opencc import OpenCC
        value = OpenCC('t2s').convert(value)
    except ImportError:
        pass
    return ''.join(char.lower() for char in value if char.isalnum())


def compare_lines(lines, evidence):
    texts = [normalize(row['text']) for row in lines]
    expected = ''.join(texts)
    actual = normalize(''.join(row.get('text', '') for row in evidence.get('segments', [])))
    matched, actual_matched = set(), set()
    for block in SequenceMatcher(None, expected, actual, autojunk=False).get_matching_blocks():
        matched.update(range(block.a, block.a+block.size))
        actual_matched.update(range(block.b, block.b+block.size))
    cursor, findings = 0, []
    for index, (line, text) in enumerate(zip(lines, texts), 1):
        missing = ''.join(char for offset, char in enumerate(text) if cursor+offset not in matched)
        status = 'matched' if text and not missing and evidence.get('status') == 'ok' else 'review_required'
        findings.append({'id': line.get('id', str(index)), 'expected_text': line['text'],
                         'status': status, 'unmatched_characters': missing,
                         'expected_interval': [line.get('start'), line.get('end')]})
        cursor += len(text)
    extra = ''.join(char for index, char in enumerate(actual) if index not in actual_matched)
    return {'status': 'matched' if findings and not extra and all(r['status']=='matched' for r in findings) else 'review_required',
            'lines': findings, 'blind_observed_text': actual,
            'unmatched_observed_characters': extra,
            'limitation': 'ASR mismatch can be recognition error, masking or missing speech; inspect locally before deciding. Match is not artistic acceptance.'}


def align_caption_lines(lines, evidence):
    """Derive caption timing from observed speech, never from Gemini's estimated scene clock."""
    observed, times = '', []
    for segment in evidence.get('segments', []):
        words = segment.get('words') or [{'word': segment.get('text', ''), 'start': segment['start'], 'end': segment['end']}]
        for word in words:
            text = normalize(word['word'])
            observed += text
            times.extend([(word['start'], word['end'])] * len(text))
    expected = ''.join(normalize(row['text']) for row in lines)
    positions = {}
    for block in SequenceMatcher(None, expected, observed, autojunk=False).get_matching_blocks():
        positions.update({block.a+i: block.b+i for i in range(block.size)})
    result, issues, cursor = [], [], 0
    for index, row in enumerate(lines):
        text = normalize(row['text'])
        matches = [positions.get(cursor+i) for i in range(len(text))]
        if not matches or any(value is None for value in matches) or evidence.get('status') != 'ok':
            issues.append({'id': row.get('id', str(index)), 'text': row['text'], 'status': 'timing_review_required'})
        else:
            result.append(dict(row, start=times[matches[0]][0], end=times[matches[-1]][1]))
        cursor += len(text)
    return result, {'status': 'aligned_estimate' if not issues else 'review_required', 'issues': issues,
                    'basis': 'Actual blind ASR word bounds; estimated, not phoneme-accurate forced alignment'}


def expected_lines(contexts):
    result = []
    for context in contexts:
        try:
            value = json.loads(context['content'])
        except (KeyError, TypeError, ValueError):
            continue
        values = value if isinstance(value, list) else value.get('captions', value.get('dialogue_lines', [])) if isinstance(value, dict) else []
        if isinstance(values, list):
            result.extend({'id': row.get('id', row.get('shot', 'line')+'-'+str(i)),
                           'text': row['text'], 'start': row.get('start'), 'end': row.get('end')}
                          for i, row in enumerate(values, 1) if isinstance(row, dict) and row.get('text'))
    return result


def audit_edit(plan_path, output, *, model=None, language=None):
    plan = read(plan_path)
    findings = []
    for clip in plan['clips']:
        groups = {}
        for row in clip['audio_segments']:
            media = Path(row.get('source_job', clip['job']))/'output-0.mp4'
            groups.setdefault(media, []).append([row['start'], row['end']])
        for media, kept in groups.items():
            evidence = transcribe(media, model=model, language=language)
            required = protected_intervals(evidence)
            missing = missing_intervals(required, kept)
            findings.append({'id': clip['id'], 'input': evidence['input'],
                             'status': 'speech_cut_risk' if missing else 'protected' if required else 'unknown',
                             'missing_source_intervals': missing,
                             'protected_source_intervals': required, 'retained_source_intervals': kept})
    report = {'version': 1, 'plan': ref(plan_path), 'findings': findings,
              'status': 'review_required' if any(r['status']!='protected' for r in findings) else 'protected',
              'artistic_accepted': False}
    save(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('transcribe', 'check-export'):
        p = sub.add_parser(name); p.add_argument('media', type=Path); p.add_argument('--output', required=True, type=Path)
        p.add_argument('--model'); p.add_argument('--expected', type=Path); p.add_argument('--language')
    p = sub.add_parser('check-edit'); p.add_argument('plan', type=Path); p.add_argument('--output', required=True, type=Path); p.add_argument('--model'); p.add_argument('--language')
    args = parser.parse_args()
    try:
        if args.action == 'check-edit':
            result = audit_edit(args.plan, args.output, model=args.model, language=args.language)
        else:
            result = transcribe(args.media, model=args.model, language=args.language)
            if args.action == 'check-export':
                if not args.expected:
                    raise ValueError('Export comparison requires current dialogue lines, not a claim that audio passed')
                result = {'input': result['input'], 'transcription': result,
                          'comparison': compare_lines(expected_lines([{'content': args.expected.read_text(encoding='utf-8-sig')}]), result)}
            save(args.output, result)
        status = result.get('comparison', result).get('status')
        print(json.dumps({'status': status, 'output': str(args.output.resolve()), 'artistic_accepted': False}, ensure_ascii=False))
        return 0 if status in {'ok', 'matched', 'protected'} else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('DIALOGUE_CHECK_FAILED: '+str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
