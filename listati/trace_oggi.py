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

# Trace l'esecuzione intorno al 05/06
print("TRADE LOG dettagliato — cerca trade del 05/06:")
print()
trades_all = []
pos, ep = 0, 0.0
entry_dt, entry_px = None, None
entry_raw_open = None
entry_bar = 0

for i in range(20, len(df)):
    if i+1 >= len(df): continue
    dt_next = df.index[i+1]
    hr_n, mn_n = dt_next.hour, dt_next.minute
    dt_curr = df.index[i]
    overnight_gap = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

    if pos != 0 and (is_after_22(hr_n) or overnight_gap):
        if overnight_gap and not is_after_22(hr_n):
            ex = c_arr[i]
            exit_dt_actual = dt_curr
            if pos == 1: pnl = ex - ep - comm_pt
            else: pnl = ep - ex - comm_pt
        else:
            ex = o_arr[i+1]
            exit_dt_actual = dt_next
            if pos == 1: pnl = ex - ep - comm_pt - slip
            else: pnl = ep - ex - comm_pt - slip
        
        t = {"entry": entry_dt, "exit": exit_dt_actual, "dir": "LONG" if pos==1 else "SHORT",
             "epx": entry_px, "epx_raw": entry_raw_open, "exx": ex, "pnl": pnl, "type": "FORCED"}
        trades_all.append(t)
        pos = 0
        
        if entry_dt is not None and entry_dt.date() == pd.Timestamp("2026-06-05").date():
            print("  FORCED EXIT: {} -> {} {} ep={:.1f} ex={:.1f} pnl={:+.2f}".format(
                entry_dt, exit_dt_actual, t["dir"], entry_px, ex, pnl))

    if pos != 0:
        if pos == 1 and d[i-1]==1 and d[i]==-1:
            ex = o_arr[i+1] - slip
            pnl = ex - ep - comm_pt
            t = {"entry": entry_dt, "exit": dt_next, "dir": "LONG",
                 "epx": entry_px, "epx_raw": entry_raw_open, "exx": ex, "pnl": pnl, "type": "REVERSAL"}
            trades_all.append(t)
            pos = 0
            if entry_dt is not None and entry_dt.date() == pd.Timestamp("2026-06-05").date():
                print("  REV EXIT LONG: {} -> {} ep={:.1f} ex={:.1f} pnl={:+.2f}".format(
                    entry_dt, dt_next, entry_px, ex, pnl))
        elif pos == -1 and d[i-1]==-1 and d[i]==1:
            ex = o_arr[i+1] + slip
            pnl = ep - ex - comm_pt
            t = {"entry": entry_dt, "exit": dt_next, "dir": "SHORT",
                 "epx": entry_px, "epx_raw": entry_raw_open, "exx": ex, "pnl": pnl, "type": "REVERSAL"}
            trades_all.append(t)
            pos = 0
            if entry_dt is not None and entry_dt.date() == pd.Timestamp("2026-06-05").date():
                print("  REV EXIT SHORT: {} -> {} ep={:.1f} ex={:.1f} pnl={:+.2f}".format(
                    entry_dt, dt_next, entry_px, ex, pnl))

    if pos == 0 and in_fascia(hr_n, mn_n):
        if d[i]==1 and d[i-1]==-1:
            pos = 1; ep = o_arr[i+1] + slip
            entry_dt = dt_next; entry_px = o_arr[i+1] + slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1
            if entry_dt.date() == pd.Timestamp("2026-06-05").date():
                print("  ENTRY LONG: {} open={:.1f} ep={:.1f}".format(dt_next, o_arr[i+1], ep))
        elif d[i]==-1 and d[i-1]==1:
            pos = -1; ep = o_arr[i+1] - slip
            entry_dt = dt_next; entry_px = o_arr[i+1] - slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1
            if entry_dt.date() == pd.Timestamp("2026-06-05").date():
                print("  ENTRY SHORT: {} open={:.1f} ep={:.1f}".format(dt_next, o_arr[i+1], ep))

print()
print("RIEPILOGO:")
print("  Trade totali generati:", len(trades_all))
pnls = np.array([t["pnl"] for t in trades_all])

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
kept_trades = [trades_all[i] for i in idx]
print("  Dopo CB:", len(kept_trades))

# Mostra gli ultimi 5 trade
print()
print("ULTIMI 5 TRADE (con CB):")
for t in kept_trades[-5:]:
    if t["entry"] is None: continue
    d = t["dir"]
    c = "+" if t["pnl"] >= 0 else ""
    print("  {} -> {} {} entry={:.1f} exit={:.1f} pnl={}{:+.2f} {}".format(
        t["entry"].strftime('%d/%m %H:%M'), t["exit"].strftime('%d/%m %H:%M'),
        d, t["epx"], t["exx"], c, t["pnl"], t["type"]))
