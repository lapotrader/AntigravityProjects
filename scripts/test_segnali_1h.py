import pandas as pd
import numpy as np

df = pd.read_csv('1oraprova.txt', sep='\t', skiprows=2)
df.columns = ['data', 'high', 'low', 'open', 'close', 'volume']
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
for c in ['high','low','open','close','volume']:
    df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('data').reset_index(drop=True)

# Supertrend (14, 3.0)
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
        final_ub[i] = df['basic_ub'].iloc[i]
        final_lb[i] = df['basic_lb'].iloc[i]
        supertrend[i] = final_ub[i]
        direction[i] = -1; continue
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

trades = []
for i in range(2, len(df)):
    prev_dir = df['direction'].iloc[i-1]
    prev_prev_dir = df['direction'].iloc[i-2]
    if prev_dir == 1 and prev_prev_dir == -1:  # flip long
        entry = df['open'].iloc[i]
        atr_entry = df['atr'].iloc[i-1]
        tp = entry + 1.0 * atr_entry
        trades.append({'tipo': 'LONG', 'data': df['data'].iloc[i], 'entry': entry, 'atr': atr_entry, 'tp': tp})
    elif prev_dir == -1 and prev_prev_dir == 1:  # flip short
        entry = df['open'].iloc[i]
        atr_entry = df['atr'].iloc[i-1]
        tp = entry - 1.0 * atr_entry
        trades.append({'tipo': 'SHORT', 'data': df['data'].iloc[i], 'entry': entry, 'atr': atr_entry, 'tp': tp})

print(f"\n=== SEGNALI SU 1oraprova.txt — ST(14,3.0) TP=1.0 ===\n")
print(f"{'Data':<22} {'Tipo':<8} {'Entry':<10} {'ATR':<10} {'TP Target':<12}")
print('-'*65)
for t in trades:
    print(f"{t['data'].strftime('%d/%m/%Y %H:%M'):<22} {t['tipo']:<8} {t['entry']:<10.2f} {t['atr']:<10.4f} {t['tp']:<12.2f}")
print(f"\nTotale segnali: {len(trades)}")
print(f"ATR medio: {np.mean([t['atr'] for t in trades]):.4f}")
