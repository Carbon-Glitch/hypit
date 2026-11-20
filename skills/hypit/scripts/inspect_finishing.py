"""Scan actual media for finishing candidates; never certify hearing, emotion or taste.

Decode the full source without changing it. Preserve raw diagnostics and source hashes.
Optional WhisperX-style segments locate speech gaps, which are not automatic trim points.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Expected a finite time/threshold')
    return float(value)


def ffmpeg_path(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ValueError('Explicit FFmpeg executable does not exist')
        return str(path)
    found = shutil.which('ffmpeg')
    if found:
        return found
    local = Path.home()/'.hypit/tools'/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
    if local.is_file():
        return str(local)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ValueError('Supply --ffmpeg or prepare an available FFmpeg; no automatic download') from exc


def metadata(path, executable, probe=None):
    candidate = Path(executable).with_name('ffprobe.exe' if Path(executable).suffix == '.exe' else 'ffprobe')
    probe = probe or shutil.which('ffprobe') or (str(candidate) if candidate.is_file() else None)
    if probe:
        result = subprocess.run([str(probe), '-v', 'error', '-show_format', '-show_streams',
                                 '-of', 'json', str(path)], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode:
            raise ValueError('ffprobe failed: ' + result.stderr[-1500:])
        raw = json.loads(result.stdout)
        duration = float(raw.get('format', {}).get('duration', 0))
        streams = raw.get('streams', [])
        details = [{k: row[k] for k in ('codec_type', 'codec_name', 'width', 'height', 'r_frame_rate',
                                       'sample_rate', 'channels', 'duration') if k in row} for row in streams]
    else:
        try:
            import av
        except ImportError as exc:
            raise ValueError('Metadata needs --ffprobe, sibling ffprobe, or installed PyAV') from exc
        with av.open(str(path)) as container:
            duration = container.duration / av.time_base if container.duration is not None else 0
            details = [{'codec_type': stream.type, 'codec_name': stream.codec_context.name}
                       for stream in container.streams if stream.type in {'video', 'audio'}]
        streams = details
    duration = finite(duration)
    if duration <= 0:
        raise ValueError('Actual media duration unavailable')
    flags = {kind: any(x.get('codec_type') == kind for x in streams) for kind in ('video', 'audio')}
    if not any(flags.values()):
        raise ValueError('No usable audio/video streams')
    return {'duration': duration, 'streams': flags, 'details': details}


def intervals(log, prefix, duration):
    tokens = re.findall(r'\b' + re.escape(prefix) + r'_(start|end):\s*(-?\d+(?:\.\d+)?)', log)
    spans = []
    start = None
    for kind, raw in tokens:
        value = max(0.0, min(float(raw), duration))
        if kind == 'start':
            start = value
        elif start is not None:
            if value > start:
                spans.append([start, value])
            start = None
    if start is not None and duration > start:
        spans.append([start, duration])
    return spans


def parse_diagnostics(log, duration):
    black = [[float(a), min(float(b), duration)] for a, b in
             re.findall(r'black_start:(\d+(?:\.\d+)?)\s+black_end:(\d+(?:\.\d+)?)', log)]
    loudness = None
    for raw in re.findall(r'\{\s*"input_i".*?\}', log, re.S):
        try:
            loudness = json.loads(raw)
        except json.JSONDecodeError:
            continue
    return {'silence_candidates': intervals(log, 'silence', duration),
            'black_candidates': black, 'freeze_candidates': intervals(log, 'freeze', duration),
            'loudness': loudness}


def speech_gaps(path, duration):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    segments = data.get('segments') if isinstance(data, dict) else data
    if not isinstance(segments, list):
        raise ValueError('Speech evidence must contain an actual segments list')
    spans = []
    for row in segments:
        if not isinstance(row, dict):
            raise ValueError('Invalid speech segment')
        start, end = finite(row.get('start')), finite(row.get('end'))
        if not 0 <= start < end <= duration + 0.05:
            raise ValueError('Speech times lie outside this actual media')
        spans.append((start, min(end, duration)))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    gaps, cursor = [], 0.0
    for start, end in merged:
        if start > cursor:
            gaps.append([cursor, start])
        cursor = end
    if cursor < duration:
        gaps.append([cursor, duration])
    return {'artifact': {'file': str(Path(path).resolve()), 'sha256': sha(path)},
            'speech_intervals': merged, 'no_speech_candidates': gaps,
            'limitation': 'User must supply timestamps of this exact cut; gaps are not dead time or heard dialogue evidence.'}


def inspect(path, output, *, executable=None, probe=None, speech=None, planned_duration=None,
            noise_db=-45.0, min_event=0.5):
    path, output = Path(path).resolve(), Path(output).resolve()
    if path == output or (speech and Path(speech).resolve() == output):
        raise ValueError('Diagnostic output must not overwrite media or speech evidence')
    source_hash = sha(path)
    binary = ffmpeg_path(executable)
    info = metadata(path, binary, probe)
    noise_db, min_event = finite(noise_db), finite(min_event)
    if min_event <= 0 or not -120 <= noise_db <= 0:
        raise ValueError('Invalid detector settings')
    version = subprocess.run([binary, '-version'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    command = [binary, '-hide_banner', '-nostdin', '-xerror', '-i', str(path)]
    if info['streams']['video']:
        command += ['-map', '0:v:0', '-vf', f'blackdetect=d={min_event},freezedetect=n=-60dB:d={min_event}']
    if info['streams']['audio']:
        # silencedetect measures before the throwaway loudnorm output. Source is never altered.
        command += ['-map', '0:a:0', '-af', f'silencedetect=n={noise_db}dB:d={min_event},loudnorm=print_format=json']
    command += ['-f', 'null', '-']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if sha(path) != source_hash:
        raise ValueError('Input changed during inspection; rescan current bytes')
    report = {'version': 1, 'input': {'file': str(path), 'sha256': source_hash}, 'metadata': info,
              'decode': {'status': 'ok' if result.returncode == 0 else 'failed', 'returncode': result.returncode},
              'detector_settings': {'noise_db': noise_db, 'min_event_seconds': min_event},
              'tool': {'ffmpeg': binary, 'version': version.stdout.splitlines()[0] if version.stdout else 'unavailable'},
              'command': command, 'measurements': parse_diagnostics(result.stderr, info['duration']),
              'raw_diagnostics': result.stderr,
              'inspection': 'Full-file decode and measurements; no normal-speed hearing, artistic pass or automatic trimming.'}
    if planned_duration is not None:
        planned = finite(planned_duration)
        if planned <= 0:
            raise ValueError('Planned duration must be positive')
        report['timing'] = {'planned': planned, 'actual': info['duration'], 'delta': info['duration'] - planned,
                            'delta_percent': (info['duration'] / planned - 1) * 100}
    if speech:
        report['speech'] = speech_gaps(speech, info['duration'])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    parser.add_argument('--speech', type=Path, help='Actual timed segments from this exact edited file')
    parser.add_argument('--planned-duration', type=float)
    parser.add_argument('--noise-db', type=float, default=-45.0, help='Diagnosis setting, not an acceptance threshold')
    parser.add_argument('--min-event', type=float, default=0.5, help='Detector minimum seconds; not a trim instruction')
    args = parser.parse_args()
    try:
        report = inspect(args.media, args.output, executable=args.ffmpeg, probe=args.ffprobe, speech=args.speech,
                         planned_duration=args.planned_duration, noise_db=args.noise_db, min_event=args.min_event)
    except (OSError, ValueError, KeyError) as exc:
        print('FINISHING_SCAN_FAILED: ' + str(exc))
        return 1
    print(json.dumps({'output': str(args.output.resolve()), 'decode': report['decode'],
                      'duration': report['metadata']['duration'], 'artistic_accepted': False}, ensure_ascii=False))
    return 0 if report['decode']['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
