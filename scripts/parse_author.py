"""Parse the 91-day daily per-model token chart embedded in an OpenRouter author page (live or Wayback capture)."""
import gzip, re, json, sys
def parse(raw: bytes) -> dict:
    try: txt = gzip.decompress(raw).decode("utf-8", "replace")
    except Exception: txt = raw.decode("utf-8", "replace")
    s2 = txt.replace('\\"', '"')
    rows = {}
    for x, ys in re.findall(r'\{"x":"([0-9-]+)[^"]*","ys":\{([^}]*)\}\}', s2):
        rows[x] = {k: float(v) for k, v in re.findall(r'"([^"]+)":([0-9.eE+-]+)', ys)}
    return rows
if __name__ == "__main__":
    r = parse(open(sys.argv[1], "rb").read())
    ds = sorted(r); print(len(r), ds[:1], ds[-1:], len({k for v in r.values() for k in v}))
