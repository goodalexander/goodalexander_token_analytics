"""Daily and monthly dollars spent on OpenRouter models, Jun 1 - Oct 31 2026.

    python3 scripts/build.py          # from the repo root; reads data/, writes results/

Tokens   data/raw: OpenRouter lab pages (openrouter.ai/<lab>), live and Wayback captures. Each page embeds 91 days of
         daily tokens per model (prompt + completion). Per (day, model) the newest source listing the model wins; a
         capture's last day is partial and dropped.
Prices   every model-day is priced at OpenRouter's realized, cache-blended input/output price ($/M tokens):
           each model's archived effective-pricing captures (each = realized price over the ~7 days before it) plus
           today's live realized price as a point dated LIVE_DATE; the day's price is interpolated in time between
           the points either side. Labels: archived / live (nearest point within 45 days) or *-extrapolated.
         free (":free") and stealth/cloaked models cost $0.
Mix      input and output tokens are split with that model's daily prompt/completion counts: archived model-activity
         captures for history, the live 31-day window for recent days, else the model's average mix.
"""
import bisect, collections, csv, datetime as dt, glob, json, os, statistics as st, sys

sys.path.insert(0, os.path.dirname(__file__))
from parse_author import parse

START, END = "2026-06-01", "2026-10-31"
LIVE_FROM = "2026-10-01"   # live realized prices cover roughly the last 31 days
LIVE_DATE = "2026-11-01"   # date the live realized prices were read (data/prices/live_effective.json)
FREE_PREFIXES = ("stealth/", "openrouter/")


def stitch():
    labs = sorted(os.path.basename(f)[:-5] for f in glob.glob("data/raw/live/*.html"))
    tokens = collections.defaultdict(dict)
    for lab in labs:
        sources = [parse(open(f"data/raw/live/{lab}.html", "rb").read())]
        sources += [parse(open(f, "rb").read()) for f in sorted(glob.glob(f"data/raw/wayback/{lab}/*.html"), reverse=True)]
        have = {}
        for rows in sources:
            for d in sorted(rows)[:-1]:
                slot = have.setdefault(d, {})
                for m, v in rows[d].items():
                    if m.lower() in ("others", "other"):
                        continue
                    if m not in slot or (slot[m] == 0 and v > 0):
                        slot[m] = v
        for d, ms in have.items():
            if START <= d <= END:
                tokens[d].update(ms)
    return {d: tokens[d] for d in sorted(tokens)}


def is_free(m):
    return m.endswith(":free") or m.startswith(FREE_PREFIXES)


class Pricer:
    def __init__(self):
        self.live = json.load(open("data/prices/live_effective.json"))
        arch = json.load(open("data/prices/archived_effective.json"))
        self.arch = {m: sorted(pts) for m, pts in arch.items() if pts}
        self.act = json.load(open("data/prices/archived_activity.json"))

    def mix(self, m, day):
        for daily in (self.act.get(m) or {}, (self.live.get(m) or {}).get("daily") or {}):
            if day in daily and sum(daily[day]) > 0:
                p, c = daily[day]
                return p / (p + c)
        days = {**((self.live.get(m) or {}).get("daily") or {}), **(self.act.get(m) or {})}
        p = sum(v[0] for v in days.values()); c = sum(v[1] for v in days.values())
        return p / (p + c) if p + c else 0.97

    def price(self, m, day):
        """($ per token, source). Price points: every archived capture of the model (realized price over the ~7 days
        before it) plus today's live realized price as a point dated LIVE_DATE. The day's input/output price is
        interpolated linearly in time between the points on either side of it; beyond the first/last point the
        nearest one is used. Points more than 45 days away make the price an extrapolation."""
        if is_free(m):
            return 0.0, "free"
        r = self.live.get(m) or {}
        pts = [(dt.date.fromisoformat(p[0]), p[1], p[2], "archived") for p in self.arch.get(m) or []]
        if r.get("wIn") is not None:
            pts.append((dt.date.fromisoformat(LIVE_DATE), r["wIn"], r["wOut"], "live"))
        if not pts:
            return 0.0, "unpriced"
        pts.sort()
        t = dt.date.fromisoformat(day) + dt.timedelta(days=3)   # centre of the ~7-day window a capture describes
        before = [p for p in pts if p[0] <= t]; after = [p for p in pts if p[0] > t]
        if before and after:
            a, b = before[-1], after[0]; w = (t - a[0]).days / (b[0] - a[0]).days
            wi, wo = a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2])
            near = a if w < 0.5 else b; gap = min((t - a[0]).days, (b[0] - t).days)
        else:
            near = before[-1] if before else after[0]; wi, wo = near[1], near[2]; gap = abs((t - near[0]).days)
        share = self.mix(m, day)
        rate = (share * wi + (1 - share) * wo) / 1e6
        src = near[3] if near[3] == "archived" or day >= LIVE_FROM else "live"
        return rate, src if gap <= 45 else src + "-extrapolated"


def main():
    os.makedirs("results", exist_ok=True)
    tokens = stitch()
    pr = Pricer()
    rows, daily = [], []
    for d, ms in tokens.items():
        usd = {}
        for m, t in ms.items():
            rate, src = pr.price(m, d)
            usd[m] = t * rate
            rows.append({"date": d, "model": m, "tokens": int(t), "usd": round(t * rate, 2), "price_source": src})
        by_tok = sorted(ms, key=lambda m: -ms[m])[:10]
        by_usd = sorted(usd, key=lambda m: -usd[m])[:10]
        daily.append({"date": d, "tokens": int(sum(ms.values())), "usd_all": round(sum(usd.values()), 2),
                      "usd_top10_by_usd": round(sum(usd[m] for m in by_usd), 2),
                      "usd_top10_by_tokens": round(sum(usd[m] for m in by_tok), 2)})
    with open("results/daily_spend_by_model.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open("results/daily_series.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(daily[0])); w.writeheader(); w.writerows(daily)

    by_month = collections.defaultdict(list)
    for r in daily:
        by_month[r["date"][:7]].append(r)
    src_month = collections.defaultdict(collections.Counter)
    for r in rows:
        src_month[r["date"][:7]][r["price_source"]] += r["usd"]
    monthly, prev = [], {}
    for k in sorted(by_month):
        v = by_month[k]; n = len(v); rec = {"month": k, "days": n}
        for key in ("usd_all", "usd_top10_by_usd", "usd_top10_by_tokens", "tokens"):
            per = sum(x[key] for x in v) / n
            rec[f"{key}_total"] = round(sum(x[key] for x in v), 2)
            rec[f"{key}_per_day"] = round(per, 2)
            rec[f"{key}_mom_pct"] = round((per / prev[key] - 1) * 100, 1) if key in prev else None
            prev[key] = per
        rec["usd_per_million_tokens"] = round(rec["usd_all_per_day"] / rec["tokens_per_day"] * 1e6, 4)
        s = src_month[k]; tot = sum(s.values()) or 1
        rec["price_source_share"] = {a: round(b / tot, 4) for a, b in s.items()}
        monthly.append(rec)
    json.dump(monthly, open("results/monthly.json", "w"), indent=1)

    a = [r["usd_all"] for r in daily]; med = st.median(a)
    print("zero-dollar days:", [r["date"] for r in daily if r["usd_all"] <= 0])
    print("days outside 40%-180% of the median:", [(r["date"], round(r["usd_all"] / 1e6, 2)) for r in daily if not 0.4 * med <= r["usd_all"] <= 1.8 * med])
    print(f"\n{'month':8} {'days':>4} {'all $/day':>10} {'MoM':>7} {'top10$ $/day':>12} {'MoM':>7} {'top10tok $/day':>14} {'MoM':>7} {'tokens/day':>11} {'$/M tok':>8}  price source")
    for r in monthly:
        f = lambda x: "" if x is None else f"{x:+.1f}%"
        print(f"{r['month']:8} {r['days']:4d} {r['usd_all_per_day']/1e6:9.2f}M {f(r['usd_all_mom_pct']):>7} "
              f"{r['usd_top10_by_usd_per_day']/1e6:11.2f}M {f(r['usd_top10_by_usd_mom_pct']):>7} "
              f"{r['usd_top10_by_tokens_per_day']/1e6:13.2f}M {f(r['usd_top10_by_tokens_mom_pct']):>7} "
              f"{r['tokens_per_day']/1e12:10.2f}T {r['usd_per_million_tokens']:8.3f}  "
              + ", ".join(f"{k} {v:.0%}" for k, v in sorted(r["price_source_share"].items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
