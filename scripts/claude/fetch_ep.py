import re, subprocess, time, os, collections, datetime
os.makedirs('data/claude/ep', exist_ok=True)
c = collections.defaultdict(list)
for l in open('data/claude/cdx_ep.txt'):
    ts, u = l.split()
    m = re.search(r'permaslug=anthropic%2F([^&]+)&variant=(\w+)', u)
    if m: c[(m.group(1), m.group(2))].append((ts, u))
dt = lambda t: datetime.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
for (slug, var), L in c.items():
    L.sort(); picked = []
    for ts, u in L:
        if not picked or (dt(ts) - dt(picked[-1][0])).days >= 6: picked.append((ts, u))
    for ts, u in picked:
        out = f'data/claude/ep/{slug}__{var}__{ts}.json'
        if os.path.exists(out) and os.path.getsize(out) > 50: continue
        for i in range(3):
            subprocess.run(['curl', '-s', '-L', '--max-time', '90', '-o', out, f'http://web.archive.org/web/{ts}id_/{u}'])
            if os.path.exists(out) and os.path.getsize(out) > 50: break
            time.sleep(15)
        print(slug, var, ts, os.path.getsize(out) if os.path.exists(out) else 0, flush=True)
        time.sleep(4)
print('DONE', flush=True)
