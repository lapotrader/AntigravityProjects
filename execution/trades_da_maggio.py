import pandas as pd, numpy as np

LOOKBACK = 5; ST_PERIOD = 30; ST_MULT = 1.5
PATH = 'dati/27 febbraio.txt'
df = pd.read_csv(PATH, sep='\t', header=None, decimal=',')
df.columns = ['data','high','low','open','close','volume']
for c in ['high','low','open','close','volume']: df[c] = df[c].astype(float)
df['ora'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M:%S')
n = len(df)

high, low, close = df['high'].values, df['low'].values, df['close'].values
tr = np.maximum(high-low, np.maximum(np.abs(high-np.roll(close,1)), np.abs(low-np.roll(close,1))))
tr[0] = high[0]-low[0]
atr = np.zeros(n); alpha = 1/ST_PERIOD; atr[0] = tr[0]
for i in range(1, n): atr[i] = atr[i-1] + alpha*(tr[i]-atr[i-1])
hl2 = (high+low)/2
basic_ub = hl2 + ST_MULT*atr; basic_lb = hl2 - ST_MULT*atr
final_ub, final_lb, st = np.zeros(n), np.zeros(n), np.zeros(n)
direction = np.ones(n, dtype=int)
for i in range(n):
    if i == 0:
        final_ub[i]=basic_ub[i]; final_lb[i]=basic_lb[i]; st[i]=final_ub[i]; direction[i]=-1; continue
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
for i in range(LOOKBACK, n-LOOKBACK):
    if all(df.loc[i,'high'] > df.loc[i-k,'high'] for k in range(1,LOOKBACK+1)) and all(df.loc[i,'high'] > df.loc[i+k,'high'] for k in range(1,LOOKBACK+1)): ph_flag[i] = True
    if all(df.loc[i,'low'] < df.loc[i-k,'low'] for k in range(1,LOOKBACK+1)) and all(df.loc[i,'low'] < df.loc[i+k,'low'] for k in range(1,LOOKBACK+1)): pl_flag[i] = True

ph_prev = [None]*n; pl_prev = [None]*n
lp = None; ll = None
for i in range(n):
    if ph_flag[i]: lp = float(df.loc[i,'high'])
    if pl_flag[i]: ll = float(df.loc[i,'low'])
    ph_prev[i] = lp; pl_prev[i] = ll

ph_next = [None]*n; pl_next = [None]*n
np_h = None; np_l = None
for i in range(n-1, -1, -1):
    if ph_flag[i]: np_h = float(df.loc[i,'high'])
    if pl_flag[i]: np_l = float(df.loc[i,'low'])
    ph_next[i] = np_h; pl_next[i] = np_l

trades = []
for i in range(ST_PERIOD+2, n):
    prev = direction[i-1]; pprev = direction[i-2]
    if prev == 1 and pprev == -1: dl = 'LONG'
    elif prev == -1 and pprev == 1: dl = 'SHORT'
    else: continue
    entry = round(float(df.loc[i,'open']),2)
    atr_v = float(atr[i-1])
    if dl == 'LONG':
        pl = pl_prev[i]
        if pl is None: continue
        sl = round(pl - 0.5*atr_v, 2)
        tp = round(ph_next[i],2) if ph_next[i] is not None else round(entry+abs(entry-sl),2)
    else:
        ph = ph_prev[i]
        if ph is None: continue
        sl = round(ph + 0.5*atr_v, 2)
        tp = round(pl_next[i],2) if pl_next[i] is not None else round(entry-abs(sl-entry),2)
    if sl is None or tp is None: continue
    if (dl=='LONG' and sl >= entry) or (dl=='SHORT' and sl <= entry): continue
    if dl=='LONG' and tp <= entry: tp = round(entry+abs(entry-sl),2)
    if dl=='SHORT' and tp >= entry: tp = round(entry-abs(sl-entry),2)

    idx = i; result = None; exit_p = None
    for j in range(idx+1, n):
        if dl == 'LONG':
            if df.loc[j,'low'] <= sl: result='SL'; exit_p=sl; break
            if df.loc[j,'high'] >= tp: result='TP'; exit_p=tp; break
        else:
            if df.loc[j,'high'] >= sl: result='SL'; exit_p=sl; break
            if df.loc[j,'low'] <= tp: result='TP'; exit_p=tp; break
    if result is None: continue
    pnl = round(exit_p-entry,2) if dl=='LONG' else round(entry-exit_p,2)

    entry_date = df.loc[i,'ora']
    if entry_date >= pd.Timestamp('2026-05-20'):
        trades.append({'date': entry_date, 'dir': dl, 'entry': entry, 'sl': sl, 'tp': tp, 'exit': exit_p, 'result': result, 'pnl': pnl})

print(f"Trade dal 20 maggio in poi: {len(trades)}")
print()
for t in trades:
    d = t['date'].strftime('%a %d/%m %H:%M')
    r = 'TP' if t['result']=='TP' else 'SL'
    print(f"{d} {t['dir']:5s} entry={t['entry']:.2f}  SL={t['sl']:.2f}  TP={t['tp']:.2f}  exit={t['exit']:.2f}  {r}  PnL={t['pnl']:+.2f}pt")
