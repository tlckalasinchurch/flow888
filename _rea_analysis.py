import json, os

base = "investigation.cany/evidence"
results = {}
for d in sorted(os.listdir(base)):
    dp = os.path.join(base, d)
    if not os.path.isdir(dp): continue
    for f in sorted(os.listdir(dp)):
        if not f.endswith(".json"): continue
        full = os.path.join(dp, f)
        with open(full, encoding="utf-8") as fh:
            data = json.load(fh)
        results[data["operation"]] = data

sec = results["native_sections_list"]["result"]
print("=== SECTIONS (7) ===")
for s in sec["sections"]:
    fmt = "  {:<8} {:<6} {:>10} bytes  file_off={:#x} start={:s} end={:s} entropy={:.3f}".format(
        s["name"], "X" if s["exec"] else "r", s["file_size"], s["file_offset"], s["start"], s["end"], s["entropy"])
    print(fmt)
print("\n  .rsrc = {} bytes = {:.1f} MB".format(89826352, 89826352/1048576))

print("\n=== NAMED ADDRESSES ===")
names = results["native_named_addresses_list"]["result"]
print("  total:", results["native_named_addresses_list"]["result"]["total"])
first_16 = names["names"][:16]
for n in first_16:
    print("  ", n["address"], "name:", n.get("name",""))
addrs = [int(n["address"],16) for n in names["names"]]
print("  addr range:", hex(min(addrs)), "->", hex(max(addrs)), "range:", hex(max(addrs)-min(addrs)))

print("\n=== FUNCTIONS (total 2977) ===")
funcs = results["native_functions_list"]["result"]
funcs_list = funcs["functions"]
print("  total:", funcs["total"])
sizes = [f.get("size",0) for f in funcs_list]
print("  distinct sizes:", sorted(set(sizes))[:20])
big = sorted(funcs_list, key=lambda f: f.get("size",0), reverse=True)[:10]
print("  largest 10:")
for f in big:
    print("    {:>4} bytes @ {:s} ({} instr, {} blocks)".format(f.get("size"), f["name"], f.get("instructions"), f.get("blocks")))

print("\n=== STRINGS SAMPLE (from ev_9c1ab...) ===")
strings_data = results["native_strings_browse"]["result"]
str_list = strings_data["strings"]
print("  total strings:", strings_data["total"])
# Find meaningful strings (paths, URLs, etc.)
import re
patterns = ["http", "://", ".exe", ".dll", ".dll", "fls=", "svchost", "Program Files", "HKCU", "HKEY", ".dll", "LoadLibrary", "MessageBox", "ExitProcess", "WinExec", "CreateService", "reg "
]
for s in str_list[:50]:
    txt = s.get("text","") if isinstance(s, dict) else str(s)
    if any(p in txt.lower() for p in ["http",".exe",".dll",".dll",".dll","fls=","program","hkey","loadlibrary","messagebox","exitprocess","winexec","createservice"]):
        print("  ", txt[:150])
PYEOF
