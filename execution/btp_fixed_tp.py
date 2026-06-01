"""
Test: TP fisso basato su ATR (entry +/- ATRxK).
Entry ST(30,1.5), SL pivot confermati, TP = entry +- ATR*K.
Zero look-ahead, TP determinato all'entry.
"""
import pandas as pd, numpy as np

SRC = "dati/btp_1h_full.txt"
ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

df = pd.read_csv(SRC, sep="\t", decimal=".")
df.columns=["data","open","high","low","close","volume"]
df["ora"]=pd.to_datetime(df["data"])
n=len(df)
high,low,close=df["high"].values,df["low"].values,df["close"].values

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

# --- Confirmed Pivots (SL) ---
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

# --- GRID: fixed TP = entry +/- ATRxK ---
tp_mults = [0.5, 0.8, 1.0, 1.2, 1.5, 1.7, 2.0, 2.5, 3.0]
results_full = []

for KMULT in tp_mults:
    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0

    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        flip_long=(prev==1 and pprev==-1); flip_short=(prev==-1 and pprev==1)

        if not in_trade:
            sd=None
            if flip_long: sd="LONG"
            elif flip_short: sd="SHORT"
            else: continue

            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break

            entry_price=float(df.loc[i,"open"]); entry_idx=i; atr_v=float(atr[i-1])
            if sd=="LONG":
                entry_dir="LONG"; sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                tp_price=entry_price+KMULT*atr_v
                if sl_price >= entry_price: sl_price=entry_price-2*atr_v
                if tp_price <= entry_price: tp_price=entry_price+KMULT*atr_v
            else:
                entry_dir="SHORT"; sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                tp_price=entry_price-KMULT*atr_v
                if sl_price <= entry_price: sl_price=entry_price+2*atr_v
                if tp_price >= entry_price: tp_price=entry_price-KMULT*atr_v
            in_trade=True; continue

        if in_trade:
            lo=float(low[i]); hi=float(high[i])
            exit_here=False; exit_p=0; reason=""
            if entry_dir=="LONG":
                if lo<=sl_price: exit_p=sl_price; exit_here=True; reason="SL"
                elif hi>=tp_price: exit_p=tp_price; exit_here=True; reason="TP"
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True; reason="TIME"
            else:
                if hi>=sl_price: exit_p=sl_price; exit_here=True; reason="SL"
                elif lo<=tp_price: exit_p=tp_price; exit_here=True; reason="TP"
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True; reason="TIME"
            if exit_here:
                pnl=round(exit_p-entry_price,2) if entry_dir=="LONG" else round(entry_price-exit_p,2)
                trades.append({"pnl":pnl,"reason":reason}); in_trade=False; continue

    if in_trade:
        pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
        trades.append({"pnl":pnl,"reason":"END"})

    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100

    eq=0; peak=0; max_dd=0
    for t in trades:
        eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)
    results_full.append({"mult":KMULT,"trades":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd,
        "tp_cnt":sum(1 for t in trades if t.get("reason")=="TP"),
        "sl_cnt":sum(1 for t in trades if t.get("reason")=="SL")})

print("=== TP FISSO: entry +/- ATRxK su FULL DATASET (7704 candele) ===\n")
r_sorted=sorted(results_full, key=lambda x:x["pf"], reverse=True)
print(f"{'ATRx':<6} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8} {'DD':<10} {'TP':<6} {'SL':<6}")
print("="*75)
for r in r_sorted:
    print(f"{r['mult']:<6} {r['trades']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f} {r['dd']:<10.0f} {r['tp_cnt']:<6} {r['sl_cnt']:<6}")

print(f"\nMIGLIORE: ATRx{r_sorted[0]['mult']} -> PF={r_sorted[0]['pf']:.2f} PnL={r_sorted[0]['pnl']:+.2f}pt")

# --- Also test on NEW data (27 febbraio) ---
print("\n\n=== TEST SU NUOVI DATI (27 febbraio.txt) ===")
df2 = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
df2.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df2[c]=df2[c].astype(float)
df2["ora"]=pd.to_datetime(df2["data"], format="%d/%m/%Y %H:%M:%S")
n2=len(df2)
h2,l2,c2=df2["high"].values,df2["low"].values,df2["close"].values

# ATR on new data
tr2=np.maximum(h2-l2,np.maximum(np.abs(h2-np.roll(c2,1)),np.abs(l2-np.roll(c2,1))))
tr2[0]=h2[0]-l2[0]; atr2=np.zeros(n2); alpha=1/ST_PERIOD; atr2[0]=tr2[0]
for i in range(1,n2): atr2[i]=atr2[i-1]+alpha*(tr2[i]-atr2[i-1])

# ST on new data
hl2_2=(h2+l2)/2; fu2=np.zeros(n2); fl2=np.zeros(n2); st2=np.zeros(n2); dir2=np.ones(n2,dtype=int)
for i in range(n2):
    if i==0: fu2[i]=hl2_2[i]+ST_MULT*atr2[i]; fl2[i]=hl2_2[i]-ST_MULT*atr2[i]; st2[i]=fu2[i]; dir2[i]=-1; continue
    pc=c2[i-1]; ub=hl2_2[i]+ST_MULT*atr2[i]; lb=hl2_2[i]-ST_MULT*atr2[i]
    fu2[i]=ub if (ub<fu2[i-1] or pc>fu2[i-1]) else fu2[i-1]
    fl2[i]=lb if (lb>fl2[i-1] or pc<fl2[i-1]) else fl2[i-1]
    if st2[i-1]==fu2[i-1]:
        if c2[i]>fu2[i]: st2[i]=fl2[i]; dir2[i]=1
        else: st2[i]=fu2[i]; dir2[i]=-1
    else:
        if c2[i]<fl2[i]: st2[i]=fu2[i]; dir2[i]=-1
        else: st2[i]=fl2[i]; dir2[i]=1

# Confirmed pivots on new data
ph2=np.full(n2,False); pl2=np.full(n2,False)
for i in range(LOOKBACK, n2-LOOKBACK):
    if all(df2.loc[i,"high"]>df2.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
       all(df2.loc[i,"high"]>df2.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph2[i]=True
    if all(df2.loc[i,"low"]<df2.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
       all(df2.loc[i,"low"]<df2.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl2[i]=True

results_new = []
for KMULT in tp_mults:
    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0
    for i in range(ST_PERIOD+2, n2):
        prev=dir2[i-1]; pprev=dir2[i-2]
        fl=(prev==1 and pprev==-1); fs=(prev==-1 and pprev==1)
        if not in_trade:
            sd=None
            if fl: sd="LONG"
            elif fs: sd="SHORT"
            else: continue
            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph2[j]: cp_high=float(df2.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl2[j]: cp_low=float(df2.loc[j,"low"]); break
            entry_price=float(df2.loc[i,"open"]); entry_idx=i; atr_v=float(atr2[i-1])
            if sd=="LONG":
                entry_dir="LONG"; sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                tp_price=entry_price+KMULT*atr_v
            else:
                entry_dir="SHORT"; sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                tp_price=entry_price-KMULT*atr_v
            in_trade=True; continue
        if in_trade:
            lo=float(l2[i]); hi=float(h2[i])
            exit_here=False; exit_p=0
            if entry_dir=="LONG":
                if lo<=sl_price: exit_p=sl_price; exit_here=True
                elif hi>=tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(c2[i]); exit_here=True
            else:
                if hi>=sl_price: exit_p=sl_price; exit_here=True
                elif lo<=tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(c2[i]); exit_here=True
            if exit_here:
                pnl=round(exit_p-entry_price,2) if entry_dir=="LONG" else round(entry_price-exit_p,2)
                trades.append({"pnl":pnl}); in_trade=False; continue
    if in_trade:
        pnl=round(float(c2[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(c2[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100
    results_new.append({"mult":KMULT,"trades":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf})

r_new=sorted(results_new, key=lambda x:x["pf"], reverse=True)
print(f"{'ATRx':<6} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8}")
print("="*55)
for r in r_new:
    print(f"{r['mult']:<6} {r['trades']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f}")

print(f"\nMIGLIORE su nuovi: ATRx{r_new[0]['mult']} -> PF={r_new[0]['pf']:.2f} PnL={r_new[0]['pnl']:+.2f}pt")

# --- Comparison ---
print("\n\n=== CONFRONTO FINALE: TP FISSO vs ATR TRAILING ===")
best_fixed_full = max(results_full, key=lambda x:x["pf"])
best_fixed_new = max(results_new, key=lambda x:x["pf"])

print(f"{'Strategia':<35} {'Dataset':<12} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PF':<8}")
print("="*82)
print(f"{'Originale pivot (LOOK-AHEAD)':<35} {'7704 candele':<12} {'559':<7} {'81.4':<8} {'+181.00':<10} {'3.78':<8}")
print(f"{'Originale pivot (LOOK-AHEAD)':<35} {'27 feb nuovo':<12} {'51':<7} {'88.2':<8} {'+31.13':<10} {'3.78':<8}")
print(f"{'ATR trailing 2.0+NOT_BEAR':<35} {'7704 candele':<12} {'493':<7} {'42.2':<8} {'+15.71':<10} {'1.23':<8}")
print(f"{'ATR trailing 3.0+NOT_BULL':<35} {'27 feb nuovo':<12} {'33':<7} {'48.5':<8} {'+7.21':<10} {'1.99':<8}")
print(f"{'TP FISSO ATRx'+str(best_fixed_full['mult']):<35} {'7704 candele':<12} {best_fixed_full['trades']:<7} {best_fixed_full['wr']:<8.1f} {best_fixed_full['pnl']:<+10.2f} {best_fixed_full['pf']:<8.2f}")
print(f"{'TP FISSO ATRx'+str(best_fixed_new['mult']):<35} {'27 feb nuovo':<12} {best_fixed_new['trades']:<7} {best_fixed_new['wr']:<8.1f} {best_fixed_new['pnl']:<+10.2f} {best_fixed_new['pf']:<8.2f}")
