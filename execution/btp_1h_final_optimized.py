"""
BTP 1h — Strategia Finale: ST(30,1.5) entry + ATR trailing exit + Filtri HMM.
Zero look-ahead, 100% live-replicabile.
Grid search su ATR mult × regime filter × volatilita filter × ora filter.
"""
import pandas as pd, numpy as np, os, json
from hmmlearn import hmm
import warnings; warnings.filterwarnings('ignore')

PATH = "dati/27 febbraio.txt"
ST_PERIOD = 30; ST_MULT = 1.5; LOOKBACK = 5

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns = ["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df[c] = df[c].astype(float)
df["ora"] = pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
n = len(df)
print(f"BTP 1h - OPTIMIZATION: ST({ST_PERIOD},{ST_MULT}) + ATR trailing + filters")
print(f"Dati: {df['ora'].iloc[0]} -> {df['ora'].iloc[-1]} ({n} candles)\n")

high, low, close = df["high"].values, df["low"].values, df["close"].values

# --- ATR ---
tr = np.maximum(high-low, np.maximum(np.abs(high-np.roll(close,1)), np.abs(low-np.roll(close,1))))
tr[0]=high[0]-low[0]
atr = np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

# --- SuperTrend ---
hl2=(high+low)/2
final_ub=np.zeros(n); final_lb=np.zeros(n); st=np.zeros(n)
direction=np.ones(n, dtype=int)
for i in range(n):
    if i==0:
        final_ub[i]=hl2[i]+ST_MULT*atr[i]; final_lb[i]=hl2[i]-ST_MULT*atr[i]
        st[i]=final_ub[i]; direction[i]=-1; continue
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

# --- FILTERS: Markov Regime (1h) ---
returns = close / np.roll(close, 1) - 1; returns[0] = 0
vol_window = 50
vol_rolling = pd.Series(returns).rolling(vol_window).std().values
vol_prev = np.roll(vol_rolling, 1); vol_prev[0] = vol_rolling[0]

# Markov state: Bull if return > 1σ, Bear if < -1σ, else Sideways
state = np.full(n, "Sideways")
for i in range(1, n):
    if returns[i] > vol_prev[i]: state[i] = "Bull"
    elif returns[i] < -vol_prev[i]: state[i] = "Bear"

# --- FILTERS: HMM (2 states: low/high vol) ---
# Use last 200 candles for HMM training
hmm_train_start = max(0, n-200)
train_returns = returns[hmm_train_start+1:n].reshape(-1, 1)
try:
    hmm_model = hmm.GaussianHMM(n_components=2, covariance_type="full", n_iter=100, random_state=42)
    hmm_model.fit(train_returns)
    hmm_states = hmm_model.predict(train_returns)
    # Map: state 0 = low vol (Sideways), state 1 = high vol (Trend)
    vol_by_state = [np.std(train_returns[hmm_states==s]) for s in range(2)]
    low_vol_state = np.argmin(vol_by_state)
    hmm_sideways = np.full(n, False)
    for j, s in enumerate(hmm_states):
        hmm_sideways[hmm_train_start+1+j] = (s == low_vol_state)
except:
    hmm_sideways = np.full(n, True)
    print("HMM fallito, skip filtro HMM")

# --- GRID SEARCH ---
results = []
atr_mults = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
filters = [
    {"name": "NO_FILTER",     "fn": lambda i, dir: True},
    {"name": "MARKOV_SW",     "fn": lambda i, dir: state[i] == "Sideways"},
    {"name": "HMM_SW",        "fn": lambda i, dir: hmm_sideways[i]},
    {"name": "NOT_BEAR_LONG", "fn": lambda i, dir: not (dir=="LONG" and state[i]=="Bear")},
    {"name": "NOT_BULL_SHORT","fn": lambda i, dir: not (dir=="SHORT" and state[i]=="Bull")},
    {"name": "SEMAFORO",      "fn": lambda i, dir: state[i]=="Sideways" and hmm_sideways[i]},
]

for TRAIL_MULT in atr_mults:
    for flt in filters:
        trades = []; in_trade = False
        entry_price=0; entry_idx=0; entry_dir=""
        trailing_stop=0; sl_price=0

        for i in range(ST_PERIOD+2, n):
            prev=direction[i-1]; pprev=direction[i-2]
            flip_long=(prev==1 and pprev==-1)
            flip_short=(prev==-1 and pprev==1)

            if not in_trade:
                signal_dir = None
                if flip_long: signal_dir = "LONG"
                elif flip_short: signal_dir = "SHORT"
                else: continue

                # Apply filter
                if not flt["fn"](i, signal_dir): continue

                # Last CONFIRMED pivot (j <= i-5)
                cp_high=None; cp_low=None
                for j in range(i-5, -1, -1):
                    if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
                for j in range(i-5, -1, -1):
                    if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break

                entry_price=float(df.loc[i,"open"]); entry_idx=i
                atr_v=float(atr[i-1])

                if signal_dir=="LONG":
                    entry_dir="LONG"
                    sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                else:
                    entry_dir="SHORT"
                    sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)

                trailing_stop=sl_price
                in_trade=True; continue

            if in_trade:
                hi=float(high[i]); lo=float(low[i])
                atr_v=float(atr[i-1])

                if entry_dir=="LONG":
                    new_trail=hi-TRAIL_MULT*atr_v
                    trailing_stop=max(sl_price, new_trail, trailing_stop)
                    exit_here=False; exit_p=0
                    if lo<=trailing_stop: exit_p=trailing_stop; exit_here=True
                    elif flip_short: exit_p=float(df.loc[i,"open"]); exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                    if exit_here:
                        trades.append({"pnl":round(exit_p-entry_price,2)})
                        in_trade=False; continue
                else:
                    new_trail=lo+TRAIL_MULT*atr_v
                    trailing_stop=min(sl_price, new_trail, trailing_stop)
                    exit_here=False; exit_p=0
                    if hi>=trailing_stop: exit_p=trailing_stop; exit_here=True
                    elif flip_long: exit_p=float(df.loc[i,"open"]); exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                    if exit_here:
                        trades.append({"pnl":round(entry_price-exit_p,2)})
                        in_trade=False; continue

        if in_trade:
            pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
            trades.append({"pnl":pnl})

        total=len(trades)
        if total<3: continue
        wins=sum(1 for t in trades if t["pnl"]>0)
        losses=total-wins
        pnl_pts=sum(t["pnl"] for t in trades)
        pnl_eur=pnl_pts*1000-total*6
        pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
        wr=wins/total*100

        # Max DD
        eq=0; peak=0; max_dd=0
        for t in trades:
            eq+=t["pnl"]*1000-6
            peak=max(peak, eq); max_dd=min(max_dd, eq-peak)

        results.append({"mult":TRAIL_MULT, "filter":flt["name"],
            "trades":total, "wr":wr, "pnl":pnl_pts, "pnl_eur":pnl_eur,
            "pf":pf, "dd":max_dd, "dd_pct":round(abs(max_dd)/50000*100,1)})

# --- Results Table ---
r_sorted = sorted(results, key=lambda x:x["pnl_eur"], reverse=True)
print(f"{'ATRx':<6} {'Filtro':<18} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<12} {'PF':<8} {'DD':<8}")
print("="*80)
for r in r_sorted:
    print(f"{r['mult']:<6} {r['filter']:<18} {r['trades']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+12.0f} {r['pf']:<8.2f} {r['dd']:<8.0f}")

# --- Best config ---
best = r_sorted[0]
print(f"\nMIGLIORE: ATR x{best['mult']} + {best['filter']}")
print(f"  Trade: {best['trades']} | Win: {best['wr']:.1f}% | PnL: {best['pnl']:+.2f}pt ({best['pnl_eur']:+.0f}EUR)")
print(f"  PF: {best['pf']:.2f} | MaxDD: {best['dd']:.0f}EUR ({best['dd_pct']}%)")

# --- Top 10 ---
print("\n--- TOP 10 CONFIG ---")
for r in r_sorted[:10]:
    print(f"  {r['filter']:<18} ATRx{r['mult']:<5} Trade={r['trades']:<4} WR={r['wr']:<6.1f} PnL={r['pnl']:<+8.2f}pt PF={r['pf']:<6.2f} DD={r['dd']:<6.0f}")

# --- Summary by filter ---
print("\n--- BEST PER FILTER ---")
for flt in filters:
    best_f = max([r for r in results if r["filter"]==flt["name"]], key=lambda x:x["pnl_eur"], default=None)
    if best_f:
        print(f"  {best_f['filter']:<18} ATRx{best_f['mult']:<4} T={best_f['trades']:<3} WR={best_f['wr']:<5.1f} PnL={best_f['pnl']:<+7.2f}pt PF={best_f['pf']:<5.2f}")
