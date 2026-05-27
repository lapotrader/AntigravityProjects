import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / 'dati' / '1oraprova.txt'
OUTPUT_DIR = BASE_DIR / 'output'
OUTPUT_FILE = OUTPUT_DIR / 'supertrend_signals_1h.json'

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_FILE, sep='\t', skiprows=2)
df.columns = ['data', 'high', 'low', 'open', 'close', 'volume']
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
for c in ['high', 'low', 'open', 'close', 'volume']:
    df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
df = df.sort_values('data').reset_index(drop=True)

high, low, close = df['high'], df['low'], df['close']
tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['atr'] = df['tr'].ewm(alpha=1 / 14, adjust=False).mean()
df['hl2'] = (high + low) / 2
multiplier = 3.0
df['basic_ub'] = df['hl2'] + multiplier * df['atr']
df['basic_lb'] = df['hl2'] - multiplier * df['atr']

final_ub = [0.0] * len(df)
final_lb = [0.0] * len(df)
supertrend = [0.0] * len(df)
direction = [1] * len(df)

for i in range(len(df)):
    if i == 0:
        final_ub[i] = df['basic_ub'].iloc[i]
        final_lb[i] = df['basic_lb'].iloc[i]
        supertrend[i] = final_ub[i]
        direction[i] = -1
        continue
    prev_close = df['close'].iloc[i - 1]
    if df['basic_ub'].iloc[i] < final_ub[i - 1] or prev_close > final_ub[i - 1]:
        final_ub[i] = df['basic_ub'].iloc[i]
    else:
        final_ub[i] = final_ub[i - 1]
    if df['basic_lb'].iloc[i] > final_lb[i - 1] or prev_close < final_lb[i - 1]:
        final_lb[i] = df['basic_lb'].iloc[i]
    else:
        final_lb[i] = final_lb[i - 1]
    if supertrend[i - 1] == final_ub[i - 1]:
        if df['close'].iloc[i] > final_ub[i]:
            supertrend[i] = final_lb[i]
            direction[i] = 1
        else:
            supertrend[i] = final_ub[i]
            direction[i] = -1
    else:
        if df['close'].iloc[i] < final_lb[i]:
            supertrend[i] = final_ub[i]
            direction[i] = -1
        else:
            supertrend[i] = final_lb[i]
            direction[i] = 1

signals = []
for i in range(2, len(df)):
    prev_dir = direction[i - 1]
    prev_prev_dir = direction[i - 2]
    if prev_dir == 1 and prev_prev_dir == -1:
        signals.append({
            'data': df['data'].iloc[i].strftime('%d/%m/%Y %H:%M'),
            'direzione': 'LONG',
            'prezzo_entry': round(df['open'].iloc[i], 2),
            'atr': round(df['atr'].iloc[i - 1], 4)
        })
    elif prev_dir == -1 and prev_prev_dir == 1:
        signals.append({
            'data': df['data'].iloc[i].strftime('%d/%m/%Y %H:%M'),
            'direzione': 'SHORT',
            'prezzo_entry': round(df['open'].iloc[i], 2),
            'atr': round(df['atr'].iloc[i - 1], 4)
        })

output = {
    'parametri': {'period': 14, 'multiplier': multiplier},
    'totale_segnali': len(signals),
    'segnali': signals
}

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n=== SUPERTREND SIGNALS (14, {multiplier}) — BTP 1h ===")
print(f"{'Data Entry':<22} {'Direzione':<10} {'Prezzo':<10} {'ATR':<10}")
print('-' * 55)
for s in signals:
    print(f"{s['data']:<22} {s['direzione']:<10} {s['prezzo_entry']:<10.2f} {s['atr']:<10.4f}")
print(f"\nTotale segnali: {len(signals)}")
print(f"Salvato in: {OUTPUT_FILE}")
