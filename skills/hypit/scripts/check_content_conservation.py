"""Validate canonical source contribution declarations; not an artistic verdict."""
from __future__ import annotations


from check_request_bindings import file_record, list_value, object_value, require, text_value

FAMILIES = {"plot", "dialogue", "shot_language", "director_intent", "audience_experience"}
CHECKS = {"visual", "motion", "audio"}


def indexed(value, label, *, empty=False):
    result = {}
    for raw in list_value(value, label, nonempty=not empty):
        row = object_value(raw, label)
        ident = text_value(row.get("id"), label + ".id")
        require(ident not in result, label + ": duplicate ID")
        result[ident] = row
    return result


def strings(value, label, *, empty=False):
    result = [text_value(x, label) for x in list_value(value, label, nonempty=not empty)]
    require(len(set(result)) == len(result), label + ": duplicate value")
    return result


def source_contract(source, root, details):
    require(source.get("version") in {2, 3} and type(source.get("version")) is int,
            "No-loss conservation requires source catalogue version 2 or canonical table version 3")
    require(source.get("baseline_kind") in {"reference", "approved_draft"}, "Resolve actual conservation baseline")
    if source['version'] == 3:
        require(source['baseline_kind'] == 'reference', 'Canonical table v3 is an observed reference, not an approved draft')
        from source_shots import validate_projection
        validate_projection(source, root)
    inventories = object_value(source.get("inventories"), "source contribution inventories")
    require(set(inventories) == FAMILIES, "Source must index plot/dialogue/shot language/director intent/audience experience")
    result = {}; covered = set(); obligation_ids = set(); inventory_ids = set()
    for detail in details.values():
        obligations = indexed(detail.get("obligations"), "source detail obligations")
        for ident, row in obligations.items():
            require(ident not in obligation_ids, "Source obligation IDs must be globally unique")
            obligation_ids.add(ident)
            text_value(row.get("description"), "observed source obligation")
            checks = strings(row.get("checks"), "obligation modalities")
            require(set(checks) <= CHECKS, "Unknown conservation modality")
    for family, entries in inventories.items():
        current = indexed(entries, "source " + family, empty=True)
        if not current:
            file_record(object_value(source.get("observed_absence"), "verified source absences").get(family),
                        root, "actually observed absence: " + family)
        for ident, entry in current.items():
            require(ident not in inventory_ids, "Source contribution IDs must be globally unique")
            inventory_ids.add(ident)
            refs = strings(entry.get("details"), "indexed source detail IDs")
            require(set(refs) <= set(details), "Source index invents a detail")
            covered.update(refs)
            text_value(entry.get("description"), "source contribution description")
            if family == "director_intent":
                require(entry.get("basis") in {"observed_interpretation", "author_statement"},
                        "Do not claim private director intent without an actual statement")
                if entry['basis'] == 'author_statement':
                    statement=file_record(entry.get('statement'),root,'actual director statement')
                    require(text_value(entry.get('statement_quote'),'actual director quote') in
                            statement.read_text(encoding='utf-8-sig'),'Invented private director intent is not source evidence')
            if family == "dialogue":
                for field in ("text", "speaker", "language"):
                    text_value(entry.get(field), "source dialogue." + field)
                require('audio' in {check for detail_id in refs for row in details[detail_id]['obligations']
                                    for check in row['checks']}, "Spoken source dialogue requires audio conservation")
        result[family] = current
    require(covered == set(details), "Source detail omitted from its independent contribution index")
    return result
