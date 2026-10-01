"""Stdlib-only validator for mutation-results.json against
mutation-results.schema.json (supports the subset of JSON Schema it uses:
type, required, properties, items, enum, additionalProperties).
Usage: python3 validate_artifact.py [path]   -> exit 0 valid, 1 invalid."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "mutation-results.schema.json")
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def validate(doc, schema=None, path="$"):
    """Return a list of human-readable errors (empty when valid)."""
    if schema is None:
        schema = json.load(open(SCHEMA_PATH))
    errs = []
    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        if not any(_is(doc, t) for t in types):
            return [f"{path}: expected {' or '.join(types)}, got {type(doc).__name__} {json.dumps(doc)[:60]}"]
    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: invalid value {json.dumps(doc)}; allowed: {', '.join(map(json.dumps, schema['enum']))}")
    if isinstance(doc, dict):
        for k in schema.get("required", []):
            if k not in doc:
                errs.append(f"{path}: missing required field '{k}'")
        props = schema.get("properties", {})
        for k, v in doc.items():
            sub = props.get(k, schema.get("additionalProperties"))
            if isinstance(sub, dict):
                label = f"{path}.{k}"
                if path.startswith("$.mutants[") and "name" in doc and k != "name":
                    label += f" (mutant '{doc['name']}')"
                errs += validate(v, sub, label)
    if isinstance(doc, list) and "items" in schema:
        for i, v in enumerate(doc):
            errs += validate(v, schema["items"], f"{path}[{i}]")
    return errs


def main(argv):
    p = argv[1] if len(argv) > 1 else os.path.join(HERE, "mutation-results.json")
    try:
        doc = json.load(open(p))
    except (OSError, ValueError) as e:
        print(f"INVALID {p}: cannot read JSON ({e})"); return 1
    errs = validate(doc)
    if errs:
        print(f"INVALID {p}: {len(errs)} schema error(s)")
        for e in errs:
            print(f"  - {e}")
        print(f"Schema: {os.path.basename(SCHEMA_PATH)}")
        return 1
    print(f"VALID {p}"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
