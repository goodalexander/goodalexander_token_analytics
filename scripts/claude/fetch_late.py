"""Aug-Oct 2026 model pages embed only 31 days of analytics: fetch one capture every ~25 days from mid-Aug."""
import subprocess, json, time, os, sys, datetime
def cdx(path):
    for i in range(5):
        r = subprocess.run(['curl', '-s', '--max-time', '90', f'http://web.archive.org/cdx/search/cdx?url={path}&output=json&filter=statuscode:200&fl=timestamp&from=20260801'], capture_output=True, text=True).stdout
        try: return [x[0] for x in json.loads(r)[1:]]
        except Exception: time.sleep(10 * (i + 1))
    print('cdx fail', path, flush=True); return []
dt = lambda t: datetime.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
for slug in sys.argv[1:]:
    allts = []
    for tag, path in [('act', f'openrouter.ai/anthropic/{slug}/activity'), ('page', f'openrouter.ai/anthropic/{slug}')]:
        allts += [(t, tag, path) for t in cdx(path) if t >= '20260815']; time.sleep(4)
    allts.sort(); picked = []
    for t, tag, path in allts:
        if not picked or (dt(t) - dt(picked[-1][0])).days >= 25: picked.append((t, tag, path))
    print(slug, len(allts), '->', [p[0][:8] for p in picked], flush=True)
    for t, tag, path in picked:
        out = f'data/claude/act/{slug}__{tag}__{t}.html'
        if os.path.exists(out) and os.path.getsize(out) > 5000: continue
        for i in range(3):
            subprocess.run(['curl', '-s', '-L', '--max-time', '120', '-o', out, f'http://web.archive.org/web/{t}id_/https://{path}'])
            if os.path.exists(out) and os.path.getsize(out) > 5000: break
            time.sleep(15)
        time.sleep(4)
print('DONE', flush=True)
