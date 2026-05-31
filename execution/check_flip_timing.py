import pandas as pd, numpy as np

ST_PERIOD = 30; ST_MULT = 1.5
df = pd.read_csv('dati/27 febbraio.txt', sep='\t', header=None, decimal=',')
df.columns = ['data','high','low','open','close','volume']
for c in ['high','low','open','close','volume']: df[c] = df[c].astype(float)

close_arr = df['close'].values
high_arr = df['high'].values
low_arr = df['low'].values

tr = np.maximum(high_arr - low_arr, np.maximum(np.abs(high_arr - np.roll(close_arr, 1)), np.abs(low_arr - np.roll(close_arr, 1))))
tr[0] = high_arr[0] - low_arr[0]
atr = np.zeros(len(df)); alpha = 1/ST_PERIOD; atr[0] = tr[0]
for i in range(1, len(df)): atr[i] = atr[i-1] + alpha*(tr[i]-atr[i-1])

final_ub = np.zeros(len(df)); final_lb = np.zeros(len(df)); st = np.zeros(len(df))
direction = np.ones(len(df), dtype=int)
for i in range(len(df)):
    if i == 0:
        hl2 = (high_arr[i] + low_arr[i]) / 2
        final_ub[i] = hl2 + ST_MULT*atr[i]; final_lb[i] = hl2 - ST_MULT*atr[i]
        st[i]=final_ub[i]; direction[i]=-1; continue
    pc = close_arr[i-1]
    hl2 = (high_arr[i] + low_arr[i]) / 2
    basic_ub = hl2 + ST_MULT*atr[i]; basic_lb = hl2 - ST_MULT*atr[i]
    final_ub[i] = basic_ub if (basic_ub < final_ub[i-1] or pc > final_ub[i-1]) else final_ub[i-1]
    final_lb[i] = basic_lb if (basic_lb > final_lb[i-1] or pc < final_lb[i-1]) else final_lb[i-1]
    if st[i-1] == final_ub[i-1]:
        if close_arr[i] > final_ub[i]: st[i]=final_lb[i]; direction[i]=1
        else: st[i]=final_ub[i]; direction[i]=-1
    else:
        if close_arr[i] < final_lb[i]: st[i]=final_ub[i]; direction[i]=-1
        else: st[i]=final_lb[i]; direction[i]=1

# Find May 28 SHORT entry
for idx in range(len(df)):
    d = df.loc[idx, 'data']
    if '28/05/2026' in d:
        if idx > 1 and direction[idx] == -1 and direction[idx-1] == 1:
            print(f"FLIP SHORT detected at candle close: {df.loc[idx-1, 'data']}")
            print(f"Entry candle open: {df.loc[idx, 'data']} open={df.loc[idx, 'open']:.2f}")
            print()
            print("Candele prima del flip (trend LONG):")
            for k in range(max(0, idx-6), idx):
                print(f"  {df.loc[k, 'data']} O={df.loc[k, 'open']:.2f} H={df.loc[k, 'high']:.2f} L={df.loc[k, 'low']:.2f} C={df.loc[k, 'close']:.2f} DIR=LONG")
            print()
            print("Candela del flip (chiusura = cambio direzione):")
            print(f"  {df.loc[idx, 'data']} O={df.loc[idx, 'open']:.2f} H={df.loc[idx, 'high']:.2f} L={df.loc[idx, 'low']:.2f} C={df.loc[idx, 'close']:.2f} DIR=SHORT")
            print()
            print(f"RIEPILOGO:")
            print(f"  Il flip LONG->SHORT e avvenuto alla chiusura della candela delle {df.loc[idx-1,'data']}")
            print(f"  Entrata (open candela successiva): {df.loc[idx, 'data']} a {df.loc[idx, 'open']:.2f}")
            break
