"""Apply an explicit local pacing edit and verify the resulting media."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from inspect_finishing import ffmpeg_path, metadata, sha
from dialogue_guard import transcribe, protect_segments, compare_lines, remap_interval, align_caption_lines, apply_speech_discards
from scene_continuity import protect_events


def finite(value, label, *, zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not zero):
        raise ValueError(label + ' must be a finite positive number')
    return value


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_plan(data, duration):
    if data.get('version') != 1 or not isinstance(data.get('segments'), list) or not data['segments']:
        raise ValueError('Plan requires version 1 and non-empty segments')
    rows, cursor = [], 0.0
    for index, row in enumerate(data['segments'], 1):
        start, end = finite(row.get('start'), 'segment start', zero=True), finite(row.get('end'), 'segment end')
        speed = finite(row.get('speed', 1), 'segment speed')
        if start < cursor - 0.001 or end <= start or end > duration + 0.05:
            raise ValueError('Segments must cover ordered intervals inside the actual input')
        if speed < 0.5 or speed > 2.0:
            raise ValueError('Speed must stay between 0.5x and 2.0x for this finish route')
        reason = str(row.get('reason', '')).strip()
        if speed != 1 and not reason:
            raise ValueError('Every retimed segment needs an observed editorial reason')
        rows.append({'start': start, 'end': end, 'speed': speed, 'reason': reason,
                     'preserve': row.get('preserve', [])})
        cursor = end
    return rows


def timeline_map(segments):
    result, cursor = [], 0.0
    for row in segments:
        end = cursor + (row['end'] - row['start']) / row['speed']
        result.append({'source_start': row['start'], 'source_end': row['end'],
                       'target_start': cursor, 'target_end': end, 'speed': row['speed']})
        cursor = end
    return result


def remap_anchors(anchors, mapping, duration):
    result = []
    for row in anchors:
        start, end = finite(row.get('start'), 'anchor start', zero=True), finite(row.get('end'), 'anchor end')
        if end < start or end > duration + 0.05:
            raise ValueError('Anchor lies outside the current input media')
        parts, retained = [], 0.0
        for segment in mapping:
            left, right = max(start, segment['source_start']), min(end, segment['source_end'])
            if right <= left:
                continue
            parts.append({'start': segment['target_start'] + (left - segment['source_start']) / segment['speed'],
                          'end': segment['target_start'] + (right - segment['source_start']) / segment['speed']})
            retained += right - left
        result.append({'source': row, 'target_intervals': parts,
                       'coverage': 'removed' if not parts else 'complete' if abs(retained - (end - start)) < 0.001 else 'partial'})
    return result


def speed_chain(speed):
    # atempo accepts a factor in [0.5, 100], but chains keep the common local edit explicit.
    factors = []
    value = speed
    while value > 2.0:
        factors.append(2.0)
        value /= 2.0
    while value < 0.5:
        factors.append(0.5)
        value /= 0.5
    factors.append(value)
    return ','.join('atempo=' + ('%.8g' % factor) for factor in factors)


def render(input_path, output_path, plan_path, *, ffmpeg=None, ffprobe=None, _repair_attempt=0):
    input_path, output_path, plan_path = map(Path, (input_path, output_path, plan_path))
    input_path, output_path, plan_path = input_path.resolve(), output_path.resolve(), plan_path.resolve()
    if input_path == output_path or plan_path == output_path:
        raise ValueError('Output must be separate from input and plan')
    if output_path.exists() or output_path.with_suffix(output_path.suffix + '.retime.json').exists():
        raise ValueError('Output exists; reuse it or choose a new version')
    source_hash = sha(input_path)
    binary = ffmpeg_path(ffmpeg)
    info = metadata(input_path, binary, ffprobe)
    plan = read(plan_path)
    segments = validate_plan(plan, info['duration'])
    speech = None
    protection = {'status': 'not_applicable', 'basis': 'No audio stream'}
    if info['streams']['audio']:
        if plan.get('dialogue_expected', True) is False and not plan.get('no_dialogue_basis'):
            raise ValueError('A no-dialogue shot needs its actual no_dialogue_basis, not a shortcut around speech checks')
        speech = transcribe(input_path, language=plan.get('language')) if plan.get('dialogue_expected', True) else None
        if speech:
            speech = apply_speech_discards(speech, plan.get('discarded_speech', []), plan_path.parent)
        segments, protection = protect_segments(segments, speech or {}, info['duration'],
                                                dialogue_expected=plan.get('dialogue_expected', True))
    segments, restored_events = protect_events(segments, plan.get('anchors', []))
    require_event_bounds = all(0 <= row['start'] < row['end'] <= info['duration']+.001 for row in segments)
    if not require_event_bounds:
        raise ValueError('Protected continuity event lies outside actual source media')
    mapping = timeline_map(segments)
    anchors = remap_anchors(plan.get('anchors', []), mapping, info['duration'])
    caption_rows = plan.get('captions', [])
    caption_status = {'status': 'not_requested'}
    if caption_rows:
        caption_rows, caption_status = align_caption_lines(caption_rows, speech or {})
    captions = [dict(row, **remap_interval(row['start'], row['end'], mapping)) for row in caption_rows]
    has_audio, has_video = info['streams']['audio'], info['streams']['video']
    filters_v, filters_a = [], []
    for index, row in enumerate(segments):
        start, end, speed = row['start'], row['end'], row['speed']
        if has_video:
            filters_v.append(f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=(PTS-STARTPTS)/{speed:.8f}[v{index}]")
        if has_audio:
            filters_a.append(f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,{speed_chain(speed)}[a{index}]")
    concat_inputs = ''.join((f'[v{i}]' if has_video else '') + (f'[a{i}]' if has_audio else '') for i in range(len(segments)))
    filters = ';'.join(filters_v + filters_a) + ';' + concat_inputs + f'concat=n={len(segments)}:v={int(has_video)}:a={int(has_audio)}' + ('[vout]' if has_video else '') + ('[aout]' if has_audio else '')
    command = [binary, '-hide_banner', '-nostdin', '-n', '-i', str(input_path), '-filter_complex', filters]
    if has_video:
        command += ['-map', '[vout]']
    if has_audio:
        command += ['-map', '[aout]']
    command += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-fps_mode', 'vfr'] if has_video else []
    command += ['-c:a', 'aac', '-b:a', '192k'] if has_audio else []
    command += ['-movflags', '+faststart', str(output_path)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError('FFmpeg retime failed: ' + result.stderr[-1800:])
    if sha(input_path) != source_hash:
        raise ValueError('Input changed during retime; output is not accepted')
    actual = metadata(output_path, binary, ffprobe)
    expected = sum((row['end'] - row['start']) / row['speed'] for row in segments)
    if abs(actual['duration'] - expected) > 0.15:
        raise ValueError('Rendered duration differs from planned retime')
    report = {'version': 1, 'input': {'file': str(input_path), 'sha256': source_hash},
              'plan': {'file': str(plan_path), 'sha256': sha(plan_path), 'segments': segments},
              'output': {'file': str(output_path), 'sha256': sha(output_path)},
              'actual': actual, 'expected_duration': expected,
              'timeline_map': mapping, 'remapped_anchors': anchors,
              'dialogue_protection': protection, 'mapped_captions': captions, 'caption_alignment': caption_status,
              'restored_state_change_intervals': restored_events,
              'reconform_required': ['subtitles', 'post audio cues', 'graphics/effects', 'downstream entry/exit and acceptance evidence'],
              'audio': {'preserve_pitch': True if has_audio else None,
                        'method': 'FFmpeg atempo; no pitch-shift filter', 'source_audio_retained': has_audio},
              'artistic_accepted': False,
              'inspection': 'Technical retime/conform verification only; editorial and emotional acceptance remain required.'}
    if speech:
        report['dialogue_source'] = speech
        observed = transcribe(output_path, language=plan.get('language'))
        report['dialogue_output_comparison'] = compare_lines(
            [{'id': str(i), 'text': row['text']} for i, row in enumerate(speech.get('segments', []))], observed)
        report['dialogue_output_evidence'] = observed
        full_native = len(segments) == 1 and segments[0]['start'] == 0 and abs(segments[0]['end']-info['duration']) < .001 and segments[0]['speed'] == 1
        if speech.get('status')=='ok' and observed.get('status')=='ok' and report['dialogue_output_comparison']['status'] != 'matched' and not _repair_attempt and not full_native and not plan.get('discarded_speech'):
            # A local repair only: keep the risky candidate and re-export complete original speech.
            risky = output_path.with_name(output_path.stem+'.speech-risk-'+sha(output_path)[:8]+output_path.suffix)
            if risky.exists():
                raise ValueError('Preserved repair candidate exists; reuse its record instead of overwriting')
            output_path.rename(risky)
            report['output'] = {'file': str(risky), 'sha256': sha(risky)}
            save(risky.with_suffix(risky.suffix+'.retime.json'), report)
            repaired_plan = dict(plan, segments=[{'start': 0, 'end': info['duration'], 'speed': 1,
                                                'reason': 'Automatic complete-speech recovery after output transcript mismatch'}])
            recovery = output_path.parent/'.hypit-dialogue'/('recovery-'+source_hash[:12]+'-'+hashlib.sha256(str(output_path).encode()).hexdigest()[:8]+'.json')
            save(recovery, repaired_plan)
            restored = render(input_path, output_path, recovery, ffmpeg=ffmpeg, ffprobe=ffprobe, _repair_attempt=1)
            restored['automatic_repair'] = {'original_plan': {'file': str(plan_path), 'sha256': sha(plan_path)},
                                           'preserved_candidate': str(risky), 'method': 'Retain complete native speech once; no generative API call'}
            save(output_path.with_suffix(output_path.suffix+'.retime.json'), restored)
            return restored
    report['status'] = 'needs_dialogue_review' if (
        report.get('dialogue_output_comparison', {}).get('status') == 'review_required'
        or report.get('caption_alignment', {}).get('status') == 'review_required') else 'rendered'
    save(output_path.with_suffix(output_path.suffix + '.retime.json'), report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = parser.parse_args()
    try:
        report = render(args.input, args.output, args.plan, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print('RETIME_FAILED: ' + str(exc))
        return 1
    print(json.dumps({'status': report['status'], 'output': report['output'], 'duration': report['actual']['duration'],
                      'preserve_pitch': report['audio']['preserve_pitch'], 'artistic_accepted': False}, ensure_ascii=False))
    return 2 if report['status'] == 'needs_dialogue_review' else 0


if __name__ == '__main__':
    raise SystemExit(main())
