"""
Verifica look-ahead: confronta TP con CONFIMED next_pivot (j+5 <= exit).
"""
import pandas as pd, numpy as np

PATH = "dati/27 febbraio.txt"
LOOKBACK=5; ST_PERIOD=30; ST_MULT=1.5

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df[c]=df[c].astype(float)
df["ora"]=pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
n=len(df)
high,low,close=df["high"].values,df["low"].values,df["close"].values

# --- ST ---
tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
hl2=(high+low)/2; final_ub=np.zeros(n); final_lb=np.zeros(n); st=np.zeros(n)
direction=np.ones(n,dtype=int)
for i in range(n):
    if i==0: final_ub[i]=hl2[i]+ST_MULT*atr[i]; final_lb[i]=hl2[i]-ST_MULT*atr[i]; st[i]=final_ub[i]; direction[i]=-1; continue
    pc=close[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
    final_ub[i]=ub if (ub<final_ub[i-1] or pc>final_ub[i-1]) else final_ub[i-1]
    final_lb[i]=lb if (lb>final_lb[i-1] or pc<final_lb[i-1]) else final_lb[i-1]
    if st[i-1]==final_ub[i-1]:
        if close[i]>final_ub[i]: st[i]=final_lb[i]; direction[i]=1
        else: st[i]=final_ub[i]; direction[i]=-1
    else:
        if close[i]<final_lb[i]: st[i]=final_ub[i]; direction[i]=-1
        else: st[i]=final_lb[i]; direction[i]=1

# --- Pivot flags (with look-ahead, as original) ---
ph_flag=np.full(n,False); pl_flag=np.full(n,False)
for i in range(LOOKBACK, n-LOOKBACK):
    if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_flag[i]=True
    if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_flag[i]=True

# --- ORIGINAL: next pivot with look-ahead ---
ph_next_orig=[None]*n; pl_next_orig=[None]*n
np_h=None; np_l=None
for i in range(n-1,-1,-1):
    if ph_flag[i]: np_h=float(df.loc[i,"high"])
    if pl_flag[i]: np_l=float(df.loc[i,"low"])
    ph_next_orig[i]=np_h; pl_next_orig[i]=np_l

# --- CONFIRMED: only pivots with 5+ future candles ---
# A pivot at j is confirmed at j+5. So at candle i, 
# confirmed future pivot = first pivot at j >= i where j+5 <= the exit candle
ph_next_conf=[None]*n; pl_next_conf=[None]*n
for i in range(n):
    for j in range(i+LOOKBACK, n):  # look for pivots starting i+5
        if ph_flag[j]:
            # This pivot is confirmed at j+5
            confirmed_at = j + LOOKBACK
            ph_next_conf[i] = (float(df.loc[j,"high"]), j, confirmed_at)
            break
    for j in range(i+LOOKBACK, n):
        if pl_flag[j]:
            confirmed_at = j + LOOKBACK
            pl_next_conf[i] = (float(df.loc[j,"low"]), j, confirmed_at)
            break

# --- prev pivot (SL) - same as original ---
ph_prev=[None]*n; pl_prev=[None]*n
lp=None; ll=None
for i in range(n):
    if ph_flag[i]: lp=float(df.loc[i,"high"])
    if pl_flag[i]: ll=float(df.loc[i,"low"])
    ph_prev[i]=lp; pl_prev[i]=ll

# --- SIMULATE BOTH ---
def simulate(tp_func_ph, tp_func_pl):
    """tp_func returns (tp_price, pivot_idx, confirmed_at) or None"""
    trades = []
    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        if prev==1 and pprev==-1: dir_label="LONG"
        elif prev==-1 and pprev==1: dir_label="SHORT"
        else: continue
        entry=round(float(df.loc[i,"open"]),2); atr_v=float(atr[i-1])
        if dir_label=="LONG":
            pl=pl_prev[i]
            if pl is None: continue
            sl=round(pl-0.5*atr_v,2)
            tp_info = tp_func_ph(i, entry, sl, atr_v)
            if tp_info is None: continue
            tp, tp_idx, conf_at = tp_info
        else:
            ph=ph_prev[i]
            if ph is None: continue
            sl=round(ph+0.5*atr_v,2)
            tp_info = tp_func_pl(i, entry, sl, atr_v)
            if tp_info is None: continue
            tp, tp_idx, conf_at = tp_info
        if sl is None or tp is None: continue
        if (dir_label=="LONG" and sl>=entry) or (dir_label=="SHORT" and sl<=entry): continue
        if dir_label=="LONG" and tp<=entry: tp=round(entry+abs(entry-sl),2)
        if dir_label=="SHORT" and tp>=entry: tp=round(entry-abs(sl-entry),2)
        risk=round(abs(entry-sl),2); reward=round(abs(tp-entry),2)
        rr=round(reward/risk,2) if risk>0 else 0

        idx=df[df["ora"]==pd.to_datetime(df.loc[i,"ora"])].index[0]
        result=None; exit_p=None; exit_idx=None
        for j in range(idx+1, n):
            if dir_label=="LONG":
                if df.loc[j,"low"]<=sl: result="SL"; exit_p=sl; exit_idx=j; break
                if df.loc[j,"high"]>=tp: result="TP"; exit_p=tp; exit_idx=j; break
            else:
                if df.loc[j,"high"]>=sl: result="SL"; exit_p=sl; exit_idx=j; break
                if df.loc[j,"low"]<=tp: result="TP"; exit_p=tp; exit_idx=j; break
        if result is None or exit_p is None: continue
        pnl=round(exit_p-entry,2) if dir_label=="LONG" else round(entry-exit_p,2)
        pnl_eur=round(pnl*1000-6,2)
        bars_held=exit_idx-i
        trades.append({"entry_date":df.loc[i,"ora"].strftime("%d/%m %H:%M"),
            "dir":dir_label,"entry":entry,"sl":sl,"tp":tp,"exit":round(exit_p,2),
            "result":result,"pnl":pnl,"pnl_eur":pnl_eur,"bars":bars_held,
            "tp_idx":tp_idx,"conf_at":conf_at,"entry_idx":i,"exit_idx":exit_idx})
    return trades

# ORIGINAL: TP = next pivot (any future pivot, may not be confirmed at exit)
def orig_tp_long(i, entry, sl, atr_v):
    tp_raw = ph_next_orig[i]
    if tp_raw is None: return None
    tp = round(tp_raw, 2)
    # Find pivot index
    for j in range(i+1, i+50):
        if j >= n: break
        if ph_flag[j] and abs(float(df.loc[j,"high"])-tp_raw)<0.01:
            return (tp, j, j+LOOKBACK)
    return (tp, i+99, i+99)

def orig_tp_short(i, entry, sl, atr_v):
    tp_raw = pl_next_orig[i]
    if tp_raw is None: return None
    tp = round(tp_raw, 2)
    for j in range(i+1, i+50):
        if j >= n: break
        if pl_flag[j] and abs(float(df.loc[j,"low"])-tp_raw)<0.01:
            return (tp, j, j+LOOKBACK)
    return (tp, i+99, i+99)

# CONFIRMED: TP only if pivot is confirmed by exit time
def conf_tp_long(i, entry, sl, atr_v):
    info = ph_next_conf[i]
    if info is None: return None
    tp, tp_idx, conf_at = info
    tp = round(tp, 2)
    if tp <= entry: return None  # use entry+risk
    return (tp, tp_idx, conf_at)

def conf_tp_short(i, entry, sl, atr_v):
    info = pl_next_conf[i]
    if info is None: return None
    tp, tp_idx, conf_at = info
    tp = round(tp, 2)
    if tp >= entry: return None
    return (tp, tp_idx, conf_at)

orig = simulate(orig_tp_long, orig_tp_short)
conf = simulate(conf_tp_long, conf_tp_short)

print("=== CONFRONTO: TP ORIGINALE vs TP CONFERMATO ===")
print(f"{'Metodo':<15} {'Trade':<8} {'Win':<8} {'Loss':<8} {'Win%':<8} {'PnL pt':<12} {'PnL EUR':<14} {'PF':<8}")
print("-"*75)
for name, trades in [("ORIGINALE", orig), ("CONFERMATO", conf)]:
    total=len(trades); wins=sum(1 for t in trades if t["result"]=="TP")
    losses=total-wins; wr=wins/total*100 if total else 0
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=sum(t["pnl_eur"] for t in trades)
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    print(f"{name:<15} {total:<8} {wins:<8} {losses:<8} {wr:<8.1f} {pnl_pts:<+12.2f} {pnl_eur:<+14.0f} {pf:<8.2f}")

# ANALYZE: how many TP exits happen before pivot confirmation?
print("\n=== ANALISI ANTICIPAZIONE TP ===")
premature = []
valid = []
for t in orig:
    if t["result"] == "TP":
        if t["exit_idx"] < t["conf_at"]:
            premature.append(t)
        else:
            valid.append(t)

print(f"TP totali: {len(premature)+len(valid)}")
print(f"TP PREMATURI (exit prima della conferma pivot): {len(premature)} ({len(premature)/(len(premature)+len(valid))*100:.0f}%)")
print(f"TP VALIDI (exit dopo conferma): {len(valid)} ({len(valid)/(len(premature)+len(valid))*100:.0f}%)")

if premature:
    pnl_prem = sum(t["pnl"] for t in premature)
    print(f"\nPnL contributo TP prematuri: {pnl_prem:+.2f} pt")
    print(f"Esempi:")
    for t in premature[:5]:
        print(f"  {t['entry_date']} {t['dir']:5} entry={t['entry']:<7.2f} -> {t['result']}@{t['exit']:<7.2f} "
              f"pnl={t['pnl']:+5.2f} ({t['bars']:2d} barre, "
              f"pivot@{t['tp_idx']} conferma@{t['conf_at']} exit@{t['exit_idx']})")

if valid:
    print(f"\nPnL contributo TP validi: {sum(t['pnl'] for t in valid):+.2f} pt")
