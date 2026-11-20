"""OpenRouter image fallback after a failed Codex imagegen call; one paid attempt per input set."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import time

from PIL import Image
from analyze_audio import config, credential, request as api_request

MODEL = 'google/gemini-nano-banana-2.1'
RESOLUTIONS = {'1K', '2K', '4K'}
RATIOS = {'1:1', '1:4', '1:8', '2:3', '3:2', '3:4', '4:1', '4:3', '4:5',
          '5:4', '8:1', '9:16', '16:9', '21:9'}
FAILURES = {'tool_error', 'unavailable', 'timeout', 'invalid_output'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def image_info(path):
    with Image.open(path) as picture:
        picture.load()
        alpha = picture.convert('RGBA').getchannel('A')
        return {'width': picture.width, 'height': picture.height, 'format': picture.format,
                'has_transparency': alpha.getextrema()[0] < 255}


def freeze(path, *, smoke=False):
    data = read(path)
    if data.get('version') != 1:
        raise ValueError('Unsupported image fallback request')
    root = Path(data.get('project_root', Path(path).resolve().parent)).resolve(strict=True)
    asset_id = data.get('asset_id', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', asset_id):
        raise ValueError('Use a stable asset ID, such as CHR-01-look-v1')
    failure = data.get('builtin_failure', {})
    if not smoke and (failure.get('kind') not in FAILURES or not failure.get('detail', '').strip()):
        raise ValueError('Fallback needs an actual built-in tool failure; do not switch a successful call')
    prompt = (root / data['prompt_file']).resolve(strict=True)
    text = prompt.read_text(encoding='utf-8-sig')
    if not text.strip():
        raise ValueError('The original authored prompt is empty')
    output_name = Path(data['output'])
    output = (root / output_name).resolve()
    if output_name.is_absolute() or not output.is_relative_to(root) or output.suffix.lower() != '.png':
        raise ValueError('Output must be a project-relative versioned PNG path')
    resolution = data.get('resolution', '2K')
    ratio = data.get('aspect_ratio', '1:1')
    if resolution not in RESOLUTIONS or ratio not in RATIOS:
        raise ValueError('Unsupported resolution or aspect ratio for the selected model')
    transparent = data.get('transparent_background', False)
    if not isinstance(transparent, bool):
        raise ValueError('transparent_background must be a boolean')
    references = []
    for item in data.get('references', []):
        source = (root / item['file']).resolve(strict=True)
        role = item.get('role', '').strip()
        if not role:
            raise ValueError('Each reference needs its actual identity/style/layout/edit-target duty')
        info = image_info(source)
        if info['format'] not in {'PNG', 'JPEG', 'WEBP'}:
            raise ValueError('Use real PNG/JPEG/WebP reference files')
        current = record(source)
        if item.get('sha256') and item['sha256'] != current['sha256']:
            raise ValueError('A supplied reference changed')
        references.append({**current, 'role': role, **info})
    if len(references) > 14:
        raise ValueError('Nano Banana 2.1 supports at most 14 reference images')
    bundle = {'version': 1, 'model': MODEL, 'asset_id': asset_id,
              'prompt': {**record(prompt), 'text': text}, 'references': references,
              'resolution': resolution, 'aspect_ratio': ratio, 'output': str(output),
              'transparent_background': transparent,
              'trigger': {'kind': 'integration_smoke_test'} if smoke else failure}
    fingerprint = hashlib.sha256(json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    folder = root / '.hypit-images' / asset_id / fingerprint[:20]
    return bundle, folder


def payload(bundle):
    prompt = bundle['prompt']['text']
    references = []
    roles = []
    for index, item in enumerate(bundle['references'], 1):
        path = Path(item['file'])
        if sha(path) != item['sha256']:
            raise ValueError('Reference changed before submission')
        mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[item['format']]
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        references.append({'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + encoded}})
        roles.append('Image ' + str(index) + ': ' + item['role'])
    if roles:
        prompt += '\n\nReference image duties (same order as attachments):\n' + '\n'.join(roles)
    if bundle['transparent_background']:
        prompt += '\nOutput requires a genuinely transparent background; preserve existing transparency.'
    result = {'model': MODEL, 'prompt': prompt, 'resolution': bundle['resolution'],
              'aspect_ratio': bundle['aspect_ratio'], 'n': 1}
    if references:
        result['input_references'] = references
    return result


def doctor(config_path=None):
    models = api_request('/images/models').get('data', [])
    model = next((item for item in models if item.get('id') == MODEL), None)
    if not model or 'image' not in model.get('architecture', {}).get('output_modalities', []):
        raise ValueError('Exact selected image model is not currently available')
    endpoints = api_request('/images/models/' + MODEL + '/endpoints').get('endpoints', [])
    supports = [item for item in endpoints if '2K' in item.get('supported_parameters', {}).get('resolution', {}).get('values', [])
                and item.get('supported_parameters', {}).get('input_references', {}).get('max', 0) >= 14]
    if not supports:
        raise ValueError('No current endpoint supports the selected resolution/reference workflow')
    api_request('/key', credential(config(config_path)))
    return {'model': MODEL, 'credential_verified': True, 'default_resolution': '2K',
            'reference_limit': 14, 'pricing': [item.get('pricing', []) for item in supports],
            'image_generation_calls': 0}


def finish(bundle, folder):
    raw = read(folder / 'api-response.json')
    state = read(folder / 'receipt.json')
    state.update(generation_id=raw.get('id'), usage=raw.get('usage'), response=record(folder / 'api-response.json'))
    images = raw.get('data') or []
    if raw.get('model') and raw['model'] != MODEL:
        state['status'] = 'wrong_model'
        save(folder / 'receipt.json', state)
        raise ValueError('Response model differs from the selected image model')
    if len(images) != 1 or not images[0].get('b64_json'):
        state['status'] = 'no_usable_image'
        save(folder / 'receipt.json', state)
        raise ValueError('No usable returned image; response preserved, do not regenerate blindly')
    candidate = folder / 'candidate.png'
    try:
        content = base64.b64decode(images[0]['b64_json'], validate=True)
        with Image.open(io.BytesIO(content)) as picture:
            picture.load()
            if picture.format not in {'PNG', 'JPEG', 'WEBP'}:
                raise ValueError('Unsupported returned image format')
            if not candidate.exists():
                picture.save(candidate, format='PNG')
        info = image_info(candidate)
    except (ValueError, OSError) as exc:
        state['status'] = 'invalid_returned_image'
        save(folder / 'receipt.json', state)
        raise ValueError('Returned image cannot be decoded; preserve response for recovery') from exc
    minimum = {'1K': 1024, '2K': 2048, '4K': 4096}[bundle['resolution']]
    issues = []
    if max(info['width'], info['height']) < minimum:
        issues.append('returned_resolution_below_requested_tier')
    width, height = (int(value) for value in bundle['aspect_ratio'].split(':'))
    if abs((info['width'] / info['height']) / (width / height) - 1) > 0.03:
        issues.append('returned_aspect_ratio_mismatch')
    if bundle['transparent_background'] and not info['has_transparency']:
        issues.append('transparent_background_not_delivered')
    state.update(candidate=record(candidate), image=info, issues=issues,
                 status='needs_local_repair' if issues else 'generated_needs_visual_review',
                 artistic_accepted=False)
    # Never replace an accepted or concurrently edited asset.
    output = Path(bundle['output'])
    if not issues:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            if sha(output) != sha(candidate):
                save(folder / 'receipt.json', state)
                raise ValueError('Destination has changed; keep candidate and choose a sibling version')
        else:
            with output.open('xb') as handle:
                handle.write(candidate.read_bytes())
        state['output'] = record(output)
    save(folder / 'receipt.json', state)
    return {**state, 'receipt_file': str(folder / 'receipt.json')}


def run(path, *, config_path=None, timeout=180, smoke=False, recover=False):
    bundle, folder = freeze(path, smoke=smoke)
    receipt = folder / 'receipt.json'
    if receipt.exists():
        saved = read(folder / 'bundle.json')
        if saved != bundle:
            raise ValueError('Stored input bundle changed')
        if (folder / 'api-response.json').exists():
            return finish(bundle, folder)
        raise ValueError('Submission outcome uncertain/already attempted; do not automatically rebill')
    if recover:
        raise ValueError('No saved response to recover; recovery never submits')
    if Path(bundle['output']).exists():
        raise ValueError('Output already exists; reuse it or choose a sibling version before submission')
    request = payload(bundle)
    key = credential(config(config_path))
    save(folder / 'bundle.json', bundle)
    save(receipt, {'version': 1, 'status': 'submitted', 'model': MODEL,
                   'asset_id': bundle['asset_id'], 'trigger': bundle['trigger'],
                   'submitted_at_unix': time.time(), 'artistic_accepted': False})
    try:
        raw = api_request('/images', key, request, timeout=timeout, title='Hypit Image Fallback')
    except RuntimeError:
        state = read(receipt)
        state['status'] = 'submission_uncertain_or_rejected'
        save(receipt, state)
        raise RuntimeError('Image API request failed; receipt retained, no automatic second paid attempt') from None
    save(folder / 'api-response.json', raw)
    return finish(bundle, folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['doctor', 'inspect', 'run', 'recover'])
    parser.add_argument('request_file', nargs='?', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--smoke', action='store_true', help='Explicit integration test, not a fabricated built-in failure')
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            result = doctor(args.config)
        elif args.action == 'inspect':
            bundle, folder = freeze(args.request_file, smoke=args.smoke)
            result = {'model': MODEL, 'resolution': bundle['resolution'], 'reference_count': len(bundle['references']),
                      'output': bundle['output'], 'job': str(folder), 'image_generation_calls': 0}
        else:
            result = run(args.request_file, config_path=args.config, timeout=args.timeout,
                         smoke=args.smoke, recover=args.action == 'recover')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
        print('IMAGE_FALLBACK_FAILED: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
