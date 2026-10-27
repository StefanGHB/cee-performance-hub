import json, os, sys, glob, pathlib
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7
BASE = pathlib.Path("/home/claude/schemas/repo/fabric/item/report/definition")
def retrieve(uri):
    # map https://developer.microsoft.com/json-schemas/fabric/item/report/definition/... and file uris
    if uri.startswith("file://"):
        p = pathlib.Path(uri[7:])
    else:
        p = BASE / uri.split("/report/definition/")[1]
    return Resource.from_contents(json.load(open(p)), default_specification=DRAFT7)
registry = Registry(retrieve=retrieve)
def schema_for(doc_schema_url):
    rel = doc_schema_url.split("/report/definition/")[1]
    if rel.startswith("visualContainer/2.14.0"):
        rel = rel.replace("2.14.0", "2.13.0")
    p = BASE / rel
    s = json.load(open(p))
    s["$id"] = p.as_uri()
    return s
root = sys.argv[1]
errors = 0; n = 0
for f in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
    d = json.load(open(f))
    if "$schema" not in d or "/report/definition/" not in d["$schema"]:
        continue
    n += 1
    s = schema_for(d["$schema"])
    d["$schema"] = d["$schema"].replace("visualContainer/2.14.0", "visualContainer/2.13.0")
    v = Draft7Validator(s, registry=registry)
    errs = sorted(v.iter_errors(d), key=lambda e: e.path)
    for e in errs[:5]:
        errors += 1
        print(os.path.relpath(f, root), "->", list(e.absolute_path)[:8], e.message[:200])
print(f"validated {n} files, {errors} errors")
