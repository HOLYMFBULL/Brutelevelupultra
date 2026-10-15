#!/usr/bin/env python3
"""Add post-match EXP refresh to lc.py — idempotent, safe to run twice."""
import pathlib, re, sys

TARGET = pathlib.Path("lc.py")
src = TARGET.read_text(encoding="utf-8")

if "POST-MATCH-REFRESH" in src:
    print("[!] already patched. nothing to do.")
    sys.exit(0)

# ─── 1) Add trigger_post_match_refresh() inside functional_lone_wolf ───
# Match the function signature, then the first "try:" line at deeper indent.
sig_re = re.compile(
    r"(async def functional_lone_wolf\([^\)]*\):[ \t]*\r?\n)"    # header
    r"((?:[ \t]+[^\n]*\r?\n)*?)"                                  # body up to first try
    r"([ \t]+try:[ \t]*\r?\n)",
    re.MULTILINE,
)

def add_trigger(m):
    header, body, tryln = m.group(1), m.group(2), m.group(3)
    if "trigger_post_match_refresh" in body:
        return m.group(0)
    indent = re.match(r"[ \t]+", tryln).group(0)
    trig = (
        f"{indent}# POST-MATCH-REFRESH: ~10s after a match completes, re-read level\n"
        f"{indent}async def trigger_post_match_refresh():\n"
        f"{indent}    await asyncio.sleep(10.0)\n"
        f"{indent}    try:\n"
        f"{indent}        cd = bot_state.account_credentials.get(uid_str)\n"
        f"{indent}        if cd:\n"
        f"{indent}            await refresh_account_profile(cd)\n"
        f"{indent}            try:\n"
        f"{indent}                _lv = bot_state.get_account_level(uid_str)\n"
        f"{indent}                print_info(f\"[POST-MATCH-REFRESH] UID {{uid_str}} live level: {{_lv}}\")\n"
        f"{indent}            except Exception:\n"
        f"{indent}                pass\n"
        f"{indent}    except Exception as _e:\n"
        f"{indent}        print_warning(f\"[POST-MATCH-REFRESH] error: {{_e}}\")\n"
        f"\n"
    )
    return header + body + trig + tryln

src_new, n = sig_re.subn(add_trigger, src, count=1)
if n == 0:
    print("[X] functional_lone_wolf signature not matched. step 1 skipped.")
    sys.exit(1)
src = src_new
print("[+] step 1: added trigger_post_match_refresh")

# ─── 2) Patch play_game signature to accept on_match_complete=None ───
sig_pg = re.compile(
    r"(async def play_game\([^\)]*?match_index\s*:\s*int\s*)(\))",
    re.DOTALL,
)

def add_pg_param(m):
    head, tail = m.group(1), m.group(2)
    if "on_match_complete" in head:
        return m.group(0)
    return head.rstrip() + ", on_match_complete=None" + tail

src_new, n = sig_pg.subn(add_pg_param, src, count=1)
if n == 0:
    print("[!] step 2: play_game signature not matched — SKIPPING")
else:
    src = src_new
    print("[+] step 2: play_game accepts on_match_complete")

# ─── 3) Pass the callback in the play_game(...) call inside functional_lone_wolf ───
pg_call = re.compile(
    r"(play_game\s*\(\s*[^\)]*?match_index\s*=\s*match_index\s*)(\))",
    re.DOTALL,
)

def add_call_param(m):
    head, tail = m.group(1), m.group(2)
    if "on_match_complete" in head:
        return m.group(0)
    return head.rstrip() + ", on_match_complete=trigger_post_match_refresh" + tail

src_new, n = pg_call.subn(add_call_param, src, count=1)
if n == 0:
    print("[!] step 3: play_game(...) call not matched — SKIPPING")
else:
    src = src_new
    print("[+] step 3: play_game(...) passes callback")

# ─── 4) Wire the callback inside play_game's finally block ───
# Find "if completed_cleanly:" block in the finally section.
fin_re = re.compile(
    r"([ \t]+if completed_cleanly:\r?\n(?:[ \t]+[^\n]*\r?\n)+)",
    re.MULTILINE,
)

def add_fin_call(m):
    block = m.group(1)
    if "on_match_complete" in block:
        return m.group(0)
    # indent for the new lines: one level deeper than the "if" statement
    base = re.match(r"[ \t]+", block).group(0)
    inner = base + "    "
    add = (
        f"{inner}if on_match_complete:\n"
        f"{inner}    try:\n"
        f"{inner}        asyncio.create_task(on_match_complete())\n"
        f"{inner}    except Exception:\n"
        f"{inner}        pass\n"
    )
    return block + add

src_new, n = fin_re.subn(add_fin_call, src, count=1)
if n == 0:
    print("[!] step 4: 'if completed_cleanly:' block not matched — SKIPPING")
else:
    src = src_new
    print("[+] step 4: play_game fires callback on completed_cleanly")

TARGET.write_text(src, encoding="utf-8")
print(f"[✓] wrote {TARGET}")
