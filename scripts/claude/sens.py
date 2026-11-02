import runpy, sys, io, contextlib
from collections import defaultdict
sys.argv=['x']
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path('scripts/claude/spend.py')
daily, how_day, dates, quarter = g['daily'], g['how_day'], g['dates'], g['quarter']
for f in (0.8, 0.9, 1.0, 1.1, 1.2):
    Q = defaultdict(lambda: [0, 0])
    for d in dates:
        s = sum(v * (f if how_day[d][k] in ('interp', 'fallback') else 1) for k, v in daily[d].items() if k != 'Others')
        named = sum(v for k, v in daily[d].items() if k != 'Others')
        s *= sum(daily[d].values()) / named
        Q[quarter(d)][0] += s; Q[quarter(d)][1] += 1
    qs = sorted(Q); pd = [Q[q][0] / Q[q][1] for q in qs]
    print(f'interp x{f:.1f}: ' + '  '.join(f'{q[2:]} {100*(b/a-1):+.0f}%' for q, a, b in zip(qs[1:], pd, pd[1:])))
