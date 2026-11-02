"""Live realized prices for every model on the lab pages -> data/prices/live_effective.json

For each model: OpenRouter's effective-pricing (cache-blended realized input/output $/M over roughly the last day or
week) and model-activity (daily prompt/completion tokens, last ~31 days). Free (":free") and stealth/cloaked models
are $0. No API key needed."""
import glob, json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from parse_author import parse
H = {"User-Agent": "Mozilla/5.0"}
def get(u):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40))
        except Exception: time.sleep(3 * (i + 1))
    return {}
models = set()
for f in glob.glob("data/raw/live/*.html") + glob.glob("data/raw/wayback/*/*.html"):
    for ys in parse(open(f, "rb").read()).values():
        models |= {m for m in ys if m.lower() not in ("others", "other")}
out = {}
for m in sorted(models):
    if m.endswith(":free") or m.startswith(("stealth/", "openrouter/")):
        out[m] = {"kind": "free"}; continue
    q = urllib.parse.quote(m, safe="")
    ep = get(f"https://openrouter.ai/api/frontend/v1/stats/effective-pricing?permaslug={q}&shape=v7&variant=standard").get("data") or {}
    act = get(f"https://openrouter.ai/api/frontend/v1/stats/model-activity?permaslug={q}&variant=standard").get("data") or {}
    act = act.get("analytics", act) if isinstance(act, dict) else act
    out[m] = {"kind": "effective" if ep.get("weightedInputPrice") is not None else "missing",
              "wIn": ep.get("weightedInputPrice"), "wOut": ep.get("weightedOutputPrice"), "cacheHit": ep.get("weightedCacheHitRate"),
              "daily": {r["date"][:10]: [r.get("total_prompt_tokens") or 0, r.get("total_completion_tokens") or 0] for r in act}}
    time.sleep(0.4)
os.makedirs("data/prices", exist_ok=True)
json.dump(out, open("data/prices/live_effective.json", "w"))
print(len(out), "models")
