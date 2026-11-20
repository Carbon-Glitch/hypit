"""Compatibility entry for light request checks. No reviewers, freeze chain or CI invocation."""
import argparse
from pathlib import Path
from check_request_bindings import file_record, read_json, require
from runninghub_h3 import check_prompt_sections, check_prepared


def validate(package_path, review_path=None, *, request_id=None):
    path=Path(package_path).resolve()
    if path.is_dir():job=path
    else:
        data=read_json(path)
        if path.name=="prepared.json":job=path.parent
        elif "artifacts" in data:
            rows=[row for row in data["artifacts"] if row.get("role")=="request"
                  and (request_id is None or row.get("id")==request_id)]
            require(len(rows)==1,"Select one actual request")
            job=file_record(rows[0],path.parent,"actual request").parent
        else:job=path.parent
    prepared=read_json(job/"prepared.json")
    route=file_record(prepared["route"],job,"selected route")
    return check_prepared(job,route)


def checked_submit(package_path, review_path, submit_bytes, *, request_id=None):
    return submit_bytes(validate(package_path,review_path,request_id=request_id))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_or_package");parser.add_argument("legacy_review",nargs="?")
    parser.add_argument("--request-id");args=parser.parse_args()
    body=validate(args.job_or_package,args.legacy_review,request_id=args.request_id)
    print("REQUEST_OK: "+str(len(body))+" bytes; no reviewers, model calls or tests run.")
