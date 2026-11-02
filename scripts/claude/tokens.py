"""Merge Anthropic daily token charts (OpenRouter author page, live + Wayback) into one series on the
post-Aug-2025 (native-token) basis. Output: tokens.json {date: {key: tokens_native}} plus diagnostics."""
import json, statistics
from collections import defaultdict

snaps = json.load(open('data/claude/snap_rows.json'))
snaps['99999999live'] = json.load(open('data/claude/ant_author_chart.json'))
snaps = {k: v for k, v in snaps.items() if v}
REVISION = '20250808'   # snapshots on/after this date carry the revised (native) counts

def is_new(ts): return ts >= REVISION

by_date = defaultdict(dict)   # date -> ts -> rows (full days only)
for ts, rows in snaps.items():
    last = max(rows)
    for d, r in rows.items():
        if d != last:
            by_date[d][ts] = r

# kappa per model: new/old ratio on overlap dates (old = 20250715 snapshot, new = 20250808)
old, new = snaps['20250715151119'], snaps['20250808191216']
ratios = defaultdict(list)
for d in old:
    if d in new and d != max(old) and d != max(new):
        for k, v in old[d].items():
            if k in new[d] and v > 1e8:
                ratios[k].append(new[d][k] / v)
kappa = {k: statistics.median(v) for k, v in ratios.items() if len(v) >= 10}
tot_ratio = [sum(new[d].values()) / sum(old[d].values()) for d in old if d in new and d != max(old) and d != max(new)]
kappa_all = statistics.median(tot_ratio)

out, meta = {}, {}
for d in sorted(by_date):
    cands = by_date[d]
    newc = {ts: r for ts, r in cands.items() if is_new(ts)}
    pool = newc or cands
    # fewest tokens hidden in "Others"; ties -> latest snapshot
    ts = min(pool, key=lambda t: (pool[t].get('Others', 0) / sum(pool[t].values()), -int(t[:8])))
    r = pool[ts]
    if not is_new(ts):
        r = {k: v * kappa.get(k, kappa_all) for k, v in r.items()}
    out[d] = r
    meta[d] = dict(ts=ts, basis='new' if is_new(ts) else 'old->new', others=r.get('Others', 0) / sum(r.values()))

json.dump(dict(tokens=out, meta=meta, kappa=kappa, kappa_all=kappa_all), open('data/claude/tokens.json', 'w'))
if __name__ == '__main__':
    ds = sorted(out)
    import datetime
    d0, d1 = datetime.date.fromisoformat(ds[0]), datetime.date.fromisoformat(ds[-1])
    missing = [str(d0 + datetime.timedelta(i)) for i in range((d1 - d0).days + 1) if str(d0 + datetime.timedelta(i)) not in out]
    print('range', ds[0], ds[-1], 'days', len(ds), 'missing', missing)
    print('kappa_all %.3f' % kappa_all, {k.split('/')[-1]: round(v, 3) for k, v in kappa.items()})
    tot = {d: sum(r.values()) for d, r in out.items()}
    zeros = [d for d, t in tot.items() if t <= 0]
    print('zero days', zeros)
    # day-over-day jumps > 40% (possible partial / bad rows)
    for a, b in zip(ds, ds[1:]):
        if tot[a] > 0 and abs(tot[b] / tot[a] - 1) > 0.4:
            print('jump', a, b, round(tot[a] / 1e9, 1), round(tot[b] / 1e9, 1), meta[a]['ts'], meta[b]['ts'])
    others = [m['others'] for m in meta.values()]
    print('Others share median %.3f max %.3f' % (statistics.median(others), max(others)))
