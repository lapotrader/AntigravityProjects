import pandas as pd
import numpy as np
from numba import jit
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"

cols = ["datetime","h","l","o","c","v"]
df = pd.read_csv(base + "/dati/ultimissimi5giugno.txt", sep="\t", header=None, names=cols)
df["dt"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M:%S")
df = df.set_index("dt").drop(columns=["datetime"])
df = df.astype(float)
df.columns = ["high","low","open","close","volume"]

h_arr = df["high"].values.astype(np.float64)
l_arr = df["low"].values.astype(np.float64)
c_arr = df["close"].values.astype(np.float64)
o_arr = df["open"].values.astype(np.float64)
n_bars = len(df)

@jit(nopython=True)
def st(h,l,c,p,m):
    n=len(h);d=np.ones(n);tr=np.zeros(n);a=np.zeros(n);s2=np.zeros(n)
    fu=np.zeros(n);fl=np.zeros(n)
    for i in range(1,n):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    s=0.0
    for i in range(1,p):s+=tr[i]
    a[p]=s/p
    for i in range(p+1,n):a[i]=(a[i-1]*(p-1)+tr[i])/p
    for i in range(p,n):
        hl=(h[i]+l[i])/2;ub=hl+m*a[i];lb=hl-m*a[i]
        if i==p:fu[i]=ub;fl[i]=lb;s2[i]=ub;d[i]=-1
        else:
            fu[i]=ub if(ub<fu[i-1])or(c[i-1]>fu[i-1])else fu[i-1]
            fl[i]=lb if(lb>fl[i-1])or(c[i-1]<fl[i-1])else fl[i-1]
            if d[i-1]==1:
                s2[i]=fl[i]
                if c[i]<=fl[i]:d[i]=-1;s2[i]=fu[i]
                else:d[i]=1
            else:
                s2[i]=fu[i]
                if c[i]>=fu[i]:d[i]=1;s2[i]=fl[i]
                else:d[i]=-1
    return d,s2

comm_pt = 3/25
slip = 1.0

def in_fascia(hr, mn):
    return (hr>=9 and hr<11) or (hr==15 and mn>=30) or (hr>=16 and hr<17) or (hr==17 and mn<=30)

def is_after_22(hr):
    return hr >= 22

d, s2 = st(h_arr, l_arr, c_arr, 10, 3.0)

trades = []
pos, ep = 0, 0.0
entry_dt, entry_px = None, None
entry_raw_open = None
entry_bar = 0

for i in range(20, n_bars):
    if i+1 >= n_bars: continue
    dt_next = df.index[i+1]
    hr_n, mn_n = dt_next.hour, dt_next.minute
    dt_curr = df.index[i]
    overnight_gap = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

    if pos != 0 and (is_after_22(hr_n) or overnight_gap):
        if overnight_gap and not is_after_22(hr_n):
            ex = c_arr[i] - slip if pos == 1 else c_arr[i] + slip
            exit_dt_actual = dt_curr
            if pos == 1: pnl = ex - ep - comm_pt
            else: pnl = ep - ex - comm_pt
            trades.append({"entry_dt": entry_dt, "exit_dt": exit_dt_actual,
                           "entry_raw_open": entry_raw_open, "entry_px": entry_px,
                           "exit_px": ex, "exit_raw_open": c_arr[i],
                           "pnl_pt": pnl, "dir": "LONG" if pos==1 else "SHORT",
                           "type": "FORCED", "entry_bar": entry_bar, "exit_bar": i})
        else:
            ex = o_arr[i+1]
            if pos == 1: pnl = ex - ep - comm_pt - slip
            else: pnl = ep - ex - comm_pt - slip
            trades.append({"entry_dt": entry_dt, "exit_dt": dt_next,
                           "entry_raw_open": entry_raw_open, "entry_px": entry_px,
                           "exit_px": ex, "exit_raw_open": o_arr[i+1],
                           "pnl_pt": pnl, "dir": "LONG" if pos==1 else "SHORT",
                           "type": "FORCED", "entry_bar": entry_bar, "exit_bar": i+1})
        pos = 0

    if pos != 0:
        if pos == 1 and d[i-1]==1 and d[i]==-1:
            ex = o_arr[i+1] - slip
            pnl = ex - ep - comm_pt
            trades.append({"entry_dt": entry_dt, "exit_dt": dt_next,
                           "entry_raw_open": entry_raw_open, "entry_px": entry_px,
                           "exit_px": ex, "exit_raw_open": o_arr[i+1],
                           "pnl_pt": pnl, "dir": "LONG", "type": "REVERSAL",
                           "entry_bar": entry_bar, "exit_bar": i+1})
            pos = 0
        elif pos == -1 and d[i-1]==-1 and d[i]==1:
            ex = o_arr[i+1] + slip
            pnl = ep - ex - comm_pt
            trades.append({"entry_dt": entry_dt, "exit_dt": dt_next,
                           "entry_raw_open": entry_raw_open, "entry_px": entry_px,
                           "exit_px": ex, "exit_raw_open": o_arr[i+1],
                           "pnl_pt": pnl, "dir": "SHORT", "type": "REVERSAL",
                           "entry_bar": entry_bar, "exit_bar": i+1})
            pos = 0

    if pos == 0 and in_fascia(hr_n, mn_n):
        if d[i]==1 and d[i-1]==-1:
            pos = 1; ep = o_arr[i+1] + slip
            entry_dt = dt_next; entry_px = o_arr[i+1] + slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1
        elif d[i]==-1 and d[i-1]==1:
            pos = -1; ep = o_arr[i+1] - slip
            entry_dt = dt_next; entry_px = o_arr[i+1] - slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1

pnls = np.array([t["pnl_pt"] for t in trades])

def apply_cb(p, ml, cd):
    kept=[];c=0;r=0
    for j,val in enumerate(p):
        if r>0: r-=1; continue
        if val<0: c+=1
        else: c=0
        if c>=ml: r=cd;c=0; continue
        kept.append(j)
    return np.array([p[i] for i in kept]), np.array(kept)

kept, idx = apply_cb(pnls, 2, 3)
kept_trades = [trades[i] for i in idx]
last_10 = kept_trades[-10:]

pnls_10 = np.array([t["pnl_pt"] for t in last_10])
tot_pnl = pnls_10.sum() * 25
wins = sum(1 for t in last_10 if t["pnl_pt"] > 0)
losses = sum(1 for t in last_10 if t["pnl_pt"] < 0)

print(f"File: {n_bars} barre, {df.index[0]} -> {df.index[-1]}")
print(f"Trade totali: {len(trades)} | Dopo CB: {len(kept_trades)}")
print(f"")
print(f"{'='*95}")
print(f"ULTIMI 10 TRADE (sui tuoi dati aggiornati)")
print(f"{'='*95}")
print(f"{'Entry':<18} {'Exit':<18} {'Dir':<6} {'Entry px':<10} {'Exit px':<10} {'PnL pt':<10} {'PnL eur':<12} {'Type':<10}")
print(f"{'-'*95}")

for t in reversed(last_10):
    e = t["entry_dt"].strftime('%d/%m %H:%M')
    x = t["exit_dt"].strftime('%d/%m %H:%M')
    d = "LONG" if t["dir"]=="LONG" else "SHORT"
    pnl_pt = t["pnl_pt"]
    pnl_eur = pnl_pt * 25
    c = "+" if pnl_pt >= 0 else ""
    print(f"{e:<18} {x:<18} {d:<6} {t['entry_px']:<10.1f} {t['exit_px']:<10.1f} {c}{pnl_pt:<+8.2f}  {c}{pnl_eur:>+8,.0f} EUR  {t['type']:<10}")

print(f"{'-'*95}")
print(f"TOTALE: {tot_pnl:+.0f} EUR | {wins}W/{losses}L")

# Posizione aperta attuale
if pos != 0:
    print(f"\n{'='*95}")
    print(f"POSIZIONE APERTA: {d_str} dal {entry_dt} a {ep:.1f}")
else:
    print(f"\nNessuna posizione aperta.")

# Direzione ST attuale
st_current = d[-1]
st_prev = d[-2]
print(f"SuperTrend attuale: {'LONG' if st_current==1 else 'SHORT'} (precedente: {'LONG' if st_prev==1 else 'SHORT'})")
if st_current != st_prev:
    print(f">>> REVERSAL appena avvenuto!")
