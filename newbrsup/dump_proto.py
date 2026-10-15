import importlib

MODS = ["thunderFF_pb2", "StartMatch_pb2", "xora_pb2", "xorateam_pb2"]

def field_kind(f):
    try:
        if f.is_repeated:
            return "rep"
        if f.is_required:
            return "req"
        return "opt"
    except Exception:
        return "opt"

def type_name(f):
    if f.message_type is not None:
        return f.message_type.full_name
    if f.enum_type is not None:
        return f.enum_type.full_name
    return str(f.type)

def walk(msg_desc, indent=0):
    pad = "  " * indent
    print(f"{pad}message {msg_desc.name}")
    for f in msg_desc.fields:
        print(f"{pad}  #{f.number} {f.name}  ({field_kind(f)} {type_name(f)})")
    for nested in msg_desc.nested_types:
        walk(nested, indent + 1)

for name in MODS:
    try:
        mod = importlib.import_module(name)
    except Exception as e:
        print(f"===== {name}: import failed: {e}")
        continue
    print(f"\n===== {name} =====")
    for sym in dir(mod):
        obj = getattr(mod, sym)
        try:
            d = obj.DESCRIPTOR
        except Exception:
            continue
        if not hasattr(d, "fields"):
            continue
        # only top-level
        try:
            if d.containing_type is not None:
                continue
        except Exception:
            pass
        print(f"\n--- {sym} ---")
        walk(d, 1)
