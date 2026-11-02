import gzip, re, json, glob, os, sys
out={}
for f in sorted(glob.glob('*.html')):
    raw=open(f,'rb').read()
    try: txt=gzip.decompress(raw).decode('utf-8','replace')
    except Exception: txt=raw.decode('utf-8','replace')
    s2=txt.replace('\\"','"')
    m=re.findall(r'\{"x":"([0-9-]+)[^"]*","ys":\{([^}]*)\}\}', s2)
    rows={}
    for x,ys in m:
        rows[x]={k:float(v) for k,v in re.findall(r'"([^"]+)":([0-9.eE+-]+)', ys)}
    ts=f[:-5]
    if rows:
        ds=sorted(rows)
        print(ts, len(rows), ds[0], ds[-1], len(set(k for r in rows.values() for k in r)))
    else:
        print(ts, 'NO CHART', len(txt))
    out[ts]=rows
json.dump(out,open('snap_rows.json','w'))
