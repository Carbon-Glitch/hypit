"""Current shot-table schemas, legacy readers and explicit lossless-column migration."""
from __future__ import annotations
import argparse
import csv
import json
import re
from pathlib import Path

SCHEMA = json.loads((Path(__file__).resolve().parent.parent/'assets/shot-table-schema.json').read_text(encoding='utf-8'))

def schema(kind):
    return SCHEMA[kind]

def read_table(path, kind):
    spec=schema(kind)
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
    if headers not in (spec['columns'],spec['legacy']):
        raise ValueError(f"Use the {len(spec['columns'])}-column {kind} table (legacy {len(spec['legacy'])} also supported)")
    if not rows:raise ValueError(kind+' table is empty')
    required=spec['legacy'] if headers==spec['legacy'] else spec['required']
    seen=set();id_field=headers[0]
    for row in rows:
        if None in row or any(not isinstance(row.get(k),str) for k in headers):raise ValueError('Malformed CSV row')
        if any(not row[k].strip() for k in required):raise ValueError('Missing required '+kind+' fields')
        ident=row[id_field].strip()
        if ident in seen:raise ValueError('Duplicate shot ID: '+ident)
        seen.add(ident)
    return rows,headers

def sections(row,column,kind='source'):
    """Recognize only migration sections for this column, not arbitrary story markup."""
    value=row.get(column,'');old=schema(kind)['groups'].get(column,[])
    parts=re.split(r'(?m)^\[\[([^\]\r\n]+)\]\]\n',value)
    if parts[0] or len(parts)<3 or parts[1::2]!=old:return {}
    # One separator newline is added between sections by migration.
    return {label:body[:-1] if i<len(old)-1 else body
            for i,(label,body) in enumerate(zip(parts[1::2],parts[2::2]))}

def field_value(row,field,kind='source'):
    if field in row:return row[field]
    for column,old in schema(kind)['groups'].items():
        if field in old and column in row:
            if len(old)==1:return row[column]
            values=sections(row,column,kind)
            if field in values:return values[field]
    if kind=='source' and field=='时长':
        from source_shots import clock
        return str(clock(row['出点'])-clock(row['入点']))
    raise KeyError(field)

def expanded_fields(row,fields):
    result=set()
    for field in fields:
        parts=sections(row,field)
        result.update(parts if parts else [field])
    return result

def content_fields(row,headers):
    spec=schema('source')
    names=spec['legacy'][6:46] if headers==spec['legacy'] else spec['columns'][4:23]
    return {f for f in expanded_fields(row,names)
            if field_value(row,f).strip() and not field_value(row,f).lstrip().startswith(('UNKNOWN:','N/A:'))}

def migrate(path,output,kind):
    path,output=Path(path).resolve(),Path(output).resolve()
    if output.exists():raise ValueError('Use a new output path; the original table remains the backup')
    rows,headers=read_table(path,kind);spec=schema(kind)
    if kind=='source':
        from source_shots import load_table
        load_table(path)  # Checks legacy duration before replacing it with derived duration.
    converted=[]
    for row in rows:
        if headers==spec['columns']:converted.append(row);continue
        merged={}
        for column,old in spec['groups'].items():
            merged[column]=row[old[0]] if len(old)==1 else '\n'.join('[['+f+']]\n'+row[f] for f in old)
        for field in spec['legacy']:
            if kind=='source' and field=='时长':continue
            if field_value(merged,field,kind)!=row[field]:
                raise ValueError('Ambiguous migration section: '+field)
        converted.append(merged)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=spec['columns']);writer.writeheader();writer.writerows(converted)
    return {'output':str(output),'shots':len(converted),'columns':len(spec['columns']),
            'input_preserved':str(path),'source_pointers':'legacy field labels remain resolvable in migrated cells'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['migrate']);p.add_argument('kind',choices=['source','target'])
    p.add_argument('table',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    try:print(json.dumps(migrate(args.table,args.output,args.kind),ensure_ascii=False));return 0
    except (ValueError,KeyError,OSError) as e:print('TABLE_MIGRATION_FAILED: '+str(e));return 1

if __name__=='__main__':raise SystemExit(main())
