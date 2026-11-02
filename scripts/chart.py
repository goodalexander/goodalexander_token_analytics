"""results/spend.png from results/daily_series.csv and results/monthly.json (needs matplotlib)."""
import csv, datetime as dt, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

R = list(csv.DictReader(open("results/daily_series.csv")))
M = json.load(open("results/monthly.json"))
x = [dt.date.fromisoformat(r["date"]) for r in R]
ma = lambda v, n=7: [sum(v[max(0, i - n + 1):i + 1]) / len(v[max(0, i - n + 1):i + 1]) for i in range(len(v))]

fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 9), dpi=150, gridspec_kw={"height_ratios": [3, 2]}, sharex=True)
for key, label, color in (("usd_all", "All models (16 labs, ~92% of OpenRouter tokens)", "#14181f"),
                          ("usd_top10_by_usd", "Top 10 models by dollars", "#1f5fa8"),
                          ("usd_top10_by_tokens", "Top 10 models by tokens (leaderboard)", "#c06a00")):
    v = [float(r[key]) / 1e6 for r in R]
    a1.plot(x, v, color=color, alpha=0.22, lw=1)
    a1.plot(x, ma(v), color=color, lw=2.2, label=f"{label}, 7-day avg")
for m in M:
    mid = dt.date.fromisoformat(m["month"] + "-15")
    txt = f"${m['usd_all_per_day']/1e6:.2f}M/day" + (f"\n{m['usd_all_mom_pct']:+.1f}% MoM" if m["usd_all_mom_pct"] is not None else "")
    a1.text(mid, 8.0, txt, ha="center", va="top", fontsize=9.5, fontweight="bold", color="#14181f")
a1.set_ylim(0, 8.2); a1.set_ylabel("\\$ millions per day")
a1.set_title("OpenRouter: dollars spent per day, Jun 1 - Oct 31 2026", loc="left", fontsize=14, fontweight="bold", pad=12)
a1.legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.84), fontsize=9)

tok = [int(r["tokens"]) / 1e12 for r in R]
ppm = [float(r["usd_all"]) / int(r["tokens"]) * 1e6 for r in R]
a2.plot(x, ma(tok), color="#7c8291", lw=2.2, label="Tokens per day (trillions), 7-day avg")
a2.set_ylabel("trillion tokens / day", color="#4a5160"); a2.set_ylim(0, None)
b2 = a2.twinx()
b2.plot(x, ma(ppm), color="#b42318", lw=2.2, label="Average price, \\$ per million tokens (right), 7-day avg")
b2.set_ylabel("\\$ per million tokens", color="#b42318"); b2.set_ylim(0, None)
h1, l1 = a2.get_legend_handles_labels(); h2, l2 = b2.get_legend_handles_labels()
a2.legend(h1 + h2, l1 + l2, frameon=False, loc="upper center", fontsize=9)
for ax in (a1, a2, b2):
    ax.spines["top"].set_visible(False)
a1.spines["right"].set_visible(False)
for ax in (a1, a2):
    ax.grid(axis="y", color="#ecebe5")
a2.xaxis.set_major_formatter(md.DateFormatter("%b %d"))
fig.text(0.01, 0.005, "Tokens: openrouter.ai lab pages (live + Wayback). Dollars: realized cache-blended prices (archived + live) x prompt/completion mix; "
         "free models = 0.  github.com/goodalexander/goodalexander_token_analytics",
         fontsize=7.2, color="#7c8291")
plt.tight_layout(rect=(0, 0.02, 1, 1))
plt.savefig("results/spend.png")
print("results/spend.png")
