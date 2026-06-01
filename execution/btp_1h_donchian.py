"""
Test: Donchian trailing exit (= pivot stimato via canale N barre).
Entry ST(30,1.5), SL su pivot confermati, TP trailing su canale N barre (lowest low / highest high).
Zero look-ahead.
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

# --- GRID: Donchian channel lengths ---
results = []
channel_lens = [3, 5, 7, 8, 10, 13, 15, 20]
for CHAN_LEN in channel_lens:
    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0
    donchian_stop=0  # trailing stop based on channel

    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        flip_long=(prev==1 and pprev==-1)
        flip_short=(prev==-1 and pprev==1)

        if not in_trade:
            signal_dir=None
            if flip_long: signal_dir="LONG"
            elif flip_short: signal_dir="SHORT"
            else: continue
            if state[i]=="Bull" and signal_dir=="SHORT": continue  # NOT_BULL_SHORT filter
            if state[i]=="Bear" and signal_dir=="LONG": continue   # NOT_BEAR_LONG filter

            # Confirmed pivot SL
            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break

            entry_price=float(df.loc[i,"open"]); entry_idx=i; atr_v=float(atr[i-1])
            if signal_dir=="LONG":
                entry_dir="LONG"
                sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                donchian_stop=sl_price
            else:
                entry_dir="SHORT"
                sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                donchian_stop=sl_price
            in_trade=True; continue

        if in_trade:
            lo=float(low[i]); hi=float(high[i])
            if entry_dir=="LONG":
                # Donchian: exit at lowest low of last CHAN_LEN candles
                if i-CHAN_LEN >= entry_idx:
                    chan_low = float(min(low[i-CHAN_LEN:i+1]))
                    donchian_stop = max(sl_price, chan_low, donchian_stop)
                exit_here=False; exit_p=0
                if lo <= donchian_stop: exit_p=donchian_stop; exit_here=True
                elif flip_short: exit_p=float(df.loc[i,"open"]); exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                if exit_here:
                    pnl=round(exit_p-entry_price,2); trades.append({"pnl":pnl}); in_trade=False; continue
            else:
                if i-CHAN_LEN >= entry_idx:
                    chan_high = float(max(high[i-CHAN_LEN:i+1]))
                    donchian_stop = min(sl_price, chan_high, donchian_stop)
                exit_here=False; exit_p=0
                if hi>=donchian_stop: exit_p=donchian_stop; exit_here=True
                elif flip_long: exit_p=float(df.loc[i,"open"]); exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                if exit_here:
                    pnl=round(entry_price-exit_p,2); trades.append({"pnl":pnl}); in_trade=False; continue

    if in_trade:
        pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
        trades.append({"pnl":pnl})

    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0

    eq=0; peak=0; max_dd=0
    for t in trades:
        eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)
    results.append({"chan":CHAN_LEN,"trades":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd})

r_sorted=sorted(results,key=lambda x:x["pnl_eur"],reverse=True)
print(f"{'Canale':<8} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8} {'DD':<10}")
print("="*65)
for r in r_sorted:
    print(f"{r['chan']:<8} {r['trades']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f} {r['dd']:<10.0f}")

best=r_sorted[0]
print(f"\nMIGLIORE: Canale {best['chan']} barre -> PnL {best['pnl']:+.2f}pt ({best['pnl_eur']:+.0f}EUR)")
print(f"   WR={best['wr']:.1f}% PF={best['pf']:.2f} DD={best['dd']:.0f}EUR")

# --- Confronto finale ---
print("\n=== CONFRONTO COMPLETO ===")
configs = [
    ("Originale pivot (LOOK-AHEAD)", 51, 88.2, +31.13, +30824, 3.78),
    ("ATR x3.0 + NOT_BULL_SHORT", 33, 48.5, +7.21, +7012, 1.99),
]
if r_sorted:
    b=r_sorted[0]
    configs.append((f"Donchian {b['chan']}bar + filtro", b['trades'], b['wr'], b['pnl'], b['pnl_eur'], b['pf']))

print(f"{'Strategia':<35} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8}")
print("="*88)
for name,tr,wr,pnl,peur,pf in configs:
    print(f"{name:<35} {tr:<7} {wr:<8.1f} {pnl:<+10.2f} {peur:<+14.0f} {pf:<8.2f}")
