"""Schema-driven RunningHub Ref2VA adapter: clips, uploads, exact bindings, resumable transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlencode, quote

from check_request_bindings import (
    BindingError, file_record, object_value, read_json, require, text_value, validate as check_bindings,
)

MEDIA = {"IMAGE": "image", "AUDIO": "audio", "VIDEO": "video"}
PREFIX = {"image": "Picture", "audio": "Audio", "video": "Video"}
MEDIA_ROLES = {"image": {"identity_reference", "composition_reference", "first_frame", "last_frame"},
               "video": {"video_reference"}, "audio": {"audio_reference", "audio_reuse", "speech_drive"}}
REFERENCE_ROLES = {"image": ["identity_reference", "composition_reference"],
                   "video": ["video_reference"], "audio": ["audio_reference", "audio_reuse"]}
SUFFIXES = {"image": {".png", ".jpg", ".jpeg", ".webp"},
            "video": {".mp4", ".mov", ".mkv", ".webm"},
            "audio": {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}}


MODES = {"T2VA", "I2VA", "FL2VA", "L2VA", "Ref2VA"}
BASE_SECTIONS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
REF_SECTIONS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music")

def check_prompt_sections(prompt: str, mode: str) -> None:
    """Check section presence/order only; the reviewer checks official syntax and meaning."""
    fields = sorted(set(BASE_SECTIONS + REF_SECTIONS), key=len, reverse=True)
    pattern = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(" + "|".join(fields) +
                         r")(?:\*\*)?(?:[ \t]*:[ \t]*|[ \t]*(?=\r?$))")
    matches = list(pattern.finditer(prompt))
    expected = REF_SECTIONS if mode == "Ref2VA" else BASE_SECTIONS
    require(tuple(x.group(1) for x in matches) == expected,
            "H3 prompt sections are missing, duplicated, out of order or from a different mode")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(prompt)
        require(bool(prompt[match.end():end].strip()), "Empty official H3 prompt section")

def generation_policy(payload):
    """Current production choice: default instance and empty video-reference inputs."""
    empty = (None, "", "None", "none", [], {})
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"instanceType", "instance_type"}:
                    require(item == "default", "RunningHub must use the default instance")
                if key in {"video", "videos", "videoUrl", "videoUrls", "reference_video", "referenceVideo"}:
                    require(item in empty, "Video reference inputs are disabled")
                visit(item)
            if value.get("fieldName") in {"video", "video_path", "video_url"}:
                require(value.get("fieldValue") in empty, "Video reference inputs are disabled")
        elif isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, str):
            require(re.search(r"<Video\s+[0-9]+>", value) is None, "Video reference labels are disabled")
    visit(payload)


def ref(path):
    path = Path(path).resolve()
    return {"file": str(path), "sha256": digest(path)}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def schema_nodes(path):
    data = object_value(read_json(path), "RunningHub schema")
    require(data.get("code", 0) == 0, "Schema API returned an error")
    body = data.get("data", data)
    require(isinstance(body, dict), "Invalid schema data")
    rows = body.get("nodeInfoList")
    require(isinstance(rows, list) and rows, "Schema has no exposed nodes")
    result = {}
    for row in rows:
        key = (text_value(row.get("nodeId"), "schema node ID"),
               text_value(row.get("fieldName"), "schema field name"))
        require(key not in result, "Duplicate schema field")
        result[key] = row
    return result


def discover(schema, host, app_id, *, prompt_node=None, duration_node=None):
    """Make a declared route. Enumeration is not evidence of internal graph wiring."""
    schema = Path(schema).resolve()
    require(urlparse(host).scheme == "https" and urlparse(host).netloc and
            not urlparse(host).path.strip("/"), "Use the selected RunningHub HTTPS origin")
    require(re.fullmatch(r"[0-9]+", app_id), "Expected app ID")
    nodes = schema_nodes(schema)
    slots, counters = [], dict.fromkeys(PREFIX, 0)
    for index, ((node, field), row) in enumerate(nodes.items()):
        if row.get("fieldType") in MEDIA:
            kind = MEDIA[row["fieldType"]]
            counters[kind] += 1
            slots.append({"id": kind + "-" + str(counters[kind]), "node_id": node, "field": field,
                          "media": kind, "order": counters[kind],
                          "enabled": kind != "video",
                          "roles": REFERENCE_ROLES[kind],
                          "pointer": "/nodeInfoList/" + str(index) + "/fieldValue"})
    prompts = [key for key, row in nodes.items() if row.get("fieldType") == "STRING" and
               row.get("nodeName") == "Text"]
    durations = [key for key, row in nodes.items() if row.get("nodeName") == "PrimitiveFloat"]
    def choose(candidates, selected, name):
        if selected:
            candidates = [key for key in candidates if key[0] == str(selected)]
        require(len(candidates) == 1, "Select the exact " + name + " node from schema")
        return {"node_id": candidates[0][0], "field": candidates[0][1]}
    prompt_key = choose(prompts, prompt_node, "prompt")
    duration_key = choose(durations, duration_node, "duration")
    prompt_index = list(nodes).index((prompt_key["node_id"], prompt_key["field"]))
    duration_index = list(nodes).index((duration_key["node_id"], duration_key["field"]))
    prompt_key["pointer"] = "/nodeInfoList/" + str(prompt_index) + "/fieldValue"
    duration_key["pointer"] = "/nodeInfoList/" + str(duration_index) + "/fieldValue"
    return {"version": 1, "id": host.rstrip("/") + "/ai-app/" + app_id + "/Ref2VA",
            "host": host.rstrip("/"), "app_id": app_id, "mode": "Ref2VA", "schema": ref(schema),
            "observed_at": time.time(), "slots": slots, "capacity": counters,
            "generation_policy": {"instance_type": "default", "video_reference": False},
            "prompt": prompt_key, "duration": duration_key,
            "label_order_status": "declared", "label_order_basis": "Schema enumeration; inspect graph or calibrate actual labels",
            "limits": {"output_min": 4, "output_max": 15, "clip_min": 2, "clip_max": 15,
                       "audio_total_max": 15, "video_total_max": 15, "mixed_max": 12},
            "endpoints": {"upload": "/openapi/v2/media/upload/binary",
                          "submit": "/openapi/v2/run/ai-app/" + app_id, "query": "/openapi/v2/query"}}


def route_data(path):
    path = Path(path).resolve()
    data = object_value(read_json(path), "RunningHub route")
    require(data.get("version") == 1 and data.get("mode") == "Ref2VA", "Adapter requires Ref2VA route v1")
    schema = file_record(data.get("schema"), path.parent, "current app schema")
    nodes = schema_nodes(schema)
    seen, orders = set(), set()
    for slot in data.get("slots", []):
        key = (slot.get("node_id"), slot.get("field"))
        require(key in nodes and MEDIA.get(nodes[key].get("fieldType")) == slot.get("media"),
                "Slot does not match schema type/field")
        require(slot.get("id") not in seen and (slot["media"], slot.get("order")) not in orders,
                "Duplicate slot ID/order")
        require(type(slot.get("order")) is int and slot["order"] > 0, "Invalid slot order")
        require(isinstance(slot.get("roles"), list) and slot["roles"] and
                set(slot["roles"]) <= MEDIA_ROLES[slot["media"]], "Unknown semantic role for route slot")
        expected_pointer = "/nodeInfoList/" + str(list(nodes).index(key)) + "/fieldValue"
        require(slot.get("pointer") == expected_pointer, "Slot pointer differs from schema enumeration")
        seen.add(slot["id"]); orders.add((slot["media"], slot["order"]))
    declared = {(slot["node_id"], slot["field"]) for slot in data["slots"]}
    actual = {key for key, row in nodes.items() if row.get("fieldType") in MEDIA}
    require(declared == actual, "Route must inventory every exposed media slot")
    for field in ("prompt", "duration"):
        key = (data[field]["node_id"], data[field]["field"])
        require(key in nodes, "Route selector absent from schema")
        require(data[field].get("pointer") == "/nodeInfoList/" + str(list(nodes).index(key)) + "/fieldValue",
                "Route selector pointer differs from actual schema field")
    require(data.get("label_order_status") in {"declared", "verified"}, "Unknown label-order status")
    text_value(data.get("label_order_basis"), "label-order evidence")
    host = data.get("host", "")
    require(urlparse(host).scheme == "https" and urlparse(host).netloc and
            not urlparse(host).path.strip("/"), "Route origin must be HTTPS")
    return data, nodes


def executable(name, supplied=None):
    if supplied:
        path = Path(supplied).resolve()
        require(path.is_file(), "Specified media tool missing")
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".hypit" / "tools" / (name + ".exe" if os.name == "nt" else name)
    require(local.is_file(), "Install or locate " + name + " for actual media inspection")
    return str(local)


def probe(path, ffprobe=None):
    run = subprocess.run([executable("ffprobe", ffprobe), "-v", "error", "-show_format", "-show_streams",
                          "-of", "json", str(Path(path).resolve())], capture_output=True, text=True, check=True)
    data = json.loads(run.stdout)
    duration = float(data.get("format", {}).get("duration", 0))
    return {"duration": duration, "streams": data.get("streams", []), "artifact": ref(path)}


def clip(source, start, end, kind, output, *, ffmpeg=None, ffprobe=None, keep_audio=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    require(source != output, "Preserve original source media")
    require(kind in {"audio", "video"} and math.isfinite(start) and math.isfinite(end) and 0 <= start < end,
            "Invalid source clip interval")
    original = probe(source, ffprobe)
    require(end <= original["duration"] + .01 and 2 <= end-start <= 15, "Reference clips must be 2–15 seconds")
    require(output.suffix.lower() in SUFFIXES[kind], "Output suffix does not match clip kind")
    if output.exists():
        existing = output.with_suffix(output.suffix + ".clip.json")
        require(existing.is_file(), "Existing output has no extraction provenance; use a new path")
        cached = read_json(existing)
        require(cached.get("source") == ref(source) and cached.get("source_interval") == [start, end] and
                cached.get("media") == kind and cached.get("asset") == ref(output) and
                cached.get("source_audio_enabled") == (kind == "audio" or keep_audio),
                "Existing extraction differs from requested bytes/range; preserve it and use a new version")
        return cached
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [executable("ffmpeg", ffmpeg), "-v", "error", "-i", str(source),
               "-ss", str(start), "-t", str(end-start)]
    if kind == "audio":
        require(output.suffix.lower() == ".wav", "Audio extraction uses a WAV file")
        command += ["-vn", "-ac", "2", "-ar", "32000", "-c:a", "pcm_s16le"]
    else:
        require(output.suffix.lower() == ".mp4", "Video extraction uses MP4")
        command += ["-map", "0:v:0", "-c:v", "libx264", "-crf", "18", "-preset", "fast"]
        command += ["-map", "0:a:0?", "-c:a", "aac"] if keep_audio else ["-an"]
        command += ["-movflags", "+faststart"]
    subprocess.run(command + [str(output)], capture_output=True, check=True)
    actual = probe(output, ffprobe)
    require(abs(actual["duration"] - (end-start)) < .15, "Extracted clip duration differs from source range")
    receipt = {"version": 1, "source": ref(source), "source_interval": [start, end], "media": kind,
               "asset": ref(output), "probe": actual, "source_audio_enabled": kind == "audio" or keep_audio,
               "artistic_accepted": False}
    save(output.with_suffix(output.suffix + ".clip.json"), receipt)
    return receipt


def credential():
    key = os.environ.get("RUNNINGHUB_API_KEY")
    if key:
        return key.strip()
    folder = Path.home() / ".hypit" / "runninghub"
    encrypted = folder / "credential.dpapi"
    require(os.name == "nt" and encrypted.is_file(),
            "RunningHub credential missing; configure RUNNINGHUB_API_KEY or the user-bound .hypit/runninghub/credential.dpapi")
    env = dict(os.environ, HYPIT_RH_CREDENTIAL_FILE=str(encrypted))
    for name in list(env):
        if name.lower() == "psmodulepath":
            del env[name]
    command = ('$s=ConvertTo-SecureString ((Get-Content -Raw -LiteralPath $env:HYPIT_RH_CREDENTIAL_FILE).Trim()); '
               '$c=New-Object System.Management.Automation.PSCredential("hypit",$s); '
               '[Console]::Write($c.GetNetworkCredential().Password)')
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            env=env, capture_output=True, text=True)
    require(result.returncode == 0 and result.stdout.strip(), "Cannot decrypt user-bound RunningHub credential")
    return result.stdout.strip()


class HttpClient:
    """No automatic retry of create-job requests."""
    def __init__(self, key=None):
        self.key = key or credential()

    def send(self, url, data, content_type, timeout):
        request = urllib.request.Request(url, data=data, method="POST",
            headers={"Authorization": "Bearer " + self.key, "Content-Type": content_type})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("RunningHub request failed; preserve operation state before retrying") from exc

    def post(self, url, body):
        return self.send(url, body, "application/json", 90)

    def schema(self, host, app_id):
        # Official read-only ai-app schema API. Query credentials remain in process memory.
        url = host.rstrip("/") + "/api/webapp/apiCallDemo?" + urlencode({"apiKey": self.key, "webappId": app_id})
        request = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.key})
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                raw = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Cannot refresh current RunningHub app schema") from exc
        require(raw.get("code") == 0 and isinstance(raw.get("data", {}).get("nodeInfoList"), list),
                "Current application schema is unavailable")
        safe = {"code": 0, "data": {"webappName": raw["data"].get("webappName"),
                                  "nodeInfoList": raw["data"]["nodeInfoList"]}}
        return json.loads(json.dumps(safe, ensure_ascii=False).replace(self.key, "[redacted]"))

    def upload(self, url, path):
        path = Path(path)
        boundary = "hypit-" + uuid.uuid4().hex
        # A stable ASCII filename avoids multipart quoting/newline ambiguity.
        name = digest(path) + path.suffix.lower()
        prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                  f"Content-Type: {mimetypes.guess_type(name)[0] or 'application/octet-stream'}\r\n\r\n").encode()
        body = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.send(url, body, "multipart/form-data; boundary=" + boundary, 180)

    def download(self, url, destination):
        # Result URLs can be on signed object storage: never forward the API credential there.
        # API result paths may contain Chinese filenames; preserve existing escapes/signatures.
        url = quote(url, safe=":/?#[]@!$&'()*+,;=%~")
        with urllib.request.urlopen(url, timeout=180) as response, Path(destination).open("wb") as stream:
            shutil.copyfileobj(response, stream)


def upload(path, route, cache, client, now=None):
    now = time.time() if now is None else now
    path, cache = Path(path).resolve(), Path(cache)
    cache_key = hashlib.sha256((route["host"] + "\n" + digest(path)).encode()).hexdigest()
    target = cache / (cache_key + ".json")
    if target.exists():
        old = read_json(target)
        if old.get("expires_at", 0) > now + 120 and old.get("asset") == ref(path):
            return old
    response = client.upload(route["host"] + route["endpoints"]["upload"], path)
    require(response.get("code") == 0, "RunningHub upload rejected")
    value = text_value(response.get("data", {}).get("fileName"), "actual uploaded fileName")
    out = {"version": 1, "host": route["host"], "asset": ref(path), "value": value,
           "uploaded_at": now, "expires_at": now + 86400, "receipt": response}
    save(target, out)
    return out


def reference_plan(selection_path, *, spec_override=None):
    """Resolve pre-upload labels and scoped assets for the designated prompt writer."""
    selection_path = Path(selection_path).resolve()
    root = selection_path.parent
    spec = object_value(spec_override if spec_override is not None else read_json(selection_path), "reference selection")
    require(spec.get("version") == 1, "Unsupported reference selection")
    route_path = file_record(spec.get("route"), root, "reference route")
    route, _ = route_data(route_path)
    packet_path = file_record(spec.get("packet"), root, "reference shot packet")
    from shot_packet import validate as packet_check
    packet = packet_check(packet_path)
    slots = {slot["id"]: slot for slot in route["slots"]}
    selected = spec.get("media", [])
    require(isinstance(selected, list) and selected, "Select actual reference assets")
    require(all(item.get("slot") in slots for item in selected), "Reference selection uses an unavailable slot")
    require(not any(slots[item["slot"]]["media"] == "video" for item in selected),
            "Video reference inputs are disabled")
    require(len({item["slot"] for item in selected}) == len(selected) and
            len({item["id"] for item in selected}) == len(selected), "Duplicate reference slot/ID")
    from scene_continuity import check_references
    state_inputs = check_references(packet.get('continuity'), selected, root)
    result = {"version": 1, "kind": "reference_input_plan", "selection": ref(selection_path),
              "route": ref(route_path), "packet": ref(packet_path), "selected_shots": packet["selected_shots"],
              "label_order_status": route["label_order_status"], "references": [], "artistic_accepted": False}
    if packet.get('continuity'):
        result['continuity'] = {'context': packet['continuity'], 'inspected_inputs': state_inputs,
                                'pixel_semantics_verified': False}
    numbers = dict.fromkeys(PREFIX, 0)
    for item in sorted(selected, key=lambda row: (slots[row["slot"]]["media"], slots[row["slot"]]["order"])):
        slot = slots[item["slot"]]; kind = slot["media"]; numbers[kind] += 1
        require(set(item.get("roles", [])) and set(item["roles"]) <= set(slot["roles"]),
                "Reference duty is not exposed by route")
        require(item.get("accepted") is True, "Reference selection needs actual scoped asset acceptance")
        if item.get("grid"):
            require(not ({"first_frame", "last_frame"} & set(item["roles"])), "A grid cannot be a concrete frame")
        control = object_value(item.get("control"), "selected reference intent")
        require(isinstance(control.get("allow"), list) and control["allow"] and
                isinstance(control.get("deny"), list), "Record actual allowed/excluded reference duties")
        row = {key: item[key] for key in ("id", "slot", "roles", "accepted")}
        row.update(media=kind, label="<" + PREFIX[kind] + " " + str(numbers[kind]) + ">",
                   asset=ref(file_record(item["asset"], root, "accepted reference")),
                   review=ref(file_record(item["review"], root, "reference inspection")),
                   control_intent={"allow": control["allow"], "deny": control["deny"]})
        for key in ("speaker", "grid", "source_clip", "continuity_shots"):
            if key in item:
                row[key] = ref(file_record(item[key], root, "clip provenance")) if key == "source_clip" else item[key]
        result["references"].append(row)
    return result


def check_reference_plan(path):
    path = Path(path).resolve()
    data = object_value(read_json(path), "actual reference plan")
    require(data.get("kind") == "reference_input_plan", "Wrong reference plan kind")
    selection = file_record(data.get("selection"), path.parent, "reference selection")
    require(data == reference_plan(selection), "Reference plan differs from current selected assets/labels")
    return data


def prepare(spec_path, folder, *, client=None, ffprobe=None, upload_cache=None):
    """Upload only selected media; all exposed unselected media nodes become None."""
    spec_path, folder = Path(spec_path).resolve(), Path(folder).resolve()
    spec, root = object_value(read_json(spec_path), "H3 execution selection"), spec_path.parent
    require(spec.get("version") == 1, "Unsupported execution selection")
    generation_policy({"instance_type": spec.get("instance_type", "default")})
    planned = None
    if spec.get("reference_plan"):
        reference_path = file_record(spec["reference_plan"], root, "authored reference assignment")
        planned = check_reference_plan(reference_path)
        spec.setdefault("route", planned["route"])
        spec.setdefault("packet", planned["packet"])
        if "media" not in spec:
            quotes = object_value(spec.get("reference_quotes"), "actual authored reference clauses")
            spec["media"] = []
            for row in planned["references"]:
                item = {key: value for key, value in row.items() if key not in {"media", "control_intent"}}
                item["control"] = {**row["control_intent"], "prompt_quotes": quotes.get(row["id"], [])}
                spec["media"].append(item)
    route_path = file_record(spec.get("route"), root, "selected route")
    route, schema = route_data(route_path)
    packet_path = file_record(spec.get("packet"), root, "shot execution packet")
    from shot_packet import validate as packet_check
    packet = packet_check(packet_path)
    if spec.get("reference_plan"):
        reference_path = file_record(spec["reference_plan"], root, "authored reference assignment")
        require(file_record(planned["packet"], reference_path.parent, "planned packet") == packet_path and
                file_record(planned["route"], reference_path.parent, "planned route") == route_path,
                "Prompt reference assignment uses a different packet/route")
        current = reference_plan(spec_path, spec_override=spec)
        require(planned["references"] == current["references"], "Execution media differs from the prompt writer's reference assignment")
    prompt_path = file_record(spec.get("prompt"), root, "authored/compiled H3 prompt")
    prompt = prompt_path.read_text(encoding="utf-8-sig")
    check_prompt_sections(prompt, "Ref2VA")
    generation_policy(prompt)
    duration = spec.get("duration")
    require(type(duration) in {int, float} and math.isfinite(duration) and 4 <= duration <= 15,
            "H3 output must be 4–15 seconds")
    selected = spec.get("media", [])
    require(isinstance(selected, list) and selected, "Ref2VA execution must select actual references; use the base mode for text only")
    slots = {slot["id"]: slot for slot in route["slots"]}
    require(len(selected) == len({item.get("slot") for item in selected}), "A media slot is assigned twice")
    require(all(isinstance(item.get("id"), str) and item["id"].strip() for item in selected) and
            len(selected) == len({item["id"] for item in selected}), "Media binding IDs must be distinct")
    require(all(item.get("slot") in slots for item in selected), "Selected media slot is not exposed")
    require(not any(slots[item["slot"]]["media"] == "video" for item in selected),
            "Video reference inputs are disabled")
    # File order follows the actual route's declared graph order, not arbitrary request list order.
    ordered = sorted(selected, key=lambda item: (slots[item["slot"]]["media"], slots[item["slot"]]["order"]))
    checked, counts, totals = [], dict.fromkeys(PREFIX, 0), {"video": 0., "audio": 0.}
    for item in ordered:
        slot, roles = slots[item["slot"]], item.get("roles")
        kind = slot["media"]; counts[kind] += 1
        label = "<" + PREFIX[kind] + " " + str(counts[kind]) + ">"
        require(item.get("label") == label, "Prompt reference label disagrees with active slot order")
        require(isinstance(roles, list) and roles and set(roles) <= MEDIA_ROLES[kind], "Role incompatible with media slot")
        if item.get("grid"):
            require(not ({"first_frame", "last_frame"} & set(roles)), "Multiview grid is not a concrete keyframe")
        require(set(roles) <= set(slot["roles"]), "Selected semantic operation is not declared for this actual route slot")
        require(item.get("accepted") is True, "Selected input needs actual acceptance for its scoped use")
        path = file_record(item.get("asset"), root, "selected media")
        file_record(item.get("review"), root, "actual input review")
        require(path.suffix.lower() in SUFFIXES[kind], "Input suffix differs from slot modality")
        require(label in prompt, "Selected input label absent from submitted prompt")
        control = object_value(item.get("control"), "reference control scope")
        from check_request_bindings import control_scope
        control_scope(item, {"prompt_pointer": "/prompt"}, {"prompt": prompt}, "selected reference", True)
        for quote in control.get("prompt_quotes", []):
            require(text_value(quote, "reference clause") in prompt, "Reference clause absent from submitted prompt")
        actual = probe(path, ffprobe) if kind != "image" else None
        if actual:
            require(2 <= actual["duration"] <= 15.05, "Reference input clip must be 2–15 seconds")
            require(any(s.get("codec_type") == kind for s in actual["streams"]), "Reference lacks the selected media stream")
            totals[kind] += actual["duration"]
        checked.append((item, slot, path, label, actual))
    require(len(checked) <= min(12, route["limits"]["mixed_max"]) and
            counts["image"] <= 9 and counts["audio"] <= 3 and counts["video"] <= 3, "Too many reference files")
    require(all(totals[k] <= min(15, route["limits"][k + "_total_max"]) + .05 for k in totals),
            "Reference audio/video total exceeds 15 seconds")
    used_labels = set(re.findall(r"<(?:Picture|Video|Audio) [1-9][0-9]*>", prompt))
    require(used_labels == {item[3] for item in checked}, "Prompt refers to unbound or unused media labels")
    from scene_continuity import check_references, check_prompt
    state_inputs = check_references(packet.get('continuity'), selected, root)
    state_carriers = check_prompt(packet.get('continuity'), prompt)
    if (folder / "submit-started.json").exists() or (folder / "receipt.json").exists():
        raise BindingError("Do not rebuild a submitted job; recover it or create an explicit repair version")
    folder.mkdir(parents=True, exist_ok=True)
    if client is None and checked:
        client = HttpClient()
    require(type(spec.get("use_personal_queue", False)) is bool, "use_personal_queue must be a boolean")
    payload = {"nodeInfoList": [], "instanceType": "default",
               "usePersonalQueue": spec.get("use_personal_queue", False)}
    node_index = {}
    overrides = spec.get("controls", [])
    override_lookup = {(x["node_id"], x["field"]): x["value"] for x in overrides}
    require(len(override_lookup) == len(overrides) and set(override_lookup) <= set(schema), "Invalid control override")
    protected = {(slot["node_id"], slot["field"]) for slot in route["slots"]}
    protected.update((route[k]["node_id"], route[k]["field"]) for k in ("prompt", "duration"))
    require(not (set(override_lookup) & protected), "Media/prompt/duration must use their owned fields")
    for key, row in schema.items():
        value = "None" if row.get("fieldType") in MEDIA else row.get("fieldValue")
        if key in override_lookup:
            value = override_lookup[key]
        if key == (route["prompt"]["node_id"], route["prompt"]["field"]):
            value = prompt
        if key == (route["duration"]["node_id"], route["duration"]["field"]):
            value = str(duration)
        node_index[key] = len(payload["nodeInfoList"])
        payload["nodeInfoList"].append({"nodeId": key[0], "fieldName": key[1], "fieldValue": value})
    prompt_pointer = "/nodeInfoList/" + str(node_index[(route["prompt"]["node_id"], route["prompt"]["field"])]) + "/fieldValue"
    bindings, requirements = [], []
    upload_cache = Path(upload_cache).resolve() if upload_cache is not None else root / ".hypit-runninghub" / "uploads"
    for item, slot, path, label, actual in checked:
        receipt = upload(path, route, upload_cache, client)
        stored = folder / ("upload-" + slot["id"] + ".json")
        save(stored, receipt)
        index = node_index[(slot["node_id"], slot["field"])]
        payload["nodeInfoList"][index]["fieldValue"] = receipt["value"]
        binding = {"id": item["id"], "roles": item["roles"], "accepted": True,
                   "asset": ref(path), "review": ref(file_record(item["review"], root, "input review")),
                   "pointer": "/nodeInfoList/" + str(index) + "/fieldValue", "value": receipt["value"],
                   "slot": slot["id"], "label": label, "control": item["control"], "upload": ref(stored)}
        if actual:
            binding["media_probe"] = actual
        if item.get("speaker"):
            binding["speaker"] = item["speaker"]
        if item.get('continuity_shots'):
            binding['continuity_shots'] = item['continuity_shots']
        if item.get("source_clip"):
            clipping_path = file_record(item["source_clip"], root, "source excerpt provenance")
            clipping = read_json(clipping_path)
            require(file_record(clipping.get("asset"), clipping_path.parent, "extracted clip") == path,
                    "Reference source interval belongs to different media")
            file_record(clipping.get("source"), clipping_path.parent, "clip source")
            binding["source_clip"] = ref(clipping_path)
        bindings.append(binding)
        requirements.extend({"id": item["id"] + ":" + role, "role": role, "binding": item["id"]} for role in item["roles"])
    save(folder / "request.json", payload)
    generation_policy(payload)
    prompt_selector = {"pointer": prompt_pointer, "value": prompt}
    plan = {"version": 1, "request": ref(folder / "request.json"), "prompt_pointer": prompt_pointer,
            "route": {"id": route["id"], "evidence": ref(route_path),
                      "supported_roles": sorted(set().union(*(set(slot["roles"]) for slot in route["slots"]))),
                      "selectors": [prompt_selector], "slot_manifest": ref(route_path)},
            "bindings": bindings, "requirements": requirements, "dependencies": spec.get("dependencies", []),
            "packet": ref(packet_path), "upload_receipts_required": True}
    if planned is not None:
        plan["reference_plan"] = ref(reference_path)
    if packet.get('continuity'):
        plan['continuity'] = {'context': packet['continuity'], 'inspected_inputs': state_inputs,
                              'prompt_carriers': state_carriers, 'pixel_semantics_verified': False}
    save(folder / "bindings.json", plan)
    # Existing gate can consume request, prompt, route, bindings and packet without a second creative owner.
    check_bindings(folder / "bindings.json", require_control_scopes=True)
    output = {"version": 1, "selection": ref(spec_path), "packet": ref(packet_path),
              "request": ref(folder / "request.json"), "bindings": ref(folder / "bindings.json"),
              "prompt": ref(prompt_path), "route": ref(route_path), "prompt_pointer": prompt_pointer,
              "duration_pointer": "/nodeInfoList/" + str(node_index[(route["duration"]["node_id"], route["duration"]["field"])]) + "/fieldValue",
              "selected_shots": packet["selected_shots"], "actual_media_counts": counts,
              "label_order_status": route["label_order_status"], "artistic_accepted": False}
    save(folder / "prepared.json", output)
    return output


def check_prepared(job, route_path):
    """Default preflight: actual request, assets and target rows; no team review package."""
    from check_request_bindings import pointer_value
    job, route_path = Path(job).resolve(), Path(route_path).resolve()
    prepared = read_json(job / "prepared.json")
    require(file_record(prepared["route"], job, "prepared route") == route_path,
            "Submission route differs from preparation")
    request_path = file_record(prepared["request"], job, "actual request")
    require(request_path == job / "request.json", "Prepared request path differs from job")
    payload = read_json(request_path); generation_policy(payload)
    prompt = pointer_value(payload, prepared["prompt_pointer"])
    prompt_path = file_record(prepared["prompt"], job, "current authored prompt")
    require(prompt_path.read_text(encoding="utf-8-sig") == prompt, "Serialized H3 prompt differs from authored prompt")
    check_prompt_sections(prompt, "Ref2VA")
    duration = float(pointer_value(payload, prepared["duration_pointer"]))
    require(math.isfinite(duration) and 4 <= duration <= 15, "H3 duration must be 4–15 seconds")
    binding_path = file_record(prepared["bindings"], job, "current bindings")
    check_bindings(binding_path, require_control_scopes=True)
    binding = read_json(binding_path)
    require(file_record(binding["request"], binding_path.parent, "bound request") == request_path,
            "Bindings point to another request")
    require(not any("video_reference" in row["roles"] for row in binding["bindings"]),
            "Video reference inputs are disabled")
    packet_path = file_record(prepared["packet"], job, "current selected rows")
    from shot_packet import validate as packet_check
    packet = packet_check(packet_path)
    require(file_record(binding["packet"], binding_path.parent, "bound rows") == packet_path and
            read_json(packet_path)["selected_shots"] == prepared["selected_shots"],
            "Selected shot rows differ from prepared request")
    from scene_continuity import check_references, check_prompt
    state_inputs = check_references(packet.get('continuity'), binding['bindings'], job)
    state_carriers = check_prompt(packet.get('continuity'), prompt)
    if packet.get('continuity'):
        require(binding.get('continuity') == {'context': packet['continuity'], 'inspected_inputs': state_inputs,
                                              'prompt_carriers': state_carriers, 'pixel_semantics_verified': False},
                'Current scene state differs from the prepared request; rebuild affected inputs')
    body = request_path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == prepared["request"]["sha256"],
            "Request changed during preflight")
    return body


def submit(package=None, review=None, job=None, route_path=None, *, request_id=None, client=None):
    job, route_path = Path(job).resolve(), Path(route_path).resolve()
    route, _ = route_data(route_path)
    if (job / "receipt.json").exists():
        receipt = read_json(job / "receipt.json")
        task = receipt.get("taskId") or receipt.get("data", {}).get("taskId")
        require(task, "Stored rejection/uncertain receipt; inspect before a new job version")
        return {"status": "resume", "task_id": task}
    require(not (job / "submit-started.json").exists(), "Submission outcome uncertain; query recovered task, never auto-resubmit")
    def transport(body):
        generation_policy(json.loads(body))
        prepared = read_json(job / "prepared.json")
        require(file_record(prepared["route"], job, "prepared route") == route_path, "Submission route differs from preparation")
        require(digest(job / "request.json") == hashlib.sha256(body).hexdigest(), "Gate body differs from prepared request")
        local_client = client or HttpClient()
        # The exact checked bytes go to the endpoint; key exists only in HTTP headers.
        save(job / "submit-started.json", {"time": time.time(), "request_sha256": hashlib.sha256(body).hexdigest()})
        receipt = local_client.post(route["host"] + route["endpoints"]["submit"], body)
        save(job / "receipt.json", receipt)
        task = receipt.get("taskId") or receipt.get("data", {}).get("taskId")
        require(receipt.get("code", 0) == 0 and task, "No successful task receipt; do not repeat paid submission")
        return {"status": "submitted", "task_id": task}
    return transport(check_prepared(job, route_path))


def query(job, route_path, *, client=None, ffprobe=None):
    job = Path(job).resolve()
    route, _ = route_data(route_path)
    receipt = read_json(job / "receipt.json")
    task = receipt.get("taskId") or receipt.get("data", {}).get("taskId")
    require(task, "No recoverable task ID")
    client = client or HttpClient()
    result = client.post(route["host"] + route["endpoints"]["query"], json.dumps({"taskId": task}).encode())
    save(job / "status.json", result)
    status = result.get("status", result.get("data", {}).get("status"))
    collected = []
    if status == "SUCCESS":
        results = result.get("results") or result.get("data", {}).get("results") or []
        require(results, "SUCCESS has no output list; recover this task, do not submit again")
        for index, output in enumerate(results):
            url = output.get("url") or output.get("outputUrl")
            if not url:
                continue
            extension = str(output.get("outputType") or Path(urlparse(url).path).suffix or "mp4").lower().lstrip(".")
            if extension in {"video", "audio", "image"}:
                extension = {"video": "mp4", "audio": "wav", "image": "png"}[extension]
            require(re.fullmatch(r"[a-z0-9]{1,8}", extension), "Unsupported result file extension")
            destination = job / f"output-{index}.{extension}"
            if not destination.exists():
                partial = destination.with_suffix(destination.suffix + ".part")
                client.download(url, partial)
                require(partial.stat().st_size > 0, "Downloaded output is empty")
                os.replace(partial, destination)
            row = {"artifact": ref(destination), "node_id": output.get("nodeId"), "output_type": extension}
            if destination.suffix.lower() in SUFFIXES["video"] | SUFFIXES["audio"]:
                row["probe"] = probe(destination, ffprobe)
            collected.append(row)
        require(collected, "No downloadable media; recover stored result receipt")
        save(job / "download.json", {"task_id": task, "files": collected, "usage": result.get("usage"),
                                    "artistic_accepted": False})
    return {"task_id": task, "status": status, "usage": result.get("usage"), "files": collected,
            "artistic_accepted": False, "automatic_resubmission": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--schema", type=Path); d.add_argument("--host", required=True)
    d.add_argument("--app-id", required=True); d.add_argument("--output", type=Path, required=True)
    d.add_argument("--prompt-node"); d.add_argument("--duration-node")
    c = sub.add_parser("clip")
    c.add_argument("source", type=Path); c.add_argument("--start", type=float, required=True)
    c.add_argument("--end", type=float, required=True); c.add_argument("--kind", choices=["video", "audio"], required=True)
    c.add_argument("--output", type=Path, required=True); c.add_argument("--keep-audio", action="store_true")
    c.add_argument("--ffmpeg"); c.add_argument("--ffprobe")
    p = sub.add_parser("prepare"); p.add_argument("selection", type=Path)
    p.add_argument("--job", type=Path, required=True); p.add_argument("--ffprobe")
    r = sub.add_parser("plan"); r.add_argument("selection", type=Path); r.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("submit"); s.add_argument("--package", type=Path)
    s.add_argument("--review", type=Path); s.add_argument("--job", type=Path, required=True)
    s.add_argument("--route", type=Path, required=True); s.add_argument("--request-id")
    q = sub.add_parser("query"); q.add_argument("--job", type=Path, required=True)
    q.add_argument("--route", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "discover":
            schema = args.schema
            if schema is None:
                schema = args.output.with_name(args.output.stem + ".schema.json")
                save(schema, HttpClient().schema(args.host, args.app_id))
            result = discover(schema, args.host, args.app_id, prompt_node=args.prompt_node, duration_node=args.duration_node)
            save(args.output, result)
            result = {"route": str(args.output.resolve()), "capacity": result["capacity"],
                      "label_order_status": result["label_order_status"], "paid_calls": 0}
        elif args.action == "clip":
            result = clip(args.source, args.start, args.end, args.kind, args.output,
                          ffmpeg=args.ffmpeg, ffprobe=args.ffprobe, keep_audio=args.keep_audio)
            result = {"asset": result["asset"], "source_interval": result["source_interval"],
                      "duration": result["probe"]["duration"], "source_audio_enabled": result["source_audio_enabled"]}
        elif args.action == "plan":
            result = reference_plan(args.selection); save(args.output, result)
            result = {"plan": str(args.output.resolve()), "selected_shots": result["selected_shots"],
                      "references": [{key: row[key] for key in ("id", "slot", "label", "media")} for row in result["references"]],
                      "paid_calls": 0}
        elif args.action == "prepare":
            result = prepare(args.selection, args.job, ffprobe=args.ffprobe)
        elif args.action == "submit":
            result = submit(args.package, args.review, args.job, args.route, request_id=args.request_id)
        else:
            result = query(args.job, args.route)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print("RUNNINGHUB_H3_FAILED: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
