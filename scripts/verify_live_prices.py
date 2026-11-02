"""Independent price check (network): for the 25 biggest paid models over the last 30 complete days, recompute dollars
from OpenRouter's raw daily prompt/completion counts per variant (standard + batch) x that variant's live realized
input/output price, and compare with results/daily_spend_by_model.csv."""
import collections, csv, json, time, urllib.parse, urllib.request
H = {"User-Agent": "Mozilla/5.0"}
def get(u):
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40))
        except Exception: time.sleep(3 * (i + 1))
    return {}
rows = list(csv.DictReader(open("results/daily_spend_by_model.csv")))
days = sorted({r["date"] for r in rows})[-30:]
pipe = collections.Counter()
for r in rows:
    if r["date"] in days: pipe[r["model"]] += float(r["usd"])
models = [m for m, _ in pipe.most_common(25)]
ind = collections.Counter(); batch = 0; total = 0
for m in models:
    q = urllib.parse.quote(m, safe="")
    for variant in ("standard", "batch"):
        ep = get(f"https://openrouter.ai/api/frontend/v1/stats/effective-pricing?permaslug={q}&shape=v7&variant={variant}").get("data") or {}
        act = get(f"https://openrouter.ai/api/frontend/v1/stats/model-activity?permaslug={q}&variant={variant}").get("data") or {}
        act = act.get("analytics", act) if isinstance(act, dict) else act
        wi, wo = ep.get("weightedInputPrice"), ep.get("weightedOutputPrice")
        for r in act:
            if r["date"][:10] not in days: continue
            p, c = r.get("total_prompt_tokens") or 0, r.get("total_completion_tokens") or 0
            total += p + c; batch += (p + c) if variant == "batch" else 0
            if wi is not None: ind[m] += (p * wi + c * wo) / 1e6
        time.sleep(0.3)
print(f"batch share of tokens: {batch/total:.2%}")
for m in models[:10]:
    print(f"  {m:46} pipeline ${pipe[m]/1e6:6.2f}M  independent ${ind[m]/1e6:6.2f}M  {(pipe[m]/ind[m]-1)*100:+5.1f}%" if ind[m] else f"  {m}: no live data")
P, I = sum(pipe[m] for m in models), sum(ind[m] for m in models)
print(f"top 25 total: pipeline ${P/1e6:.1f}M  independent ${I/1e6:.1f}M  {(P/I-1)*100:+.2f}%")
