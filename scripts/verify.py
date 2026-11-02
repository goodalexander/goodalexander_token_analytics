"""Checks on results/ (run after build.py, from the repo root).

1. Coverage   our 16-lab daily tokens vs OpenRouter's platform-wide weekly totals (public rankings chart, incl. "Others");
              the chart's named top models must match ours exactly.
2. Claude     pipeline Claude dollars vs an independent Claude series (data/claude, built from archived model pages
              and cache-calibrated list prices) where that series is mostly observed (Aug - Oct 25).
3. Price      share of each month's dollars priced at today's live rate rather than an archived rate, and how far
   source     month-on-month growth moves if those live-priced dollars are off by -30% / +30%.
"""
import collections, csv, datetime as dt, json

daily = list(csv.DictReader(open("results/daily_series.csv")))
rows = list(csv.DictReader(open("results/daily_spend_by_model.csv")))
tok = collections.defaultdict(dict)
for r in rows:
    tok[r["date"]][r["model"]] = float(r["tokens"])

print("1. coverage vs OpenRouter platform totals (weekly)")
W = json.load(open("data/raw/rankings_chart.json"))["data"]["data"]
covs = []
for w in W:
    s = dt.date.fromisoformat(w["x"]); days = [(s + dt.timedelta(i)).isoformat() for i in range(7)]
    if not all(d in tok for d in days):
        continue
    ours = sum(sum(tok[d].values()) for d in days); plat = sum(w["ys"].values())
    named = [k for k in w["ys"] if k != "Others"]
    match = sum(sum(tok[d].get(k, 0) for d in days) for k in named) / sum(w["ys"][k] for k in named)
    covs.append(ours / plat)
    print(f"   week {w['x']}: platform {plat/1e12:6.1f}T  ours {ours/1e12:6.1f}T  coverage {ours/plat:5.1%}  named-model match {match:.4f}")
print(f"   coverage range {min(covs):.1%} - {max(covs):.1%}, mean {sum(covs)/len(covs):.1%}")

print("\n2. Claude: pipeline vs independent series (Aug 1 - Oct 25)")
C = json.load(open("data/claude/daily_spend.json"))
pipe = collections.Counter(); ind = collections.Counter()
for r in rows:
    if r["model"].startswith("anthropic/") and "2026-08-01" <= r["date"] <= "2026-10-25":
        pipe[r["date"][:7]] += float(r["usd"])
for d, v in C.items():
    if "2026-08-01" <= d <= "2026-10-25":
        ind[d[:7]] += sum(v.values())
for k in sorted(pipe):
    print(f"   {k}: pipeline ${pipe[k]/1e6:6.2f}M  independent ${ind[k]/1e6:6.2f}M  diff {(pipe[k]/ind[k]-1)*100:+.1f}%")

print("\n3. dollars priced by extrapolating today's live rate back in time, and MoM sensitivity")
live = collections.defaultdict(float); allm = collections.defaultdict(float); days = collections.defaultdict(set)
for r in rows:
    k = r["date"][:7]; u = float(r["usd"]); allm[k] += u; days[k].add(r["date"])
    if r["price_source"].endswith("-extrapolated"):
        live[k] += u
months = sorted(allm)
for k in months:
    print(f"   {k}: extrapolated {live[k]/allm[k]:5.1%} of ${allm[k]/1e6:.1f}M")
for sc in (0.7, 1.0, 1.3):
    per = {k: (allm[k] - live[k] + live[k] * sc) / len(days[k]) for k in months}
    g = [f"{(per[months[i]]/per[months[i-1]]-1)*100:+.1f}%" for i in range(1, len(months))]
    print(f"   extrapolated x{sc}: MoM {g}  first->last {(per[months[-1]]/per[months[0]]-1)*100:+.1f}%")
