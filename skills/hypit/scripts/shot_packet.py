"""Project full shot rows into a scoped H3 execution packet. No creative rewriting."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from check_request_bindings import file_record, object_value, read_json, require, text_value
from source_shots import compile_table, load_table, validate_target_table
from shot_tables import read_table


def ref(path):
    path = Path(path).resolve()
    return {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def target_rows(path):
    return read_table(path, 'target')[0]


def identifiers(value):
    if value.strip().startswith("N/A:") or "新增" in value:
        return set()
    return {part.strip() for part in value.split(";") if part.strip()}


def scoped_records(records, content):
    """Close literal record dependencies; never summarize or invent a record."""
    selected = {}
    pending = json.dumps(content, ensure_ascii=False)
    while True:
        found = {key for key in records if re.search(
            r"(?<![A-Za-z0-9_.:-])@?" + re.escape(key) + r"(?![A-Za-z0-9_.:-])", pending)}
        new = found - set(selected)
        if not new:
            return selected
        for key in sorted(new):
            selected[key] = records[key]
        pending = json.dumps([records[key] for key in new], ensure_ascii=False)


def build(spec_path):
    spec_path = Path(spec_path).resolve()
    root = spec_path.parent
    spec = object_value(read_json(spec_path), "shot packet selection")
    require(spec.get("version") == 1, "Unsupported packet selection")
    storyboard = file_record(spec.get("storyboard"), root, "target storyboard")
    rows = target_rows(storyboard)
    selected = spec.get("selected_shots")
    require(isinstance(selected, list) and selected and len(selected) == len(set(selected)),
            "Select distinct target shots in playback order")
    lookup = {row["目标镜头ID"].strip(): row for row in rows}
    require(set(selected) <= set(lookup), "Packet selects an unknown target shot")
    positions = [list(lookup).index(key) for key in selected]
    require(positions == sorted(positions), "Packet shot order differs from target storyboard")
    scope = text_value(spec.get("scope"), "packet scope")
    result = {"version": 1, "kind": "shot_execution_packet", "scope": scope,
              "selection": ref(spec_path), "storyboard": ref(storyboard),
              "selected_shots": selected, "target_rows": [lookup[key] for key in selected],
              "owners": [], "owner_slices": [], "source_rows": [], "source_records": {},
              "dependencies": [], "artistic_accepted": False}
    for raw in spec.get("owners", []):
        path = file_record(raw, root, "stable document owner")
        result["owners"].append(ref(path))
    for raw in spec.get("owner_slices", []):
        path = file_record(raw.get("artifact"), root, "scoped owner")
        start, end = raw.get("start_line"), raw.get("end_line")
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines),
                "Owner slice must address actual complete lines")
        result["owner_slices"].append({"artifact": ref(path), "start_line": start, "end_line": end,
                                      "text": "".join(lines[start-1:end])})
    for raw in spec.get("dependencies", []):
        result["dependencies"].append(ref(file_record(raw, root, "packet dependency")))
    if "source_table" in spec:
        table = file_record(spec["source_table"], root, "canonical source table")
        context = file_record(spec.get("source_context"), root, "canonical source context")
        source = compile_table(table, context)
        validate_target_table(storyboard, source)
        source_rows, _ = load_table(table)
        source_lookup = {row["镜头ID"].strip(): row for row in source_rows}
        needed = set().union(*(identifiers(row["源镜头ID"]) for row in result["target_rows"]))
        neighbors = spec.get("dependency_source_shots", [])
        require(isinstance(neighbors, list) and set(neighbors) <= set(source_lookup),
                "Unknown neighboring source dependency")
        needed.update(neighbors)
        require(needed <= set(source_lookup), "Target row references an unknown source shot")
        result["source_rows"] = [row for row in source_rows if row["镜头ID"].strip() in needed]
        meta = read_json(context)
        result["source_records"] = scoped_records(meta.get("records", {}),
                                                  result["target_rows"] + result["source_rows"])
        result["source"] = {"table": ref(table), "context": ref(context),
                            "media": source["media"], "review": source["review"]}
        result["dependencies"].extend(source["source_shots"]["dependencies"])
    else:
        require(spec.get("source_kind") == "original", "Source-led packet needs canonical source table/context")
        require(not any(identifiers(row["源镜头ID"]) for row in result["target_rows"]),
                "Original packet cannot invent source references")
    from scene_continuity import resolve as resolve_continuity
    spatial = resolve_continuity(spec, root, result['target_rows'], all_rows=rows)
    if spatial:
        result['continuity'] = spatial
    else:
        require(not spec.get('adoptions'), 'Adopted scene state was supplied but no selected row consumes it')
    result["context_usage"] = {
        "full_target_rows": len(rows), "selected_target_rows": len(selected),
        "selected_source_rows": len(result["source_rows"]),
        "policy": "literal full selected rows and dependency closure; stable owners by hash, no summaries"}
    return result


def validate(path):
    path = Path(path).resolve()
    data = object_value(read_json(path), "shot execution packet")
    require(data.get("kind") == "shot_execution_packet", "Wrong packet kind")
    selection = file_record(data.get("selection"), path.parent, "packet selection")
    require(data == build(selection), "Packet differs from current owning rows; mechanically rebuild it")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = build(args.path) if args.action == "build" else validate(args.path)
        if args.action == "build":
            require(args.output is not None, "build requires --output")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "projected", "selected_shots": data["selected_shots"],
                          "context_usage": data["context_usage"], "artistic_accepted": False}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("SHOT_PACKET_FAILED: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
