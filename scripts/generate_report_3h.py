import pandas as pd
import numpy as np

df = pd.read_csv('btp3h_optimization_results.csv')

df['profit_dd_ratio'] = df['net_profit_eur'] / df['max_dd_eur']
df_sorted = df.sort_values(by='profit_dd_ratio', ascending=False)

top1 = df_sorted.iloc[0]

def fmt_ma(v):
    if v == 'None':
        return 'OFF'
    return f'SMA{v}'

rows_html = ''
for _, r in df_sorted.head(20).iterrows():
    ma_style = "class='highlight-text'" if r['ma_period'] == 'None' else ''
    rows_html += f"""<tr><td {ma_style}>{fmt_ma(r['ma_period'])}</td><td>({int(r['st_period'])},{r['st_multiplier']})</td><td>{r['tp_mult']}</td><td>{int(r['trades'])}</td><td>{r['win_rate']:.0f}%</td><td>{r['profit_factor']:.2f}</td><td class="profit-text">{r['net_profit_eur']:,.0f}€</td><td class="dd-text">{r['max_dd_eur']:,.0f}€</td><td><span class="ratio-badge">{r['profit_dd_ratio']:.1f}</span></td></tr>"""

html = f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BTP 3H</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#0a0e17;color:#e5e7eb;padding:30px 20px}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:1.8rem;font-weight:700;background:linear-gradient(135deg,#00f2fe,#4facfe);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:5px}}
.subtitle{{color:#6b7280;font-size:.9rem;margin-bottom:30px}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th{{text-transform:uppercase;letter-spacing:.5px;color:#6b7280;padding:12px 10px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left;font-weight:600}}
td{{padding:12px 10px;border-bottom:1px solid rgba(255,255,255,.04)}}
tr:hover td{{background:rgba(255,255,255,.02)}}
tr:first-child td{{background:rgba(0,242,254,.05);border-bottom:1px solid rgba(0,242,254,.15)}}
.highlight-text{{font-weight:700;color:#00f2fe}}
.profit-text{{color:#10b981;font-weight:700}}
.dd-text{{color:#ef4444}}
.ratio-badge{{display:inline-block;padding:2px 8px;border-radius:4px;background:rgba(16,185,129,.1);color:#10b981;font-weight:700}}
footer{{margin-top:40px;color:#6b7280;font-size:.8rem;text-align:center}}
</style></head>
<body><div class="container">
<h1>BTP 3H Optimization</h1>
<p class="subtitle">ST Periodi: 10,14,20,30 × Moltiplicatori: 1.5,2.0,2.5,3.0 × TP: 0.5,1.0,1.5,2.0,3.0,NoTP × MA: OFF,21,50,100,200</p>
<div style="overflow-x:auto"><table>
<thead><tr><th>MA</th><th>ST(P,M)</th><th>TP</th><th>Trades</th><th>Win%</th><th>PF</th><th>Profit</th><th>DD</th><th>P/DD</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<footer>{len(df)} test · Migliore: ST({int(top1['st_period'])},{top1['st_multiplier']}) TP{top1['tp_mult']} MA{fmt_ma(top1['ma_period'])} · Ratio {top1['profit_dd_ratio']:.1f}</footer>
</div></body></html>"""

with open('btp3h_optimization_results.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Fatto")
