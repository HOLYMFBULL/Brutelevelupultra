import re, shutil, sys, pathlib

SRC = pathlib.Path("lc.py")
code = SRC.read_text(encoding="utf-8")

if "_dbg_post" in code:
    print("[!] already injected. aborting.")
    sys.exit(0)

shutil.copy("lc.py", "lc.py.bak3")
print("[+] backup -> lc.py.bak3")

# ---- 1. Swap call sites BEFORE injecting helpers (so helpers aren't hit) ----
n_post = code.count("await client.post(")
n_get  = code.count("await client.get(")
code = code.replace("await client.post(", "await _dbg_post(")
code = code.replace("await client.get(",  "await _dbg_get(")
print(f"[+] swapped {n_post} POST, {n_get} GET call sites")

# ---- 2. Locate the client = httpx.AsyncClient(...) definition ----
m = re.search(r'^\s*client\s*=\s*httpx\.AsyncClient\(', code, re.M)
if not m:
    print("[X] could not find 'client = httpx.AsyncClient(' line")
    sys.exit(1)

# find end of that statement (matching closing paren) - simple heuristic:
start = m.start()
# scan forward for balanced parens starting from the first '('
depth = 0
i = code.index("(", start)
while i < len(code):
    c = code[i]
    if c == "(":
        depth += 1
    elif c == ")":
        depth -= 1
        if depth == 0:
            break
    i += 1
end = i + 1
insert_at = end

DEBUG_LAYER = r'''

# ==================== INJECTED HTTP DEBUG LAYER ====================
_MAG = '\033[95m'; _CYN = '\033[96m'; _WHT = '\033[97m'
_RED = '\033[91m'; _GRN = '\033[92m'; _YEL = '\033[93m'; _RST = '\033[0m'

_DEBUG_HTTP = True
_DEBUG_BODY_LIMIT = 4096
_raw_client = client


def _dbg_hx(data, limit=_DEBUG_BODY_LIMIT):
    if data is None:
        return "<None>"
    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")
    if not isinstance(data, (bytes, bytearray)):
        return f"<{type(data).__name__}>"
    h = bytes(data).hex()
    if len(h) > limit:
        return h[:limit] + f"...[+{len(h)-limit} hex chars]"
    return h


def _dbg_txt(data, limit=_DEBUG_BODY_LIMIT):
    if data is None:
        return "<None>"
    if isinstance(data, str):
        s = data
    elif isinstance(data, (bytes, bytearray)):
        try:
            s = bytes(data).decode("utf-8", errors="replace")
        except Exception:
            return _dbg_hx(data, limit)
    else:
        s = str(data)
    if len(s) > limit:
        return s[:limit] + f"...[+{len(s)-limit} chars]"
    return s


def _label_from_url(url):
    try:
        path = url.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else path
        return path.split("?")[0] or url
    except Exception:
        return str(url)


async def _dbg_post(url, **kwargs):
    label = _label_from_url(str(url))
    if not _DEBUG_HTTP:
        return await _raw_client.post(url, **kwargs)

    print(f"\n{_MAG}======================================================================{_RST}")
    print(f"{_MAG}[HTTP->] POST {label}{_RST}")
    print(f"{_WHT}  URL     : {url}{_RST}")
    hdrs = kwargs.get("headers") or {}
    if hdrs:
        print(f"{_WHT}  Headers :{_RST}")
        for k, v in hdrs.items():
            print(f"{_WHT}    {k}: {v}{_RST}")
    data = kwargs.get("data")
    jbody = kwargs.get("json")
    if data is not None:
        if isinstance(data, (bytes, bytearray)):
            print(f"{_WHT}  Body    : <bytes {len(data)}>{_RST}")
            print(f"{_WHT}    hex   : {_dbg_hx(data)}{_RST}")
            if len(data) % 16 == 0 and len(data) > 0:
                print(f"{_WHT}    (len %% 16 == 0 -> looks like AES-CBC ciphertext){_RST}")
        else:
            print(f"{_WHT}  Body    : {_dbg_txt(data)}{_RST}")
    if jbody is not None:
        try:
            print(f"{_WHT}  JSON    : {json.dumps(jbody)}{_RST}")
        except Exception:
            print(f"{_WHT}  JSON    : {jbody!r}{_RST}")

    import time as _t
    t0 = _t.time()
    try:
        resp = await _raw_client.post(url, **kwargs)
        dt = (_t.time() - t0) * 1000.0
        print(f"{_MAG}[HTTP<-] {label}  status={resp.status_code}  {dt:.0f}ms{_RST}")
        print(f"{_WHT}  Resp headers:{_RST}")
        for k, v in resp.headers.items():
            print(f"{_WHT}    {k}: {v}{_RST}")
        raw = resp.content
        print(f"{_WHT}  Resp len : {len(raw)} bytes{_RST}")
        printable = all((c >= 0x20 and c < 0x7F) or c in (9,10,13) for c in raw[:256]) if raw else True
        if printable:
            print(f"{_WHT}  Resp body: {_dbg_txt(raw)}{_RST}")
        else:
            print(f"{_WHT}  Resp hex : {_dbg_hx(raw)}{_RST}")
        ct = resp.headers.get("content-type", "")
        if "json" in ct.lower():
            try:
                j = resp.json()
                print(f"{_GRN}[HTTP<-] {label} parsed JSON:{_RST}")
                print(f"{_GRN}{json.dumps(j, indent=2)}{_RST}")
            except Exception as e:
                print(f"{_YEL}[HTTP<-] {label}: JSON parse failed: {e}{_RST}")
        print(f"{_MAG}======================================================================{_RST}\n")
        return resp
    except Exception as e:
        dt = (_t.time() - t0) * 1000.0
        print(f"{_RED}[HTTPX] {label}  FAILED after {dt:.0f}ms{_RST}")
        print(f"{_RED}  Exception: {type(e).__name__}: {e}{_RST}")
        print(f"{_MAG}======================================================================{_RST}\n")
        raise


async def _dbg_get(url, **kwargs):
    label = _label_from_url(str(url))
    if not _DEBUG_HTTP:
        return await _raw_client.get(url, **kwargs)

    print(f"\n{_MAG}======================================================================{_RST}")
    print(f"{_MAG}[HTTP->] GET {label}{_RST}")
    print(f"{_WHT}  URL     : {url}{_RST}")
    hdrs = kwargs.get("headers") or {}
    if hdrs:
        print(f"{_WHT}  Headers :{_RST}")
        for k, v in hdrs.items():
            print(f"{_WHT}    {k}: {v}{_RST}")

    import time as _t
    t0 = _t.time()
    try:
        resp = await _raw_client.get(url, **kwargs)
        dt = (_t.time() - t0) * 1000.0
        print(f"{_MAG}[HTTP<-] {label}  status={resp.status_code}  {dt:.0f}ms{_RST}")
        raw = resp.content
        print(f"{_WHT}  Resp len : {len(raw)} bytes{_RST}")
        printable = all((c >= 0x20 and c < 0x7F) or c in (9,10,13) for c in raw[:256]) if raw else True
        if printable:
            print(f"{_WHT}  Resp body: {_dbg_txt(raw)}{_RST}")
        else:
            print(f"{_WHT}  Resp hex : {_dbg_hx(raw)}{_RST}")
        print(f"{_MAG}======================================================================{_RST}\n")
        return resp
    except Exception as e:
        dt = (_t.time() - t0) * 1000.0
        print(f"{_RED}[HTTPX] {label}  FAILED after {dt:.0f}ms{_RST}")
        print(f"{_RED}  Exception: {type(e).__name__}: {e}{_RST}")
        print(f"{_MAG}======================================================================{_RST}\n")
        raise


# ---- protobuf parse tracer: dumps bytes when ParseFromString fails ----
def _install_proto_trace():
    try:
        from google.protobuf.message import Message
    except Exception:
        return
    if getattr(Message, "_dbg_traced", False):
        return
    _orig = Message.ParseFromString
    def traced(self, data, *args, **kwargs):
        try:
            return _orig(self, data, *args, **kwargs)
        except Exception as e:
            cls = type(self).__name__
            print(f"\n{_RED}[PROTO-X] {cls}.ParseFromString failed: {e}{_RST}")
            print(f"{_RED}  input len : {len(data) if data else 0}{_RST}")
            if data:
                print(f"{_RED}  hex[:128] : {bytes(data[:128]).hex()}{_RST}")
                print(f"{_RED}  hex[-128]: {bytes(data[-128:]).hex()}{_RST}")
                print(f"{_RED}  repr[:64] : {bytes(data[:64])!r}{_RST}")
            print(f"{_MAG}======================================================================{_RST}\n")
            raise
    Message.ParseFromString = traced
    Message._dbg_traced = True


_install_proto_trace()
# ==================== END INJECTED DEBUG LAYER ====================
'''

code = code[:insert_at] + DEBUG_LAYER + code[insert_at:]
SRC.write_text(code, encoding="utf-8")
print("[+] injected debug layer after client definition")
print("[+] done. run: python -u lc.py 2>&1 | tee dbg_run.log")
