import pandas as pd
import numpy as np

df = pd.read_csv('1oraprova.txt', sep='\t', skiprows=2)
df.columns = ['data', 'high', 'low', 'open', 'close', 'volume']
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
for c in ['high','low','open','close','volume']:
    df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('data').reset_index(drop=True)

# Barre 3h pulite: 08-11, 11-14, 14-17
df['date'] = df['data'].dt.date
df['minutes_since_08'] = df['data'].dt.hour * 60 + df['data'].dt.minute - 8 * 60
df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 540)].copy()  # fino 17:00
df['bin'] = pd.cut(df['minutes_since_08'], bins=[-1, 180, 360, 541], labels=[0, 1, 2], right=False)

grouped = df.groupby(['date', 'bin'], observed=False)
bars = grouped.agg(open=('open','first'), high=('high','max'), low=('low','min'), close=('close','last'), volume=('volume','sum')).reset_index()
bars = bars.dropna(subset=['open'])
bars['date'] = pd.to_datetime(bars['date'])
bars = bars.sort_values(by=['date','bin']).reset_index(drop=True)

def get_bin_time(row):
    if row['bin'] == 0: offset = pd.Timedelta(hours=8)
    elif row['bin'] == 1: offset = pd.Timedelta(hours=11)
    else: offset = pd.Timedelta(hours=14)
    return row['date'] + offset
bars['data'] = bars.apply(get_bin_time, axis=1)
bars = bars[['data','open','high','low','close','volume']]

# Supertrend (14, 3.0)
high, low, close = bars['high'], bars['low'], bars['close']
tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
bars['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
bars['atr'] = bars['tr'].ewm(alpha=1/14, adjust=False).mean()
bars['hl2'] = (high + low) / 2
bars['basic_ub'] = bars['hl2'] + 3.0 * bars['atr']
bars['basic_lb'] = bars['hl2'] - 3.0 * bars['atr']

final_ub = [0.0]*len(bars); final_lb = [0.0]*len(bars)
supertrend = [0.0]*len(bars); direction = [1]*len(bars)
for i in range(len(bars)):
    if i == 0:
        final_ub[i] = bars['basic_ub'].iloc[i]; final_lb[i] = bars['basic_lb'].iloc[i]
        supertrend[i] = final_ub[i]; direction[i] = -1; continue
    prev_close = bars['close'].iloc[i-1]
    if bars['basic_ub'].iloc[i] < final_ub[i-1] or prev_close > final_ub[i-1]:
        final_ub[i] = bars['basic_ub'].iloc[i]
    else: final_ub[i] = final_ub[i-1]
    if bars['basic_lb'].iloc[i] > final_lb[i-1] or prev_close < final_lb[i-1]:
        final_lb[i] = bars['basic_lb'].iloc[i]
    else: final_lb[i] = final_lb[i-1]
    if supertrend[i-1] == final_ub[i-1]:
        if bars['close'].iloc[i] > final_ub[i]:
            supertrend[i] = final_lb[i]; direction[i] = 1
        else: supertrend[i] = final_ub[i]; direction[i] = -1
    else:
        if bars['close'].iloc[i] < final_lb[i]:
            supertrend[i] = final_ub[i]; direction[i] = -1
        else: supertrend[i] = final_lb[i]; direction[i] = 1
bars['direction'] = direction
bars['supertrend'] = supertrend

# Trova segnali
segnali = []
for i in range(2, len(bars)):
    prev_dir = bars['direction'].iloc[i-1]
    prev_prev_dir = bars['direction'].iloc[i-2]
    if prev_dir == 1 and prev_prev_dir == -1:
        segnali.append({'idx':i,'tipo':'LONG','entry':bars['open'].iloc[i],'atr':bars['atr'].iloc[i-1],'data':bars['data'].iloc[i]})
    elif prev_dir == -1 and prev_prev_dir == 1:
        segnali.append({'idx':i,'tipo':'SHORT','entry':bars['open'].iloc[i],'atr':bars['atr'].iloc[i-1],'data':bars['data'].iloc[i]})

# Genera HTML con tabella barre + segnali
rows_bars = ''
for i, (_, r) in enumerate(bars.iterrows()):
    dir_sym = '▲' if r['direction'] == 1 else '▼'
    dir_color = '#10b981' if r['direction'] == 1 else '#ef4444'
    
    # Check if this bar has a signal
    signal = ''
    for s in segnali:
        if s['idx'] == i:
            tp = s['entry'] + s['atr'] if s['tipo'] == 'LONG' else s['entry'] - s['atr']
            signal = f'<span style="color:{"#10b981" if s["tipo"]=="LONG" else "#ef4444"};font-weight:700">► {s["tipo"]} entry={s["entry"]:.2f} TP={tp:.2f}</span>'
            break
    if r['direction'] != bars['direction'].iloc[i-1] if i > 0 else True:
        flip_style = 'background:rgba(255,255,100,0.08)'
    else:
        flip_style = ''
    
    rows_bars += f'<tr style="{flip_style}"><td>{r["data"].strftime("%d/%m %H:%M")}</td><td>{r["open"]:.2f}</td><td>{r["high"]:.2f}</td><td>{r["low"]:.2f}</td><td>{r["close"]:.2f}</td><td style="color:{dir_color}">{dir_sym}</td><td>{r["supertrend"]:.2f}</td><td>{r["atr"]:.4f}</td><td>{signal}</td></tr>'

rows_signals = ''
for s in segnali:
    tp = s['entry'] + s['atr'] if s['tipo'] == 'LONG' else s['entry'] - s['atr']
    # Esito
    esito = 'APERTO'
    for j in range(s['idx']+1, len(bars)):
        if s['tipo'] == 'LONG':
            if bars['high'].iloc[j] >= tp: esito = f'TP {tp:.2f}'; break
            if bars['close'].iloc[j] < bars['supertrend'].iloc[j]: esito = f'STOP {bars["close"].iloc[j]:.2f}'; break
        else:
            if bars['low'].iloc[j] <= tp: esito = f'TP {tp:.2f}'; break
            if bars['close'].iloc[j] > bars['supertrend'].iloc[j]: esito = f'STOP {bars["close"].iloc[j]:.2f}'; break
    color = '#10b981' if esito.startswith('TP') else '#ef4444'
    rows_signals += f'<tr><td>{s["data"].strftime("%d/%m %H:%M")}</td><td style="color:{"#10b981" if s["tipo"]=="LONG" else "#ef4444"};font-weight:700">{s["tipo"]}</td><td>{s["entry"]:.2f}</td><td>{s["atr"]:.4f}</td><td>{tp:.2f}</td><td style="color:{color}">{esito}</td></tr>'

html = f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><title>BTP 3H - Barre e Segnali</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0a0e17;color:#e5e7eb;padding:20px}}
h1,h2{{color:#00f2fe}}
table{{border-collapse:collapse;font-size:.85rem;width:100%;margin-bottom:30px}}
th{{text-transform:uppercase;color:#6b7280;padding:8px 6px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left;font-size:.75rem}}
td{{padding:6px;border-bottom:1px solid rgba(255,255,255,.04)}}
tr:hover td{{background:rgba(255,255,255,.02)}}
</style></head>
<body>
<h1>BTP 3H — Barre 08-11 | 11-14 | 14-17</h1>
<p>ST(14,3.0) TP=1.0 — {len(bars)} barre, {len(segnali)} segnali</p>

<h2>Segnali</h2>
<table><thead><tr><th>Data</th><th>Segnale</th><th>Entry</th><th>ATR</th><th>TP</th><th>Esito</th></tr></thead>
<tbody>{rows_signals}</tbody></table>

<h2>Barre 3h</h2>
<div style="overflow-x:auto"><table>
<thead><tr><th>Data</th><th>O</th><th>H</th><th>L</th><th>C</th><th>Dir</th><th>ST</th><th>ATR</th><th>Segnale</th></tr></thead>
<tbody>{rows_bars}</tbody></table></div>
</body></html>"""

with open('btp3h_barre_segnali.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Fatto. {len(bars)} barre, {len(segnali)} segnali.")
