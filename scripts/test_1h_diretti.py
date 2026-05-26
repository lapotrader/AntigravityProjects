import pandas as pd
import numpy as np

df = pd.read_csv('1oraprova.txt', sep='\t', skiprows=2)
df.columns = ['data', 'high', 'low', 'open', 'close', 'volume']
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
for c in ['high','low','open','close','volume']:
    df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('data').reset_index(drop=True)

# Filtra 08-19
df['hour'] = df['data'].dt.hour
df = df[(df['hour'] >= 8) & (df['hour'] <= 18)].copy()

# Supertrend (14, 3.0) su 1h
high, low, close = df['high'], df['low'], df['close']
tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['atr'] = df['tr'].ewm(alpha=1/14, adjust=False).mean()
df['hl2'] = (high + low) / 2
df['basic_ub'] = df['hl2'] + 3.0 * df['atr']
df['basic_lb'] = df['hl2'] - 3.0 * df['atr']

final_ub = [0.0]*len(df); final_lb = [0.0]*len(df)
supertrend = [0.0]*len(df); direction = [1]*len(df)
for i in range(len(df)):
    if i == 0:
        final_ub[i] = df['basic_ub'].iloc[i]; final_lb[i] = df['basic_lb'].iloc[i]
        supertrend[i] = final_ub[i]; direction[i] = -1; continue
    prev_close = df['close'].iloc[i-1]
    if df['basic_ub'].iloc[i] < final_ub[i-1] or prev_close > final_ub[i-1]:
        final_ub[i] = df['basic_ub'].iloc[i]
    else: final_ub[i] = final_ub[i-1]
    if df['basic_lb'].iloc[i] > final_lb[i-1] or prev_close < final_lb[i-1]:
        final_lb[i] = df['basic_lb'].iloc[i]
    else: final_lb[i] = final_lb[i-1]
    if supertrend[i-1] == final_ub[i-1]:
        if df['close'].iloc[i] > final_ub[i]:
            supertrend[i] = final_lb[i]; direction[i] = 1
        else: supertrend[i] = final_ub[i]; direction[i] = -1
    else:
        if df['close'].iloc[i] < final_lb[i]:
            supertrend[i] = final_ub[i]; direction[i] = -1
        else: supertrend[i] = final_lb[i]; direction[i] = 1
df['direction'] = direction
df['supertrend'] = supertrend

# Mostra 12 e 20 maggio
mask = (df['data'] >= '2026-05-12') & (df['data'] <= '2026-05-22 12:00')
sub = df[mask].copy()

print(f"{'Data 1h':<22} {'Close':<8} {'ST':<10} {'Dir':<5} {'ATR':<8} {'Flip?'}")
print('-'*70)
prev_dir = None
for _, r in sub.iterrows():
    dir_str = 'LONG' if r['direction']==1 else 'SHORT'
    flip = ''
    if prev_dir is not None and r['direction'] != prev_dir:
        flip = '<<< FLIP'
    print(f"{r['data'].strftime('%d/%m/%Y %H:%M'):<22} {r['close']:<8.2f} {r['supertrend']:<10.2f} {dir_str:<5} {r['atr']:<8.4f} {flip}")
    prev_dir = r['direction']

# Segnali trade
print('\n=== SEGNALI COMPLETI 1h ST(14,3.0) TP=1.0 ===')
trades = []
for i in range(2, len(df)):
    prev_dir = df['direction'].iloc[i-1]
    prev_prev_dir = df['direction'].iloc[i-2]
    is_long = prev_dir == 1 and prev_prev_dir == -1
    is_short = prev_dir == -1 and prev_prev_dir == 1
    if not (is_long or is_short): continue
    entry = df['open'].iloc[i]
    atr_entry = df['atr'].iloc[i-1]
    tp = entry + atr_entry if is_long else entry - atr_entry
    tp_str = f"{tp:.2f}"
    # Cerca chiusura
    esito = 'APERTO'
    for j in range(i+1, len(df)):
        if is_long:
            if df['high'].iloc[j] >= tp:
                esito = 'TP'; break
            if df['close'].iloc[j] < df['supertrend'].iloc[j]:
                esito = f'STOP a {df["close"].iloc[j]:.2f}'; break
        else:
            if df['low'].iloc[j] <= tp:
                esito = 'TP'; break
            if df['close'].iloc[j] > df['supertrend'].iloc[j]:
                esito = f'STOP a {df["close"].iloc[j]:.2f}'; break
    trades.append({'data':df['data'].iloc[i],'tipo':'LONG' if is_long else 'SHORT','entry':entry,'tp':tp,'atr':atr_entry,'esito':esito})

print(f"{'Data 1h':<22} {'Tipo':<8} {'Entry':<10} {'ATR':<10} {'TP':<12} {'Esito':<22}")
print('-'*80)
for t in trades:
    print(f"{t['data'].strftime('%d/%m/%Y %H:%M'):<22} {t['tipo']:<8} {t['entry']:<10.2f} {t['atr']:<10.4f} {t['tp']:<12.2f} {t['esito']:<22}")
