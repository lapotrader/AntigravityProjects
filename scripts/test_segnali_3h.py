import pandas as pd
import numpy as np

df = pd.read_csv('1oraprova.txt', sep='\t', skiprows=2)
df.columns = ['data', 'high', 'low', 'open', 'close', 'volume']
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
for c in ['high','low','open','close','volume']:
    df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('data').reset_index(drop=True)

# Aggregazione barre 3h
df['date'] = df['data'].dt.date
df['minutes_since_08'] = df['data'].dt.hour * 60 + df['data'].dt.minute - 8 * 60
df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 660)].copy()
df['bin'] = pd.cut(df['minutes_since_08'], bins=[-1, 180, 360, 661], labels=[0, 1, 2], right=False)
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

# Simula trades completi (esito su tutto il futuro fino a chiusura)
trades = []
for i in range(2, len(bars)):
    prev_dir = bars['direction'].iloc[i-1]
    prev_prev_dir = bars['direction'].iloc[i-2]
    if not (prev_dir == 1 and prev_prev_dir == -1) and not (prev_dir == -1 and prev_prev_dir == 1):
        continue

    entry_idx = i
    entry = bars['open'].iloc[i]
    atr_entry = bars['atr'].iloc[i-1]
    is_long = prev_dir == 1 and prev_prev_dir == -1
    tp = entry + atr_entry if is_long else entry - atr_entry
    entry_date = bars['data'].iloc[i]

    esito = 'APERTO'
    for j in range(i+1, len(bars)):
        if is_long:
            if bars['high'].iloc[j] >= tp:
                esito = 'TP'
                break
            if bars['close'].iloc[j] < bars['supertrend'].iloc[j]:
                esito = f'STOP a {bars["close"].iloc[j]:.2f}'
                break
        else:
            if bars['low'].iloc[j] <= tp:
                esito = 'TP'
                break
            if bars['close'].iloc[j] > bars['supertrend'].iloc[j]:
                esito = f'STOP a {bars["close"].iloc[j]:.2f}'
                break

    pnl = round((tp - entry)*1000, 2) if esito == 'TP' else 0
    trades.append({'tipo':'LONG' if is_long else 'SHORT','entry':entry,'tp':tp,'atr':atr_entry,'data':entry_date,'esito':esito,'pnl':pnl})

print(f"{'Data 3h':<22} {'Tipo':<8} {'Entry':<10} {'ATR':<10} {'TP':<12} {'Esito':<20} {'PnL€':<10}")
print('-'*80)
for t in trades:
    print(f"{t['data'].strftime('%d/%m/%Y %H:%M'):<22} {t['tipo']:<8} {t['entry']:<10.2f} {t['atr']:<10.4f} {t['tp']:<12.2f} {t['esito']:<20} {t['pnl']:<10.2f}")
print(f"\nTotale: {len(trades)} trades")
