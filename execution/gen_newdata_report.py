"""
Generate detailed HTML report for 2026 new data test.
Shows every trade: entry/exit/result on price chart + trade table.
"""
import pandas as pd
import numpy as np
import os
import json
import base64
import io

OUTPUT_DIR = "output"
PATH = "dati/27 febbraio.txt"
LOOKBACK = 5
ST_PERIOD = 30
ST_MULT = 1.5

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns = ["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df[c] = df[c].astype(float)
df["ora"] = pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
n = len(df)

high, low, close = df["high"].values, df["low"].values, df["close"].values
tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
tr[0] = high[0] - low[0]
atr = np.zeros(n); alpha = 1/ST_PERIOD; atr[0] = tr[0]
for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
hl2 = (high + low) / 2
basic_ub = hl2 + ST_MULT * atr; basic_lb = hl2 - ST_MULT * atr
final_ub = np.zeros(n); final_lb = np.zeros(n); st = np.zeros(n)
direction = np.ones(n, dtype=int)
for i in range(n):
    if i == 0:
        final_ub[i] = basic_ub[i]; final_lb[i] = basic_lb[i]
        st[i] = final_ub[i]; direction[i] = -1; continue
    pc = close[i-1]
    final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i-1] or pc > final_ub[i-1]) else final_ub[i-1]
    final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i-1] or pc < final_lb[i-1]) else final_lb[i-1]
    if st[i-1] == final_ub[i-1]:
        if close[i] > final_ub[i]: st[i] = final_lb[i]; direction[i] = 1
        else: st[i] = final_ub[i]; direction[i] = -1
    else:
        if close[i] < final_lb[i]: st[i] = final_ub[i]; direction[i] = -1
        else: st[i] = final_lb[i]; direction[i] = 1

ph_flag = np.full(n, False); pl_flag = np.full(n, False)
for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i,"high"] > df.loc[i-k,"high"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i,"high"] > df.loc[i+k,"high"] for k in range(1, LOOKBACK+1)):
        ph_flag[i] = True
    if all(df.loc[i,"low"] < df.loc[i-k,"low"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i,"low"] < df.loc[i+k,"low"] for k in range(1, LOOKBACK+1)):
        pl_flag[i] = True

ph_prev = [None]*n; pl_prev = [None]*n
lp = None; ll = None
for i in range(n):
    if ph_flag[i]: lp = float(df.loc[i,"high"])
    if pl_flag[i]: ll = float(df.loc[i,"low"])
    ph_prev[i] = lp; pl_prev[i] = ll

ph_next = [None]*n; pl_next = [None]*n
np_h = None; np_l = None
for i in range(n-1, -1, -1):
    if ph_flag[i]: np_h = float(df.loc[i,"high"])
    if pl_flag[i]: np_l = float(df.loc[i,"low"])
    ph_next[i] = np_h; pl_next[i] = np_l

# Signals + simulate
signals = []
for i in range(ST_PERIOD + 2, n):
    prev = direction[i-1]; pprev = direction[i-2]
    if prev == 1 and pprev == -1: dir_label = "LONG"
    elif prev == -1 and pprev == 1: dir_label = "SHORT"
    else: continue
    entry = round(float(df.loc[i,"open"]), 2)
    atr_v = float(atr[i-1])
    if dir_label == "LONG":
        pl = pl_prev[i]
        if pl is None: continue
        sl = round(pl - 0.5 * atr_v, 2)
        tp = round(ph_next[i], 2) if ph_next[i] is not None else round(entry + abs(entry-sl), 2)
    else:
        ph = ph_prev[i]
        if ph is None: continue
        sl = round(ph + 0.5 * atr_v, 2)
        tp = round(pl_next[i], 2) if pl_next[i] is not None else round(entry - abs(sl-entry), 2)
    if sl is None or tp is None: continue
    if (dir_label == "LONG" and sl >= entry) or (dir_label == "SHORT" and sl <= entry): continue
    if dir_label == "LONG" and tp <= entry: tp = round(entry + abs(entry - sl), 2)
    if dir_label == "SHORT" and tp >= entry: tp = round(entry - abs(sl - entry), 2)
    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp - entry), 2)
    rr = round(reward/risk, 2) if risk > 0 else 0

    # Simulate
    idx = df[df["ora"] == pd.to_datetime(df.loc[i,"ora"])].index[0]
    result = None; exit_p = None; exit_date = None; exit_idx = None
    for j in range(idx+1, n):
        if dir_label == "LONG":
            if df.loc[j,"low"] <= sl: result = "SL"; exit_p = sl; exit_idx = j; break
            if df.loc[j,"high"] >= tp: result = "TP"; exit_p = tp; exit_idx = j; break
        else:
            if df.loc[j,"high"] >= sl: result = "SL"; exit_p = sl; exit_idx = j; break
            if df.loc[j,"low"] <= tp: result = "TP"; exit_p = tp; exit_idx = j; break
    if result is None or exit_p is None: continue
    pnl = round(exit_p - entry, 2) if dir_label == "LONG" else round(entry - exit_p, 2)
    pnl_eur = round(pnl * 1000 - 6, 2)
    bars_held = exit_idx - i

    signals.append({
        "entry_date": df.loc[i,"ora"].strftime("%d/%m/%Y %H:%M"),
        "exit_date": df.loc[exit_idx,"ora"].strftime("%d/%m/%Y %H:%M"),
        "dir": dir_label, "entry": entry, "sl": sl, "tp": tp, "exit": round(exit_p, 2),
        "risk": risk, "reward": reward, "rr": rr,
        "result": result, "pnl": pnl, "pnl_eur": pnl_eur, "bars": bars_held,
        "entry_idx": i, "exit_idx": exit_idx
    })

total = len(signals)
wins = sum(1 for s in signals if s["result"] == "TP")
losses = total - wins
total_pnl = sum(s["pnl"] for s in signals)
total_pnl_eur = sum(s["pnl_eur"] for s in signals)
win_rate = wins/total*100
avg_win = np.mean([s["pnl"] for s in signals if s["result"]=="TP"]) if wins else 0
avg_loss = np.mean([s["pnl"] for s in signals if s["result"]=="SL"]) if losses else 0
max_win = max(s["pnl"] for s in signals) if signals else 0
max_loss = min(s["pnl"] for s in signals) if signals else 0
profit_factor = abs(sum(s["pnl"] for s in signals if s["result"]=="TP") / sum(s["pnl"] for s in signals if s["result"]=="SL")) if losses else 999
avg_bars = np.mean([s["bars"] for s in signals])

# Equity curve
equity = [0]
for s in signals:
    equity.append(equity[-1] + s["pnl_eur"])

# Generate price series for chart
price_data = []
for i in range(n):
    price_data.append([df.loc[i,"ora"].strftime("%d/%m %H:%M"),
                       round(float(high[i]),2),
                       round(float(low[i]),2),
                       round(float(df.loc[i,"open"]),2),
                       round(float(close[i]),2)])

def build_chart_data(price_data, signals):
    """Build lightweight price chart data with trade markers"""
    pts = []
    px = price_data
    # Only use every Nth candle for performance if needed
    for i, p in enumerate(px):
        pts.append({"t": p[0], "o": p[3], "h": p[1], "l": p[2], "c": p[4]})
    markers = []
    for s in signals:
        ei = s["entry_idx"]
        xi = s["exit_idx"]
        col = "#3fb950" if s["result"] == "TP" else "#f85149"
        markers.append({
            "entry_idx": ei, "exit_idx": xi,
            "entry_price": s["entry"], "exit_price": s["exit"],
            "sl": s["sl"], "tp": s["tp"],
            "dir": s["dir"], "result": s["result"],
            "pnl": s["pnl"], "pnl_eur": s["pnl_eur"],
            "entry_date": s["entry_date"], "exit_date": s["exit_date"],
            "bars": s["bars"], "color": col
        })
    return {"candles": pts, "markers": markers, "count": len(pts)}

chart = build_chart_data(price_data, signals)

html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test Nuovi Dati 2026 — BTP 1h ST(30,1.5)+Pivot</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family:'Segoe UI',-apple-system,sans-serif;
    background:#0d1117; color:#c9d1d9;
    padding:30px; max-width:1400px; margin:0 auto;
    line-height:1.6;
}}
h1 {{ color:#58a6ff; font-size:1.6em; margin-bottom:2px; }}
.subtitle {{ color:#8b949e; font-size:0.85em; margin-bottom:20px; }}
h2 {{ color:#79c0ff; font-size:1.15em; margin:28px 0 12px; border-bottom:1px solid #21262d; padding-bottom:6px; }}

.stats-grid {{
    display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
    gap:10px; margin-bottom:20px;
}}
.stat-card {{
    background:#161b22; border:1px solid #21262d; border-radius:6px;
    padding:12px; text-align:center;
}}
.stat-card .label {{ color:#8b949e; font-size:0.7em; text-transform:uppercase; letter-spacing:0.3px; }}
.stat-card .value {{ color:#f0f6fc; font-size:1.3em; font-weight:700; }}
.stat-card .sub {{ color:#8b949e; font-size:0.75em; }}

table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:0.82em; }}
th {{ background:#1c2128; color:#8b949e; font-weight:600; text-align:right; padding:6px 8px; border-bottom:2px solid #30363d; }}
th:first-child {{ text-align:left; }}
td {{ padding:5px 8px; border-bottom:1px solid #21262d; text-align:right; }}
td:first-child {{ text-align:left; }}
tr:hover td {{ background:#1c2128; }}
.num {{ font-family:'Consolas',monospace; }}

.chart-container {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:15px; margin:16px 0; }}
#chart {{ width:100%; height:600px; }}

.trade-tag {{ display:inline-block; padding:1px 8px; border-radius:10px; font-size:0.75em; font-weight:600; }}
.tag-win {{ background:#3fb95033; color:#3fb950; }}
.tag-loss {{ background:#f8514933; color:#f85149; }}
.tag-long {{ background:#58a6ff33; color:#58a6ff; }}
.tag-short {{ background:#f0883e33; color:#f0883e; }}

.verdict {{
    border-radius:6px; padding:14px 18px; margin:16px 0;
    border-left:4px solid #3fb950; background:#3fb95022;
}}
.verdict-label {{ color:#3fb950; font-weight:700; font-size:1.05em; }}

.detail-card {{
    background:#161b22; border:1px solid #21262d; border-radius:6px;
    padding:14px; margin-bottom:8px;
}}
.detail-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
.detail-title {{ font-weight:600; }}
.detail-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(100px,1fr)); gap:8px; font-size:0.85em; }}
.detail-item .dl {{ color:#8b949e; font-size:0.75em; }} .detail-item .dd {{ font-weight:600; }}

.footer {{ text-align:center; color:#484f58; font-size:0.75em; margin-top:40px; padding-top:16px; border-top:1px solid #21262d; }}
</style>
</head>
<body>

<h1>Test Nuovi Dati 2026 — BTP Future 1h</h1>
<div class="subtitle">ST(30, 1.5) + Pivot Trailing (lookback=5) · 27/02/2026 → 28/05/2026 · {len(price_data)} candele</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="label">Trade</div>
        <div class="value">{total}</div>
        <div class="sub">in 3 mesi</div>
    </div>
    <div class="stat-card">
        <div class="label" style="color:#3fb950;">Win Rate</div>
        <div class="value" style="color:#3fb950;">{win_rate:.0f}%</div>
        <div class="sub">{wins}V / {losses}P</div>
    </div>
    <div class="stat-card">
        <div class="label">PnL Netto</div>
        <div class="value" style="color:#3fb950;">{total_pnl_eur:+.0f}</div>
        <div class="sub">EUR</div>
    </div>
    <div class="stat-card">
        <div class="label">Profit Factor</div>
        <div class="value" style="color:#3fb950;">{profit_factor:.1f}</div>
        <div class="sub"></div>
    </div>
    <div class="stat-card">
        <div class="label">Avg Win</div>
        <div class="value" style="color:#3fb950;">+{avg_win*1000-6:.0f}</div>
        <div class="sub">EUR</div>
    </div>
    <div class="stat-card">
        <div class="label" style="color:#f85149;">Avg Loss</div>
        <div class="value" style="color:#f85149;">{avg_loss*1000-6:.0f}</div>
        <div class="sub">EUR</div>
    </div>
    <div class="stat-card">
        <div class="label">Max Win</div>
        <div class="value" style="color:#3fb950;">{max_win*1000-6:.0f}</div>
        <div class="sub">EUR</div>
    </div>
    <div class="stat-card">
        <div class="label" style="color:#f85149;">Max Loss</div>
        <div class="value" style="color:#f85149;">{max_loss*1000-6:.0f}</div>
        <div class="sub">EUR</div>
    </div>
    <div class="stat-card">
        <div class="label">Avg Bars</div>
        <div class="value">{avg_bars:.1f}</div>
        <div class="sub">candele</div>
    </div>
</div>

<h2>Performance Chart</h2>
<div class="chart-container">
    <canvas id="priceChart"></canvas>
</div>

<h2>Equity Curve</h2>
<div class="chart-container">
    <canvas id="equityChart"></canvas>
</div>

<h2>Tutti i Trade ({total})</h2>
<table>
<thead><tr>
    <th>#</th><th>Entry</th><th>Exit</th><th>Dir</th><th>Entry</th><th>Exit</th><th>SL</th><th>TP</th><th>Bars</th><th>Rischio</th><th>Reward</th><th>R/R</th><th>Risultato</th><th>PnL</th>
</tr></thead>
<tbody>"""

for k, s in enumerate(signals):
    cls = "tag-win" if s["result"]=="TP" else "tag-loss"
    dir_cls = "tag-long" if s["dir"]=="LONG" else "tag-short"
    html += f"""<tr>
    <td>{k+1}</td>
    <td class="num">{s["entry_date"]}</td>
    <td class="num">{s["exit_date"]}</td>
    <td><span class="trade-tag {dir_cls}">{s["dir"]}</span></td>
    <td class="num">{s["entry"]:.2f}</td>
    <td class="num">{s["exit"]:.2f}</td>
    <td class="num">{s["sl"]:.2f}</td>
    <td class="num">{s["tp"]:.2f}</td>
    <td class="num">{s["bars"]}</td>
    <td class="num">{s["risk"]:.2f}</td>
    <td class="num">{s["reward"]:.2f}</td>
    <td class="num">{s["rr"]:.2f}</td>
    <td><span class="trade-tag {cls}">{s["result"]}</span></td>
    <td class="num" style="color:{'#3fb950' if s['pnl']>0 else '#f85149'}">{s["pnl"]:+.2f}pt ({s["pnl_eur"]:+.0f})</td>
</tr>"""

html += """</tbody>
</table>

<div class="verdict">
<div class="verdict-label">Risultato: """ + (f"+{total_pnl:.2f}" if total_pnl > 0 else f"{total_pnl:.2f}") + f""" pt ({total_pnl_eur:+.0f} EUR netti)</div>
<div style="margin-top:6px; color:#c9d1d9; font-size:0.9em;">
    {wins} vittorie ({win_rate:.0f}%) · {losses} perdite ({100-win_rate:.0f}%) su {total} trade in 3 mesi · Profit Factor {profit_factor:.1f}
</div>
</div>

<div class="footer">
Generato il 28/05/2026 · Dati: 27/02/2026 → 28/05/2026 · BTP Future 1h
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script>
(function() {{
const chartData = """ + json.dumps(chart) + """;

// --- Price chart with trade markers ---
const ctxPrice = document.getElementById('priceChart').getContext('2d');
const candlestickPlugin = {{
    id: 'candlestick',
    beforeDraw: function(cchart) {{
        const ctx = cchart.ctx;
        const meta = cchart.getDatasetMeta(0);
        const data = cchart.data.datasets[0].data;
        if (!meta || !meta.data) return;

        const markers = cchart.markers || [];
        const yScale = cchart.scales.y;
        const xScale = cchart.scales.x;

        // Draw candles
        const barWidth = Math.max(1, (xScale.getPixelForValue(1) - xScale.getPixelForValue(0)) * 0.7);

        for (let i = 0; i < data.length; i++) {{
            const c = data[i];
            const x = xScale.getPixelForValue(i);
            if (x < -50 || x > ctx.canvas.width + 50) continue;

            const open = yScale.getPixelForValue(c.o);
            const close = yScale.getPixelForValue(c.c);
            const high = yScale.getPixelForValue(c.h);
            const low = yScale.getPixelForValue(c.l);
            const isUp = c.c >= c.o;

            ctx.strokeStyle = isUp ? '#3fb950' : '#f85149';
            ctx.fillStyle = isUp ? '#3fb950' : '#f85149';
            ctx.lineWidth = 1;

            // Wick
            ctx.beginPath();
            ctx.moveTo(x, high);
            ctx.lineTo(x, low);
            ctx.stroke();

            // Body
            const yTop = isUp ? close : open;
            const yBot = isUp ? open : close;
            const bodyH = Math.max(1, yBot - yTop);
            ctx.fillRect(x - barWidth/2, yTop, barWidth, bodyH);
        }}

        // Draw markers (entry/exit arrows)
        if (markers.length === 0) return;
        ctx.save();
        for (const m of markers) {{
            const ex = xScale.getPixelForValue(m.entry_idx);
            const ey = yScale.getPixelForValue(m.entry_price);
            const xx = xScale.getPixelForValue(m.exit_idx);
            const xy = yScale.getPixelForValue(m.exit_price);

            // Entry arrow
            ctx.beginPath();
            ctx.fillStyle = m.dir === 'LONG' ? '#58a6ff' : '#f0883e';
            if (m.dir === 'LONG') {{
                ctx.moveTo(ex - 6, ey + 8);
                ctx.lineTo(ex, ey - 2);
                ctx.lineTo(ex + 6, ey + 8);
            }} else {{
                ctx.moveTo(ex - 6, ey - 8);
                ctx.lineTo(ex, ey + 2);
                ctx.lineTo(ex + 6, ey - 8);
            }}
            ctx.fill();

            // Line from entry to exit
            ctx.strokeStyle = m.color;
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(ex, ey);
            ctx.lineTo(xx, xy);
            ctx.stroke();
            ctx.setLineDash([]);

            // Exit circle
            ctx.beginPath();
            ctx.arc(xx, xy, 4, 0, Math.PI*2);
            ctx.fillStyle = m.color;
            ctx.fill();
        }}
        ctx.restore();
    }}
}};

const labels = chartData.candles.map((_, i) => i);
const priceData = chartData.candles;
new Chart(ctxPrice, {{
    type: 'line',
    data: {{
        labels: labels,
        datasets: [{{
            data: priceData,
            borderColor: 'transparent',
            pointRadius: 0,
            parsing: false
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                callbacks: {{
                    label: function(ctx) {{
                        const i = ctx.dataIndex;
                        const c = priceData[i];
                        if (!c) return '';
                        return `${{c.t}} O:${{c.o}} H:${{c.h}} L:${{c.l}} C:${{c.c}}`;
                    }}
                }}
            }}
        }},
        scales: {{
            x: {{
                display: true,
                ticks: {{
                    color: '#8b949e',
                    maxTicksLimit: 30,
                    callback: function(v, i) {{
                        const c = priceData[Math.round(v)];
                        return c ? c.t : '';
                    }}
                }},
                grid: {{ color: '#21262d' }}
            }},
            y: {{
                display: true,
                ticks: {{ color: '#8b949e' }},
                grid: {{ color: '#21262d' }},
                reverse: false
            }}
        }}
    }},
    plugins: [candlestickPlugin]
}});

// Cleanup: get the instance and set markers
const priceChartInstance = Chart.getChart('priceChart');
if (priceChartInstance) {{
    priceChartInstance.markers = chartData.markers;
    priceChartInstance.update();
}}

// --- Equity curve ---
document.getElementById('equityChart').height = 300;
new Chart(document.getElementById('equityChart'), {{
    type: 'line',
    data: {{
        labels: [''].concat(chartData.markers.map(m => m.entry_date)),
        datasets: [{{
            label: 'Equity',
            data: """ + json.dumps(equity) + """,
            borderColor: '#58a6ff',
            backgroundColor: (ctx) => {{
                const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height);
                g.addColorStop(0, '#58a6ff44');
                g.addColorStop(1, '#58a6ff00');
                return g;
            }},
            fill: true,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.1
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }},
            tooltip: {{
                callbacks: {{
                    label: function(ctx) {{
                        return `Equity: ${{ctx.parsed.y:+,.0f}} EUR`;
                    }}
                }}
            }}
        }},
        scales: {{
            x: {{
                display: true,
                ticks: {{ color: '#8b949e', maxTicksLimit: 20, maxRotation: 45 }},
                grid: {{ color: '#21262d' }}
            }},
            y: {{
                display: true,
                ticks: {{ color: '#8b949e', callback: v => v.toLocaleString() + ' EUR' }},
                grid: {{ color: '#21262d' }}
            }}
        }}
    }}
}});
}})();
</script>
</body>
</html>"""

with open(os.path.join(OUTPUT_DIR, "report_nuovi_dati_2026.html"), "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report salvato: {os.path.join(OUTPUT_DIR, 'report_nuovi_dati_2026.html')}")
print(f"Trade: {total} | Win: {win_rate:.0f}% | PnL: {total_pnl_eur:+.0f} EUR")
