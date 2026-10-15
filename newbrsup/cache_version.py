import re, pathlib

p = pathlib.Path("lc.py")
src = p.read_text()

# find the async def version_config function and replace its body
pattern = re.compile(
    r"(async def version_config\(\).*?)(?=\n(?:async def |def |class )|\Z)",
    re.DOTALL,
)

new_fn = '''async def version_config():
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        app_version = await get_playstore_version()
        api_url = (
            "https://version.ggwhitehawk.com/live/ver.php"
            f"?version={app_version}"
            "&lang=hi&device=android&channel=android"
            "&appstore=googleplay&region=BD"
            "&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
        )
        response = await _http_get_debug("version_config", api_url)
        response.raise_for_status()
        data = response.json()
        result = (
            data.get("latest_release_version", "OB55"),
            data.get("remote_version", "1.132.10"),
            data.get("server_url", "https://loginbp.ppmainecoonghj.com/"),
        )
        _version_cache = result
        print_info(f"[VERSION] cached: rv={result[0]} cv={result[1]} url={result[2]}")
        return result
    except Exception as e:
        print_warning(f"[VERSION] live call failed ({type(e).__name__}: {e}) — using fallback")
        # cache the fallback too, but with a shorter effective TTL by leaving cache set
        # to force retry next call, we DON'T cache on failure
        return "OB55", "1.132.10", "https://loginbp.ppmainecoonghj.com/"
'''

count = 0
def repl(m):
    global count
    count += 1
    return new_fn

src_new, n = pattern.subn(repl, src, count=1)
if n == 0:
    print("[X] version_config not found")
    raise SystemExit(1)

# insert _version_cache = None just before the function definition
# find the first occurrence of "async def version_config" in the new source
idx = src_new.index("async def version_config")
insert = "_version_cache = None\n\n\n"
src_new = src_new[:idx] + insert + src_new[idx:]

p.write_text(src_new)
print(f"[+] replaced version_config, inserted _version_cache")
