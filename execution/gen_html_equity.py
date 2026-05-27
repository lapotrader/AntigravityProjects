"""Genera HTML equity curve con dati incorporati (zero dipendenze esterne)."""
import json, os

OUTPUT_DIR = "output"
with open(os.path.join(OUTPUT_DIR, "btp_1h_equity_summary.json")) as f:
    data = json.load(f)

trades = data["trades"]
curve = data["equity_curve"]
stats = data["stats"]
config = data["config"]

dates = [c["date"] for c in curve]
eq_values = [c["equity"] for c in curve]

peak = []; mx = -1e9
for v in eq_values:
    mx = max(mx, v)
    peak.append(mx)
dd_values = [-(peak[i] - eq_values[i]) for i in range(len(eq_values))]

pnl_values = [t["pnl_eur"] for t in trades]
win_x = []; win_y = []; loss_x = []; loss_y = []
running = 0
for i, t in enumerate(trades):
    running += t["pnl_eur"]
    if t["pnl_eur"] > 0:
        win_x.append(t["entry_date"]); win_y.append(running)
    else:
        loss_x.append(t["entry_date"]); loss_y.append(running)

pair = lambda a, b: [{"x": a[i], "y": b[i]} for i in range(len(a))]

html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>Equity Curve BTP 1h</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #0d1117; color: #e6e6e6; margin: 0; padding: 20px; }}
h1 {{ color: #58a6ff; border-bottom: 2px solid #30363d; padding-bottom: 10px; font-size: 22px; }}
h2 {{ color: #79c0ff; margin-top: 25px; font-size: 16px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 20px; margin: 12px 0; }}
.grid {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.metric {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; text-align: center; flex: 1; min-width: 90px; }}
.metric .val {{ font-size: 20px; font-weight: bold; color: #58a6ff; }}
.metric .lbl {{ font-size: 10px; color: #8b949e; text-transform: uppercase; }}
.metric .win {{ color: #3fb950; }} .metric .loss {{ color: #f85149; }}
.note {{ background: #1a1a2e; border-left: 3px solid #58a6ff; padding: 10px 14px; margin: 12px 0; border-radius: 0 6px 6px 0; font-size: 13px; color: #c9d1d9; }}
.footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #30363d; color: #8b949e; font-size: 11px; }}
</style>
</head>
<body>

<h1>Equity Curve — BTP Future 1h</h1>
<p>ST({config['st_period']}, {config['st_mult']}) + pivot trailing | Costi: {config['cost_entry']}€+{config['cost_exit']}€ = {config['cost_entry']+config['cost_exit']}€/trade | 1 punto = 1000€</p>

<div class="note">
<strong>Next pivot in live:</strong> all'entry il TP non è prefissato. Il pivot successivo emerge durante il trade (conferma 5 barre dopo).
Il TP viene aggiornato non appena il nuovo swing è identificato — &egrave; un <strong>trailing stop strutturale su livelli di swing</strong>.
</div>

<div class="grid">
<div class="metric"><div class="val win">{stats['win_rate']}%</div><div class="lbl">Win Rate</div></div>
<div class="metric"><div class="val">{stats['wins']}W/{stats['losses']}L</div><div class="lbl">Trade</div></div>
<div class="metric"><div class="val win">+{stats['total_pnl_eur']:,.0f} &euro;</div><div class="lbl">PnL Netto</div></div>
<div class="metric"><div class="val">{stats['profit_factor']}</div><div class="lbl">Profit Factor</div></div>
<div class="metric"><div class="val loss">{stats['max_dd_eur']:,.0f} &euro;</div><div class="lbl">Max Drawdown</div></div>
<div class="metric"><div class="val">{stats['max_dd_pct']}%</div><div class="lbl">Drawdown %</div></div>
<div class="metric"><div class="val">{stats['sharpe']}</div><div class="lbl">Sharpe</div></div>
<div class="metric"><div class="val win">{stats['avg_win_eur']:,.0f} &euro;</div><div class="lbl">Avg Win</div></div>
<div class="metric"><div class="val loss">{stats['avg_loss_eur']:,.0f} &euro;</div><div class="lbl">Avg Loss</div></div>
</div>

<h2>Equity Curve</h2>
<div id="chart-eq" style="width:100%;height:450px;"></div>

<h2>Drawdown</h2>
<div id="chart-dd" style="width:100%;height:200px;"></div>

<h2>Distribuzione PnL per Trade</h2>
<div id="chart-pnl" style="width:100%;height:250px;"></div>

<h2>Dettaglio Trade ({len(trades)} trades, costi inclusi)</h2>
<div style="max-height:450px;overflow-y:auto;border:1px solid #30363d;border-radius:6px;">
<table>
<tr><th>#</th><th>Entry</th><th>Exit</th><th>Dir</th><th>EntryP</th><th>SL</th><th>Esito</th><th>PnL &euro;</th><th>Eq &euro;</th></tr>
"""

eq_acc = 0
for i, t in enumerate(trades):
    eq_acc += t["pnl_eur"]
    cls = "win" if t["pnl_eur"] > 0 else "loss"
    pnl_str = f"+{t['pnl_eur']:,.0f}" if t["pnl_eur"] > 0 else f"{t['pnl_eur']:,.0f}"
    html += f"<tr><td>{i+1}</td><td>{t['entry_date']}</td><td>{t['exit_date']}</td><td>{t['dir']}</td><td>{t['entry']}</td><td>{t['sl']}</td><td>{t['result']}</td><td class='{cls}'>{pnl_str}</td><td>{eq_acc:,.0f}</td></tr>\n"

html += """</table>
</div>

<script>
const dates = """ + json.dumps(dates) + """;
const eq = """ + json.dumps(eq_values) + """;
const dd = """ + json.dumps(dd_values) + """;
const pnl = """ + json.dumps(pnl_values) + """;
const win = """ + json.dumps(pair(win_x, win_y)) + """;
const loss = """ + json.dumps(pair(loss_x, loss_y)) + """;

Plotly.newPlot('chart-eq', [
  { x: dates, y: eq, type: 'scatter', mode: 'lines', line: { color: '#58a6ff', width: 2 }, fill: 'tozeroy', fillcolor: 'rgba(88,166,255,0.08)', name: 'Equity' },
  { x: win.map(d=>d.x), y: win.map(d=>d.y), mode: 'markers', type: 'scatter', marker: { symbol: 'triangle-up', size: 7, color: '#3fb950', line: { color: 'white', width: 0.5 } }, name: 'Win' },
  { x: loss.map(d=>d.x), y: loss.map(d=>d.y), mode: 'markers', type: 'scatter', marker: { symbol: 'triangle-down', size: 7, color: '#f85149', line: { color: 'white', width: 0.5 } }, name: 'Loss' }
], {
  paper_bgcolor: '#0d1117', plot_bgcolor: '#161b22', font: { color: '#e6e6e6', size: 11 },
  xaxis: { gridcolor: '#30363d', zeroline: false },
  yaxis: { gridcolor: '#30363d', zeroline: true, zerolinecolor: '#30363d', title: 'Equity (€)' },
  margin: { l: 60, r: 20, t: 10, b: 40 }, hovermode: 'x unified', showlegend: true,
  legend: { orientation: 'h', y: 1.02, x: 0, font: { color: '#8b949e', size: 10 } }
}, { responsive: true });

Plotly.newPlot('chart-dd', [{
  x: dates, y: dd, type: 'scatter', mode: 'lines', line: { color: '#f85149', width: 1.5 }, fill: 'tozeroy', fillcolor: 'rgba(248,81,73,0.15)', name: 'Drawdown'
}], {
  paper_bgcolor: '#0d1117', plot_bgcolor: '#161b22', font: { color: '#e6e6e6', size: 11 },
  xaxis: { gridcolor: '#30363d', zeroline: false },
  yaxis: { gridcolor: '#30363d', zeroline: true, zerolinecolor: '#30363d', title: 'DD (€)' },
  margin: { l: 60, r: 20, t: 10, b: 40 }, hovermode: 'x unified', showlegend: false
}, { responsive: true });

Plotly.newPlot('chart-pnl', [{
  x: pnl.map((_,i)=>i+1), y: pnl, type: 'bar',
  marker: { color: pnl.map(v=>v>0?'#3fb950':'#f85149'), line: { width: 0 } },
  name: 'PnL'
}], {
  paper_bgcolor: '#0d1117', plot_bgcolor: '#161b22', font: { color: '#e6e6e6', size: 11 },
  xaxis: { gridcolor: '#30363d', zeroline: false, title: 'Trade #' },
  yaxis: { gridcolor: '#30363d', zeroline: true, zerolinecolor: '#30363d', title: 'PnL (€)' },
  margin: { l: 60, r: 20, t: 10, b: 40 }, hovermode: 'x', showlegend: false,
  shapes: [{ type: 'line', x0: 0, y0: 0, x1: pnl.length+1, y1: 0, line: { color: '#8b949e', width: 1, dash: 'dot' } }]
}, { responsive: true });
</script>

<div class="footer">
<p>Periodo: {dates[0]} - {dates[-1]} | Dati embedded (zero dipendenze locali)</p>
<p>Generato: 27/05/2026 | Performance passate non garantiscono risultati futuri</p>
</div>

</body>
</html>"""

with open(os.path.join(OUTPUT_DIR, "btp_1h_equity_report.html"), "w", encoding="utf-8") as f:
    f.write(html)

print(f"HTML generato: output/btp_1h_equity_report.html ({len(html)} bytes)")
