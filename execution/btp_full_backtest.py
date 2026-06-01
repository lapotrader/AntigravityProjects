"""
Backtest full 2.7 anni: ST(30,1.5) entry + pivot confermati SL + ATR trailing + filtri.
Dataset: btp_1h_full.txt
"""
import pandas as pd, numpy as np

SRC = "dati/btp_1h_full.txt"
ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

df = pd.read_csv(SRC, sep="\t", decimal=".")
# already has header: data, open, high, low, close, volume
df.columns=["data","open","high","low","close","volume"]
df["ora"]=pd.to_datetime(df["data"])
n=len(df)
high,low,close=df["high"].values,df["low"].values,df["close"].values
print(f"Full dataset: {df['ora'].iloc[0]} -> {df['ora'].iloc[-1]} ({n} candles)")

# --- ATR ---
tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

# --- ST ---
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

# --- Confirmed Pivots (no look-ahead) ---
ph_raw=np.full(n,False); pl_raw=np.full(n,False)
for i in range(LOOKBACK, n-LOOKBACK):
    if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_raw[i]=True
    if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_raw[i]=True

# --- Markov filter ---
returns=close/np.roll(close,1)-1; returns[0]=0
vol_rolling=pd.Series(returns).rolling(50).std().values
vol_prev=np.roll(vol_rolling,1); vol_prev[0]=vol_rolling[0]
state=np.full(n,"Sideways")
for i in range(1,n):
    if returns[i]>vol_prev[i]: state[i]="Bull"
    elif returns[i]<-vol_prev[i]: state[i]="Bear"

# --- GRID ---
results = []
for TRAIL_MULT in [2.0, 2.5, 3.0, 3.5, 4.0]:
    filters = [
        ("NO_FILTER", lambda i,dir: True),
        ("NOT_BULL_SHORT", lambda i,dir: not (dir=="SHORT" and state[i]=="Bull")),
        ("MARKOV_SW", lambda i,dir: state[i]=="Sideways"),
        ("NOT_BEAR_LONG", lambda i,dir: not (dir=="LONG" and state[i]=="Bear")),
    ]
    for fname, filt_fn in filters:
        trades=[]; in_trade=False
        entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; trail_stop=0

        for i in range(ST_PERIOD+2, n):
            prev=direction[i-1]; pprev=direction[i-2]
            flip_long=(prev==1 and pprev==-1); flip_short=(prev==-1 and pprev==1)

            if not in_trade:
                sd=None
                if flip_long: sd="LONG"
                elif flip_short: sd="SHORT"
                else: continue
                if not filt_fn(i, sd): continue

                cp_high=None; cp_low=None
                for j in range(i-5, -1, -1):
                    if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
                for j in range(i-5, -1, -1):
                    if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break

                entry_price=float(df.loc[i,"open"]); entry_idx=i; atr_v=float(atr[i-1])
                if sd=="LONG":
                    entry_dir="LONG"
                    sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                else:
                    entry_dir="SHORT"
                    sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                trail_stop=sl_price; in_trade=True; continue

            if in_trade:
                hi=float(high[i]); lo=float(low[i]); atr_v=float(atr[i-1])
                if entry_dir=="LONG":
                    trail_stop=max(sl_price, hi-TRAIL_MULT*atr_v, trail_stop)
                    exit_here=False; exit_p=0
                    if lo<=trail_stop: exit_p=trail_stop; exit_here=True
                    elif flip_short: exit_p=float(df.loc[i,"open"]); exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                    if exit_here:
                        trades.append({"pnl":round(exit_p-entry_price,2)}); in_trade=False; continue
                else:
                    trail_stop=min(sl_price, lo+TRAIL_MULT*atr_v, trail_stop)
                    exit_here=False; exit_p=0
                    if hi>=trail_stop: exit_p=trail_stop; exit_here=True
                    elif flip_long: exit_p=float(df.loc[i,"open"]); exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                    if exit_here:
                        trades.append({"pnl":round(entry_price-exit_p,2)}); in_trade=False; continue

        if in_trade:
            pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
            trades.append({"pnl":pnl})

        total=len(trades)
        if total<5: continue
        wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
        pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
        pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
        wr=wins/total*100

        eq=0; peak=0; max_dd=0
        for t in trades:
            eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)

        sharpe_approx = (pnl_pts/total*252*8.5) / (np.std([t["pnl"] for t in trades])+0.001)

        results.append({"mult":TRAIL_MULT,"filtro":fname,"trades":total,"wr":wr,
            "pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd})

# --- Results ---
r_sorted=sorted(results, key=lambda x:x["pf"], reverse=True)
print(f"\n{'ATRx':<6} {'Filtro':<18} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8} {'DD':<10}")
print("="*80)
for r in r_sorted:
    print(f"{r['mult']:<6} {r['filtro']:<18} {r['trades']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f} {r['dd']:<10.0f}")

print(f"\n=== TOP 10 per PF ===")
for r in r_sorted[:10]:
    print(f"  ATRx{r['mult']} + {r['filtro']:<18} T={r['trades']:<4} WR={r['wr']:<5.1f} PnL={r['pnl']:<+7.2f}pt PF={r['pf']:<5.2f} DD={r['dd']:<.0f}")

# Confronto con originale
print(f"\n=== CONFRONTO CON ORIGINALE (full dataset) ===")
print(f"  Originale pivot (look-ahead su 7704 candele): 559 trade, 81.4% WR, +181pt, PF=3.78")
best=r_sorted[0]
print(f"  MIGLIORE onesto: ATRx{best['mult']} + {best['filtro']:<18} T={best['trades']:<4} WR={best['wr']:<5.1f} PnL={best['pnl']:<+7.2f}pt PF={best['pf']:<5.2f}")
