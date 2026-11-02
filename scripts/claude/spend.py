"""Anthropic-on-OpenRouter dollar spend by quarter.

Daily spend per model = chart tokens (native basis) x realized $/token for that model-day.

Realized $/token comes from, in order of preference:
  volume    archived model pages through 2025-06-29 carry `volume` = dollars billed that day
  cache     later pages (and the live 31-day API) carry prompt/completion/cached tokens; priced at list
            with cache reads at the cache-read price and a cache-write uplift on uncached prompt,
            then calibrated to OpenRouter's realized prices (KCAL) where both exist
  effprice  archived effective-pricing API captures (Feb-Jun 2026): realized cache-weighted $/M over
            the 7 days before capture
  variant   :beta / :thinking listings priced at the base listing's same-day rate
  interp    linear in time between week-averaged anchors of the same model (<=120 days away)
  fallback  list price x the day's realized/list ratio across observed models
  others    the chart's "Others" bucket at the day's average $/token
"""
import json, re, gzip, glob, datetime, statistics, sys
from collections import defaultdict

T = json.load(open('data/claude/tokens.json'))
tokens, kappa, kappa_all = T['tokens'], T['kappa'], T['kappa_all']
REVISION = '20250808'   # pages captured before this report the old (pre-revision) token counts
LAST_DAY = '2026-10-25'

LP = {   # list $/M: input, output, cache read
 'claude-3-haiku': (0.25, 1.25, 0.03), 'claude-3-5-haiku': (0.8, 4, 0.08), 'claude-3-5-haiku-20241022': (0.8, 4, 0.08),
 'claude-3-sonnet': (3, 15, 0.3), 'claude-3-opus': (15, 75, 1.5),
 'claude-3.5-sonnet': (3, 15, 0.3), 'claude-3.5-sonnet-20240620': (3, 15, 0.3),
 'claude-3-7-sonnet-20250219': (3, 15, 0.3), 'claude-4-sonnet-20250522': (3, 15, 0.3),
 'claude-4-opus-20250522': (15, 75, 1.5), 'claude-4.1-opus-20250805': (15, 75, 1.5),
 'claude-4.5-sonnet-20250929': (3, 15, 0.3), 'claude-4.5-haiku-20251001': (1, 5, 0.1),
 'claude-4.5-opus-20251124': (5, 25, 0.5), 'claude-4.6-opus-20260205': (5, 25, 0.5),
 'claude-4.6-sonnet-20260217': (3, 15, 0.3), 'claude-4.7-opus-20260416': (5, 25, 0.5),
 'claude-4.8-opus-20260528': (5, 25, 0.5), 'claude-5-fable-20260609': (10, 50, 1.0),
 'claude-sonnet-5-20260630': (2, 10, 0.2), 'claude-opus-5-20260723': (5, 25, 0.5),
 'claude-fable-5.1-20260831': (10, 50, 0.25), 'claude-opus-5.5-20260921': (4, 20, 0.2),
 'claude-sonnet-5.5-20260928': (2, 10, 0.1), 'claude-haiku-5.5-20261007': (0.1, 0.5, 0.01),
 # fast mode is no longer listed; assumed 6x the base model (realized prices override where captured)
 'claude-4.6-opus-fast-20260407': (30, 150, 3), 'claude-4.7-opus-fast-20260512': (30, 150, 3),
 'claude-4.8-opus-fast-20260528': (30, 150, 3), 'claude-opus-5-fast-20260723': (30, 150, 3),
}
def base(key): return key.split('/')[-1].split(':')[0]
def lp(key): return LP[base(key)]
def D(s): return datetime.date.fromisoformat(s)

# ---------- cache-write uplift on uncached prompt, from live effective pricing ----------
cur = json.load(open('data/claude/cur.json'))
U = {}
for p, x in cur.items():
    ep = x.get('ep') or {}; b = base(p)
    if b in LP and ep.get('weightedInputPrice') and ep.get('weightedCacheHitRate', 0) < 0.97:
        i, o, cr = LP[b]; h = ep['weightedCacheHitRate']
        U[b] = min(max((ep['weightedInputPrice'] - cr * h) / (i * (1 - h)) - 1, 0), 0.3)
U_DEFAULT = statistics.median(U.values())
def kcost(key, P, C, K):
    i, o, cr = lp(key); u = U.get(base(key), U_DEFAULT)
    return ((P - K) * i * (1 + u) + K * cr + C * o) / 1e6

# ---------- per model-day records from archived pages + live API ----------
def load(f):
    raw = open(f, 'rb').read()
    try: raw = gzip.decompress(raw)
    except Exception: pass
    return raw.decode('utf-8', 'replace').replace('\\"', '"')
rec = defaultdict(dict)   # key -> date -> record
def put(key, d, P, C, K, V, new):
    if not P or P + (C or 0) <= 0: return
    r = rec[key].get(d)
    score = (V is not None, K is not None, new, P + (C or 0))
    if r is None or score > r['score']:
        rec[key][d] = dict(P=P, C=C or 0, K=K, V=V, new=new, score=score)
REC_RE = re.compile(r'\{[^{}]*"date":"([0-9-]+) 00:00:00","model_permaslug":"([^"]+)","variant":"([^"]+)"[^{}]*\}')
def num(s, k):
    m = re.search(r'"%s":([0-9.eE+-]+)' % k, s); return float(m.group(1)) if m else None
for f in sorted(glob.glob('data/claude/act/*.html')):
    ts = re.search(r'(\d{14})', f.split('/')[-1]).group(1)
    rows = [(m.group(1), m.group(2), m.group(3), m.group(0)) for m in REC_RE.finditer(load(f))]
    if not rows: continue
    last = max(r[0] for r in rows)          # capture day is partial: drop it
    for d, perm, var, s in rows:
        if d >= last: continue
        key = perm if var == 'standard' else perm + ':' + var
        put(key, d, num(s, 'total_prompt_tokens'), num(s, 'total_completion_tokens'),
            num(s, 'total_native_tokens_cached'), num(s, 'volume'), ts >= REVISION)
for p, x in cur.items():
    a = (x.get('ma') or {}).get('analytics') or []
    if not a: continue
    last = max(r['date'][:10] for r in a)
    for r in a:
        if r['date'][:10] < last:
            put(p, r['date'][:10], r['total_prompt_tokens'], r['total_completion_tokens'], r.get('total_native_tokens_cached') or 0, None, True)

def comp_share(key):
    rs = rec.get(key, {})
    P = sum(r['P'] for r in rs.values()); C = sum(r['C'] for r in rs.values())
    return C / (P + C) if P + C else 0.03
def list_blend(key):
    i, o, _ = lp(key); c = comp_share(key)
    return (i * (1 - c) + o * c) / 1e6

KCAL = 1.0
def rec_rate(key, d):
    """realized $ per native token from a page/API record, or (None, None)"""
    r = rec.get(key, {}).get(d)
    if not r: return None, None
    T_ = r['P'] + r['C']
    if r['V'] is not None:
        return r['V'] / T_ / (1 if r['new'] else kappa.get(key, kappa_all)), 'volume'
    if r['K'] is not None:
        return kcost(key, r['P'], r['C'], r['K']) * KCAL / T_, 'cache'   # ratio is basis-free
    return None, None

# ---------- archived effective-pricing captures ----------
EP = defaultdict(dict)
for f in sorted(glob.glob('data/claude/ep/*.json')):
    slug, var, ts = f.split('/')[-1][:-5].split('__')
    raw = open(f, 'rb').read()
    try: raw = gzip.decompress(raw)
    except Exception: pass
    try: e = json.loads(raw)['data']
    except Exception: continue
    if not e or not e.get('weightedInputPrice'): continue
    key = 'anthropic/' + slug + ('' if var == 'standard' else ':' + var)
    c = comp_share(key)
    rate = (e['weightedInputPrice'] * (1 - c) + e['weightedOutputPrice'] * c) / 1e6
    end = D(f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}')
    for i in range(1, 8):
        EP[key][str(end - datetime.timedelta(i))] = rate

# calibrate the cache formula to realized prices on overlapping model-days
_r = []
for k, dd in EP.items():
    for d, rate in dd.items():
        rr, how = rec_rate(k, d)
        if how == 'cache' and tokens.get(d, {}).get(k): _r.append(rr / rate)
KCAL = 1 / statistics.median(_r) if len(_r) >= 20 else 1.0
KCAL_N = len(_r)

dates = sorted(d for d in tokens if '2025-01-01' <= d <= LAST_DAY)

def direct_rate(k, d):
    r, h = rec_rate(k, d)
    if r is None and d in EP.get(k, {}): r, h = EP[k][d], 'effprice'
    return r, h

known = defaultdict(dict)    # key -> date -> (rate, weight tokens)
for d in dates:
    for k, v in tokens[d].items():
        if k == 'Others' or v <= 0: continue
        r, h = direct_rate(k, d)
        if r is not None: known[k][d] = (r, v)

def anchor(k, side_dates):
    """token-weighted mean rate over up to 7 known days nearest the gap edge"""
    pts = [known[k][x] for x in side_dates[:7]]
    return sum(r * w for r, w in pts) / sum(w for r, w in pts)
def interp(k, d, win=120):
    kd = known.get(k)
    if not kd: return None
    xs = sorted(kd)
    before = [x for x in xs if x < d][::-1]; after = [x for x in xs if x > d]
    db = (D(d) - D(before[0])).days if before else 10**9
    da = (D(after[0]) - D(d)).days if after else 10**9
    if db <= win and da <= win:
        w = db / (db + da); return anchor(k, before) * (1 - w) + anchor(k, after) * w
    if db <= win: return anchor(k, before)
    if da <= win: return anchor(k, after)
    return None

RD0 = {}
for d in dates:
    num_ = den = 0
    for k, v in tokens[d].items():
        if k in known and d in known[k]: num_ += v * known[k][d][0]; den += v * list_blend(k)
    RD0[d] = num_ / den if den else None
def nearest_rd(d):
    xs = [x for x in RD0 if RD0[x] is not None]
    return RD0[min(xs, key=lambda x: abs((D(x) - D(d)).days))]

def quarter(d): return f'{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}'
daily, how_day = {}, {}
for d in dates:
    row = tokens[d]; spend = {}; how = {}
    for k, v in row.items():
        if k == 'Others' or v <= 0: continue
        r, h = direct_rate(k, d)
        if r is None and ':' in k:
            r, h = direct_rate(k.split(':')[0], d); h = 'variant' if r is not None else None
        if r is None:
            r = interp(k, d); h = 'interp' if r is not None else None
        if r is None:
            r, h = list_blend(k) * (RD0[d] or nearest_rd(d)), 'fallback'
        spend[k] = v * r; how[k] = h
    named = sum(v for k, v in row.items() if k != 'Others')
    if row.get('Others'):
        spend['Others'] = row['Others'] * sum(spend.values()) / named; how['Others'] = 'others'
    daily[d] = spend; how_day[d] = how

def report(group, label):
    agg = defaultdict(lambda: dict(spend=0, days=0, tok=0, listp=0, how=defaultdict(float)))
    for d in dates:
        g = group(d); a = agg[g]
        a['spend'] += sum(daily[d].values()); a['days'] += 1; a['tok'] += sum(tokens[d].values())
        named = {k: v for k, v in tokens[d].items() if k != 'Others'}
        a['listp'] += sum(v * list_blend(k) for k, v in named.items()) * sum(tokens[d].values()) / sum(named.values())
        for k, s in daily[d].items(): a['how'][how_day[d][k]] += s
    print(f"{label:7s} {'days':>4s} {'spend $M':>9s} {'$k/day':>8s} {'growth':>8s} {'index':>6s} {'tokB/d':>7s} {'$/Mtok':>6s} {'list$k/d':>9s} {'list gr':>8s}  observed/estimated")
    idx, prev, prevl = 100, None, None
    for g in sorted(agg):
        a = agg[g]; pd = a['spend'] / a['days']; pl = a['listp'] / a['days']
        gr = pd / prev - 1 if prev else None
        if gr is not None: idx *= 1 + gr
        obs = sum(a['how'][h] for h in ('volume', 'cache', 'effprice', 'variant')) / a['spend']
        mix = ' '.join(f"{h}={a['how'][h]/a['spend']:.0%}" for h in ('volume', 'cache', 'effprice', 'variant', 'interp', 'fallback', 'others') if a['how'][h] / a['spend'] >= 0.005)
        print(f"{g:7s} {a['days']:4d} {a['spend']/1e6:9.2f} {pd/1e3:8.0f} {('%+.1f%%' % (100*gr)) if gr is not None else '':>8s} {idx:6.0f} {a['tok']/a['days']/1e9:7.0f} {a['spend']/a['tok']*1e6:6.2f} {pl/1e3:9.0f} {('%+.1f%%' % (100*(pl/prevl-1))) if prevl else '':>8s}  obs {obs:.0%} | {mix}")
        prev, prevl = pd, pl
    return agg

if __name__ == '__main__':
    Q = report(quarter, 'qtr')
    if '-m' in sys.argv: print(); report(lambda d: d[:7], 'month')
    if '-v' in sys.argv:
        byq = defaultdict(lambda: defaultdict(float))
        for d in dates:
            for k, s in daily[d].items(): byq[quarter(d)][base(k)] += s
        for q in sorted(byq):
            tot = sum(byq[q].values())
            print(q, ' '.join(f"{k[:26]}={v/tot:.0%}" for k, v in sorted(byq[q].items(), key=lambda x: -x[1])[:6]))
        print('KCAL %.4f from %d model-days; U default %.3f' % (KCAL, KCAL_N, U_DEFAULT))
    json.dump(daily, open('data/claude/daily_spend.json', 'w'))
