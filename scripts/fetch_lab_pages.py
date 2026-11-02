"""Download OpenRouter lab pages: live (data/raw/live/<lab>.html) and, for history, Wayback captures
(data/raw/wayback/<lab>/<timestamp>.html) chosen so consecutive 91-day windows overlap back to START.

    python3 scripts/fetch_lab_pages.py                 # all labs in LABS
    python3 scripts/fetch_lab_pages.py deepseek openai # some labs

Serial and slow on purpose: the Wayback Machine throttles (~1 request / 4 s) and its index fails under parallel load."""
import datetime as dt, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from parse_author import parse
LABS = ["anthropic", "arcee-ai", "deepseek", "google", "minimax", "moonshotai", "nvidia", "openai", "openrouter", "qwen",
        "stealth", "stepfun", "tencent", "x-ai", "xiaomi", "z-ai"]   # every lab with a model in OpenRouter's weekly top models
START = dt.date(2026, 5, 25)
H = {"User-Agent": "Mozilla/5.0 (research; low rate)"}
def get(url, tries=6):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=90).read()
        except Exception: time.sleep(15 * (i + 1))
    raise RuntimeError("gave up: " + url)
D = lambda t: dt.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
for lab in sys.argv[1:] or LABS:
    os.makedirs("data/raw/live", exist_ok=True); os.makedirs(f"data/raw/wayback/{lab}", exist_ok=True)
    open(f"data/raw/live/{lab}.html", "wb").write(get(f"https://openrouter.ai/{lab}")); time.sleep(2)
    live = parse(open(f"data/raw/live/{lab}.html", "rb").read())
    need = min(dt.date.fromisoformat(d) for d in live) if live else dt.date.today()
    caps = [r[0] for r in json.loads(get(f"https://web.archive.org/cdx/search/cdx?url=openrouter.ai/{lab}&output=json&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:8"))[1:]]
    time.sleep(5)
    while need > START:
        cands = [t for t in caps if need - dt.timedelta(days=1) <= D(t) <= need + dt.timedelta(days=85)]
        if not cands:
            print(f"{lab}: no capture overlaps {need}"); break
        t = cands[0]; path = f"data/raw/wayback/{lab}/{t}.html"
        if not os.path.exists(path):
            open(path, "wb").write(get(f"https://web.archive.org/web/{t}id_/https://openrouter.ai/{lab}")); time.sleep(5)
        rows = parse(open(path, "rb").read())
        first = min(dt.date.fromisoformat(d) for d in rows) if rows else need
        caps.remove(t)
        if rows and first < need: need = first
    print(f"{lab}: covered back to {need}")
