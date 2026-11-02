"""Archived realized prices and prompt/completion mixes from the Wayback Machine.

    python3 scripts/fetch_archived_prices.py        # after build.py has run once with live prices

1. One index query per endpoint lists every archived capture of OpenRouter's effective-pricing and model-activity
   endpoints (late May - Oct 2026).
2. For the paid models carrying 90% of Jun-Sep dollars: one effective-pricing capture near the middle of each month the
   model was active, and one model-activity capture near each month end (31 days of daily prompt/completion tokens).
   For the 25 biggest October models and 15 biggest September models: captures about weekly from Sep 20 to Oct 30
   (prices move fastest in the weeks after a launch).
3. Appends to data/prices/archived_effective.json ([[date, input $/M, output $/M, cache hit rate], ...] per model) and
   data/prices/archived_activity.json ({date: [prompt, completion]} per model).
Serial, a few seconds apart: the Archive throttles."""
import collections, csv, gzip, json, os, time, urllib.parse, urllib.request
H = {"User-Agent": "Mozilla/5.0 (research; low rate)"}
def get(u, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=300).read()
        except Exception: time.sleep(20 * (i + 1))
def index(endpoint):
    rows = json.loads(get(f"https://web.archive.org/cdx/search/cdx?url=openrouter.ai/api/frontend/{endpoint}&matchType=prefix&output=json"
                          "&fl=timestamp,original&filter=statuscode:200&from=20260520&to=20261031"))[1:]
    by = collections.defaultdict(list)
    for ts, o in rows:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(o).query)
        if (q.get("variant") or ["standard"])[0] == "standard":
            by[(q.get("permaslug") or [""])[0]].append((ts, o))
    return by
EP = index("v1/stats/effective-pricing"); time.sleep(20)
for m, v in index("stats/effective-pricing").items(): EP[m] += v   # older path, used until June 2026
time.sleep(20); AC = index("v1/stats/model-activity")
spend = collections.Counter(); month = collections.defaultdict(collections.Counter)
for r in csv.DictReader(open("results/daily_spend_by_model.csv")):
    u = float(r["usd"])
    if u > 0: spend[r["model"]] += u; month[r["model"]][r["date"][:7]] += u
js = collections.Counter({m: sum(v for k, v in month[m].items() if k < "2026-10") for m in month})
models, acc = [], 0
for m, v in js.most_common():
    models.append(m); acc += v
    if acc >= 0.9 * sum(js.values()): break
oct_ = collections.Counter({m: month[m]["2026-10"] for m in month}); sep = collections.Counter({m: month[m]["2026-09"] for m in month})
near = lambda caps, day, tol: min([c for c in caps if abs(int(c[0][:8]) - int(day)) <= tol] or [None], key=lambda c: 0 if c is None else abs(int(c[0][:8]) - int(day)))
plan_p, plan_a = [], []
for m in models:
    for k, u in month[m].items():
        if u < 0.03 * spend[m]: continue
        c = near(EP.get(m, []), k.replace("-", "") + "15", 16)
        if c: plan_p.append((m, *c))
        c = near(AC.get(m, []), str(int(k.replace("-", "") + "28") + 3), 12)
        if c: plan_a.append((m, *c))
for m in dict.fromkeys([m for m, _ in oct_.most_common(25)] + [m for m, _ in sep.most_common(15)]):
    for t in ("20260920", "20260928", "20261006", "20261014", "20261022", "20261030"):
        c = near(EP.get(m, []), t, 4)
        if c: plan_p.append((m, *c))
P = json.load(open("data/prices/archived_effective.json")) if os.path.exists("data/prices/archived_effective.json") else {}
A = json.load(open("data/prices/archived_activity.json")) if os.path.exists("data/prices/archived_activity.json") else {}
for kind, plan in (("prices", plan_p), ("activity", plan_a)):
    for m, ts, orig in dict.fromkeys(plan):
        raw = get(f"https://web.archive.org/web/{ts}id_/{orig}"); time.sleep(3)
        if not raw: continue
        try: raw = gzip.decompress(raw)
        except Exception: pass
        try: d = json.loads(raw); d = d.get("data", d)
        except Exception: continue
        if kind == "prices" and d.get("weightedInputPrice") is not None:
            day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            if all(p[0] != day for p in P.get(m, [])):
                P.setdefault(m, []).append([day, d["weightedInputPrice"], d["weightedOutputPrice"], d.get("weightedCacheHitRate")])
        elif kind == "activity":
            d = d.get("analytics", d) if isinstance(d, dict) else d
            for r in d or []:
                A.setdefault(m, {})[str(r.get("date", ""))[:10]] = [r.get("total_prompt_tokens") or 0, r.get("total_completion_tokens") or 0]
json.dump(P, open("data/prices/archived_effective.json", "w")); json.dump(A, open("data/prices/archived_activity.json", "w"))
print(len(P), "models with archived prices;", len(A), "with archived activity")
