"""Check a custom runner's declared media bindings; never submit or judge media."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROLES = {
    "identity_reference", "composition_reference", "first_frame", "last_frame",
    "video_reference", "audio_reference", "audio_reuse", "speech_drive",
}


class BindingError(ValueError):
    """An input, dependency or payload no longer meets the declared contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BindingError(message)


def object_value(value, label: str) -> dict:
    require(isinstance(value, dict), f"{label}: expected an object")
    return value


def text_value(value, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty text")
    return value


def list_value(value, label: str, *, nonempty: bool = False) -> list:
    require(isinstance(value, list), f"{label}: expected a list")
    require(not nonempty or bool(value), f"{label}: cannot be empty")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON contains duplicate keys")
        result[key] = value
    return result


def reject_constant(_):
    raise BindingError("JSON contains a non-finite number")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Do not echo request bodies, upload tokens or credentials in diagnostics.
        raise BindingError("Cannot read a required UTF-8 JSON file") from exc


def file_record(record, root: Path, label: str) -> Path:
    record = object_value(record, label)
    name = text_value(record.get("file"), f"{label}.file")
    expected = record.get("sha256")
    require(isinstance(expected, str) and bool(re.fullmatch(r"[0-9a-f]{64}", expected)),
            f"{label}: expected an actual lowercase SHA-256")
    path = (root / name).resolve()
    require(path.is_file(), f"{label}: file missing")
    require(path.stat().st_size > 0, f"{label}: file is empty")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    require(digest.hexdigest() == expected, f"{label}: content changed; recheck and re-export")
    return path


def pointer_value(document, pointer: str):
    require(pointer.startswith("/"), "Payload pointer must address a field")
    current = document
    for encoded in pointer[1:].split("/"):
        require(not re.search(r"~(?![01])", encoded), "Invalid JSON pointer escape")
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            require(bool(re.fullmatch(r"0|[1-9][0-9]*", token)), "Invalid array index")
            require(int(token) < len(current), "Payload array field missing")
            current = current[int(token)]
        elif isinstance(current, dict):
            require(token in current, "Payload field missing")
            current = current[token]
        else:
            raise BindingError("Payload pointer traverses a scalar")
    return current


def payload_match(item: dict, payload, label: str) -> str:
    pointer = text_value(item.get("pointer"), f"{label}.pointer")
    require("value" in item and item["value"] is not None, f"{label}: expected value missing")
    value = item["value"]
    require(value != "" and value != [] and value != {}, f"{label}: expected value empty")
    actual = pointer_value(payload, pointer)
    require(json.dumps(actual, sort_keys=True) == json.dumps(value, sort_keys=True),
            f"{label}: serialized value differs from the declared binding")
    return pointer


def accepted_input(item: dict, root: Path, label: str) -> None:
    require(item.get("accepted") is True, f"{label}: input is not accepted for this use")
    file_record(item.get("asset"), root, f"{label}.asset")
    file_record(item.get("review"), root, f"{label}.review")


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_slot_manifest(route: dict, payload: dict, prompt: str, bindings: dict) -> dict:
    """Validate a schema-derived slot manifest without guessing provider semantics."""
    slots = list_value(route.get("slots"), "route.slots", nonempty=True)
    by_id = {}
    by_pointer = {}
    for index, raw in enumerate(slots):
        row = object_value(raw, f"route.slots[{index}]")
        ident = text_value(row.get("id"), "route slot.id")
        media = text_value(row.get("media"), "route slot.media")
        require(media in {"image", "audio", "video"}, "Unknown route slot modality")
        pointer = text_value(row.get("pointer"), "route slot.pointer")
        # `pointer` is checked by payload_match when a binding uses the slot; this probes it now
        # so an unfilled slot cannot silently point at a removed node.
        pointer_value(payload, pointer)
        require(ident not in by_id and pointer not in by_pointer, "Duplicate route slot")
        by_id[ident] = row; by_pointer[pointer] = row
    used = {}
    labels = {}
    for identifier, item in bindings.items():
        slot_id = text_value(item.get("slot"), f"binding {identifier}.slot")
        require(slot_id in by_id, f"binding {identifier}: slot is not exposed by this route")
        slot = by_id[slot_id]
        require(item["pointer"] == slot["pointer"], f"binding {identifier}: slot/pointer mismatch")
        require(item.get("media") in {None, slot["media"]}, f"binding {identifier}: slot modality mismatch")
        label = text_value(item.get("label"), f"binding {identifier}.label")
        expected = {"image": "Picture", "audio": "Audio", "video": "Video"}[slot["media"]]
        require(re.fullmatch(re.escape(expected) + r" [1-9][0-9]*", label.strip("<>") ),
                f"binding {identifier}: label does not match slot modality")
        require(slot_id not in used, f"binding {identifier}: slot already assigned")
        require(label not in labels, "Two media slots claim the same reference label")
        allowed_roles = {"image": {"identity_reference", "composition_reference", "first_frame", "last_frame"},
                         "video": {"video_reference"}, "audio": {"audio_reference", "audio_reuse", "speech_drive"}}
        require(set(item["roles"]) <= allowed_roles[slot["media"]], "Binding role incompatible with slot modality")
        require(set(item["roles"]) <= set(slot.get("roles", allowed_roles[slot["media"]])),
                "Binding invents a semantic operation absent from the selected route")
        tokens = item["pointer"].split("/")
        require(len(tokens) == 4 and tokens[1] == "nodeInfoList" and tokens[3] == "fieldValue",
                "RunningHub slot must address its actual node value")
        node = payload["nodeInfoList"][int(tokens[2])]
        require(node.get("nodeId") == slot.get("node_id") and node.get("fieldName") == slot.get("field"),
                "Binding pointer addresses a different schema node")
        used[slot_id] = identifier; labels[label] = identifier
    for ident, slot in by_id.items():
        if ident not in used:
            value = pointer_value(payload, slot["pointer"])
            require(value is None or isinstance(value, str) and value.strip().casefold() in {"", "none"},
                    "Unselected media slot contains an unreviewed default input")
    for media, prefix in (("image", "Picture"), ("audio", "Audio"), ("video", "Video")):
        chosen = sorted((slot for slot in slots if slot["id"] in used and slot["media"] == media),
                        key=lambda row: row["order"])
        for number, slot in enumerate(chosen, 1):
            require(bindings[used[slot["id"]]]["label"] == f"<{prefix} {number}>",
                    "Reference labels disagree with active media order")
    mentioned = set(re.findall(r"<(?:Picture|Video|Audio) [1-9][0-9]*>", prompt))
    require(mentioned <= set(labels), "Prompt mentions an unbound media label")
    require(set(labels) <= mentioned, "A bound media label is absent from the prompt")
    return {"exposed": len(slots), "assigned": len(used),
            "unfilled": len(slots) - len(used), "modalities": {
                media: sum(slot["media"] == media for slot in slots) for media in {"image", "audio", "video"}}}


def control_scope(item: dict, plan: dict, payload, label: str, required: bool) -> None:
    if "control" not in item:
        require(not required, f"{label}: reference control scope missing")
        return
    control = object_value(item["control"], f"{label}.control")
    allow = [normalized(text_value(value, "allowed control")) for value in
             list_value(control.get("allow"), "control.allow", nonempty=True)]
    deny = [normalized(text_value(value, "excluded control")) for value in
            list_value(control.get("deny"), "control.deny")]
    require(not set(allow).intersection(deny), f"{label}: same scope is both allowed and excluded")
    pointer = text_value(plan.get("prompt_pointer"), "prompt_pointer")
    prompt = normalized(text_value(pointer_value(payload, pointer), "actual submitted prompt"))
    quotes = [normalized(text_value(value, "control clause")) for value in
              list_value(control.get("prompt_quotes"), "control.prompt_quotes", nonempty=True)]
    require(all(quote in prompt for quote in quotes),
            f"{label}: control clause absent from actual submitted prompt")
    clauses = " ".join(quotes)
    require(all(scope in clauses for scope in allow + deny),
            f"{label}: declared scope is not expanded in its submitted clauses")


def validate(path: Path, *, require_control_scopes: bool = False) -> dict:
    path = Path(path).resolve()
    root = path.parent
    plan = object_value(read_json(path), "plan")
    require(type(plan.get("version")) is int and plan["version"] == 1, "Unsupported plan version")
    payload = read_json(file_record(plan.get("request"), root, "request"))
    route = object_value(plan.get("route"), "route")
    text_value(route.get("id"), "route.id")
    file_record(route.get("evidence"), root, "route.evidence")
    supported = list_value(route.get("supported_roles"), "route.supported_roles", nonempty=True)
    require(all(isinstance(role, str) and role in ROLES for role in supported),
            "Route contains an unknown semantic role")
    selectors = list_value(route.get("selectors"), "route.selectors", nonempty=True)
    for index, selector in enumerate(selectors):
        payload_match(object_value(selector, "route selector"), payload, f"route.selectors[{index}]")

    bindings = {}
    pointers = set()
    for index, raw in enumerate(list_value(plan.get("bindings"), "bindings", nonempty=True)):
        label = f"bindings[{index}]"
        item = object_value(raw, label)
        identifier = text_value(item.get("id"), f"{label}.id")
        require(identifier not in bindings, f"{label}: duplicate binding ID")
        roles = list_value(item.get("roles"), f"{label}.roles", nonempty=True)
        require(all(isinstance(role, str) and role in supported for role in roles),
                f"{label}: role is not supported by the declared route")
        media_value = item.get("value")
        require(not (isinstance(media_value, str) and
                     media_value.strip().casefold() in {"none", "null", "undefined"}),
                f"{label}: media input is an absent placeholder, not a bound resource")
        accepted_input(item, root, label)
        control_scope(item, plan, payload, label, require_control_scopes)
        pointer = payload_match(item, payload, label)
        require(pointer not in pointers, f"{label}: input field is assigned more than once")
        pointers.add(pointer)
        bindings[identifier] = item

    prompt_pointer = text_value(plan.get("prompt_pointer"), "prompt_pointer") if plan.get("prompt_pointer") else None
    submitted_prompt = pointer_value(payload, prompt_pointer) if prompt_pointer else None
    if submitted_prompt is not None:
        submitted_prompt = text_value(submitted_prompt, "actual submitted prompt")
    if route.get("slot_manifest") is not None:
        from runninghub_h3 import route_data
        route_path = file_record(route["slot_manifest"], root, "current slot manifest")
        manifest, _ = route_data(route_path)
        require(manifest["id"] == route["id"], "Slot manifest belongs to another route")
        require(submitted_prompt is not None and plan["prompt_pointer"] == manifest["prompt"]["pointer"],
                "Slot manifest prompt pointer differs from request")
        slot_summary = validate_slot_manifest(manifest, payload, submitted_prompt, bindings)
        if "packet" in plan:
            from shot_packet import validate as packet_check
            packet_check(file_record(plan["packet"], root, "current shot execution packet"))
        if plan.get("reference_plan"):
            from runninghub_h3 import check_reference_plan
            assignment_path = file_record(plan["reference_plan"], root, "writer reference assignment")
            assignment = check_reference_plan(assignment_path)
            require(file_record(assignment["route"], assignment_path.parent, "assigned route") == route_path and
                    file_record(assignment["packet"], assignment_path.parent, "assigned packet") ==
                    file_record(plan["packet"], root, "executed packet"),
                    "Reference assignment differs from executed route/packet")
            assigned = {row["id"]: row for row in assignment["references"]}
            require(set(assigned) == set(bindings), "Actual bindings differ from writer reference assignment")
            for identifier, item in bindings.items():
                selected = assigned[identifier]
                require(all(item.get(key) == selected.get(key) for key in ("slot", "label", "roles", "asset", "review")),
                        "Actual input differs from writer-assigned reference")
                require(item.get("control", {}).get("allow") == selected["control_intent"]["allow"] and
                        item.get("control", {}).get("deny") == selected["control_intent"]["deny"],
                        "Actual reference control differs from writer assignment")
        if plan.get("upload_receipts_required"):
            import time
            for identifier, item in bindings.items():
                upload_path = file_record(item.get("upload"), root, "actual upload receipt")
                upload = object_value(read_json(upload_path), "actual upload")
                require(upload.get("host") == manifest["host"], "Upload receipt belongs to a different host")
                require(file_record(upload.get("asset"), upload_path.parent, "uploaded media") ==
                        file_record(item["asset"], root, "bound media"), "Upload receipt binds different bytes")
                require(upload.get("value") == item["value"] ==
                        upload.get("receipt", {}).get("data", {}).get("fileName"),
                        "Upload receipt resource differs from actual request")
                require(upload.get("receipt", {}).get("code") == 0, "Upload was rejected")
                require(type(upload.get("expires_at")) in {int, float} and upload["expires_at"] > time.time(),
                        "Uploaded reference expired; re-upload before re-freezing request")
    elif route.get("slots") is not None:
        require(submitted_prompt is not None, "Slot manifest requires prompt_pointer")
        slot_summary = validate_slot_manifest(route, payload, submitted_prompt, bindings)
    else:
        slot_summary = None

    requirement_ids = set()
    requirements = list_value(plan.get("requirements"), "requirements", nonempty=True)
    for index, raw in enumerate(requirements):
        label = f"requirements[{index}]"
        item = object_value(raw, label)
        identifier = text_value(item.get("id"), f"{label}.id")
        require(identifier not in requirement_ids, f"{label}: duplicate requirement ID")
        requirement_ids.add(identifier)
        binding = text_value(item.get("binding"), f"{label}.binding")
        require(binding in bindings, f"{label}: required binding missing")
        role = text_value(item.get("role"), f"{label}.role")
        require(role in bindings[binding]["roles"],
                f"{label}: input role was substituted")

    dependency_ids = set()
    dependencies = list_value(plan.get("dependencies"), "dependencies")
    for index, raw in enumerate(dependencies):
        label = f"dependencies[{index}]"
        item = object_value(raw, label)
        identifier = text_value(item.get("id"), f"{label}.id")
        require(identifier not in dependency_ids, f"{label}: duplicate dependency ID")
        dependency_ids.add(identifier)
        accepted_input(item, root, label)
    result = {"bindings": len(bindings), "requirements": len(requirements),
              "dependencies": len(dependencies)}
    if slot_summary is not None:
        result["slots"] = slot_summary
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="Exported bindings.json for the exact request")
    parser.add_argument("--require-control-scopes", action="store_true",
                        help="Require explicit allowed/excluded reference scopes in actual prompt text")
    args = parser.parse_args()
    try:
        result = validate(args.plan, require_control_scopes=args.require_control_scopes)
    except (BindingError, OSError) as exc:
        message = str(exc) if isinstance(exc, BindingError) else "Cannot access a required file"
        print(f"INPUT_BINDINGS_FAILED: {message}")
        return 1
    print("INPUT_BINDINGS_OK: " + json.dumps(result, sort_keys=True))
    print("Provider semantics, remote upload identity and audiovisual acceptance remain separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
