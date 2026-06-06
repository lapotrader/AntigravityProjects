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

# Genera trade + traccia CB
trades = []
pos, ep = 0, 0.0
entry_dt, entry_px = None, None
entry_raw_open = None
entry_bar = 0

cb_triggers = []  # (data, loss1_pnl, loss2_pnl, trade_skip_list)
consec_losses = 0
cooldown_rem = 0
trade_num = 0
all_pnls = []
skipped_trades = []

for i in range(20, n_bars):
    if i+1 >= n_bars: continue
    dt_next = df.index[i+1]
    hr_n, mn_n = dt_next.hour, dt_next.minute
    dt_curr = df.index[i]
    overnight_gap = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

    # Forced close
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
        
        # Applica CB
        if cooldown_rem > 0:
            cooldown_rem -= 1
            skipped_trades.append({"entry": entry_dt, "exit": exit_dt_actual,
                                   "dir": "LONG" if pos==1 else "SHORT", "pnl": pnl,
                                   "reason": "CB cooldown"})
        else:
            all_pnls.append(pnl)
            if pnl < 0:
                consec_losses += 1
            else:
                consec_losses = 0
            if consec_losses >= 2:
                cooldown_rem = 3
                consec_losses = 0
                loss1 = all_pnls[-2] if len(all_pnls) >= 2 else None
                loss2 = all_pnls[-1]
                cb_triggers.append((exit_dt_actual, loss1, loss2))
        pos = 0

    # Reversal exit
    if pos != 0:
        if pos == 1 and d[i-1]==1 and d[i]==-1:
            ex = o_arr[i+1] - slip
            pnl = ex - ep - comm_pt
            exit_dt_actual = dt_next
            if cooldown_rem > 0:
                cooldown_rem -= 1
                skipped_trades.append({"entry": entry_dt, "exit": exit_dt_actual,
                                       "dir": "LONG" if pos==1 else "SHORT", "pnl": pnl,
                                       "reason": "CB cooldown"})
            else:
                all_pnls.append(pnl)
                if pnl < 0:
                    consec_losses += 1
                else:
                    consec_losses = 0
                if consec_losses >= 2:
                    cooldown_rem = 3
                    consec_losses = 0
                    loss1 = all_pnls[-2] if len(all_pnls) >= 2 else None
                    loss2 = all_pnls[-1]
                    cb_triggers.append((exit_dt_actual, loss1, loss2))
            pos = 0
        elif pos == -1 and d[i-1]==-1 and d[i]==1:
            ex = o_arr[i+1] + slip
            pnl = ep - ex - comm_pt
            exit_dt_actual = dt_next
            if cooldown_rem > 0:
                cooldown_rem -= 1
                skipped_trades.append({"entry": entry_dt, "exit": exit_dt_actual,
                                       "dir": "LONG" if pos==1 else "SHORT", "pnl": pnl,
                                       "reason": "CB cooldown"})
            else:
                all_pnls.append(pnl)
                if pnl < 0:
                    consec_losses += 1
                else:
                    consec_losses = 0
                if consec_losses >= 2:
                    cooldown_rem = 3
                    consec_losses = 0
                    loss1 = all_pnls[-2] if len(all_pnls) >= 2 else None
                    loss2 = all_pnls[-1]
                    cb_triggers.append((exit_dt_actual, loss1, loss2))
            pos = 0

    # Entry
    if pos == 0 and in_fascia(hr_n, mn_n):
        if d[i]==1 and d[i-1]==-1:
            pos = 1; ep = o_arr[i+1] + slip
            entry_dt = dt_next; entry_px = o_arr[i+1] + slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1
        elif d[i]==-1 and d[i-1]==1:
            pos = -1; ep = o_arr[i+1] - slip
            entry_dt = dt_next; entry_px = o_arr[i+1] - slip
            entry_raw_open = o_arr[i+1]; entry_bar = i+1

print("=" * 80)
print("EVENTI CB (2 loss consecutivi -> skip 3 trade)")
print("File: {} barre, {} -> {}".format(n_bars, df.index[0].date(), df.index[-1].date()))
print("=" * 80)

if not cb_triggers:
    print("Nessun evento CB nel periodo.")
else:
    for idx, (dt_trigger, loss1, loss2) in enumerate(cb_triggers):
        loss2_str = "{:+.2f}".format(loss2) if loss2 is not None else "N/A"
        loss1_str = "{:+.2f}".format(loss1) if loss1 is not None else "N/A"
        print()
        print("CB #{} — {} ({}a perdita consecutiva)".format(
            idx + 1, dt_trigger.strftime('%d/%m/%Y %H:%M'), idx + 2))
        print("  1a loss: {} pt".format(loss1_str))
        print("  2a loss: {} pt".format(loss2_str))
        print("  Cooldown: 3 trade saltati")

# Trova trade saltati intorno a ogni CB
print()
print("=" * 80)
print("TRADE SALTATI DAL CB")
print("=" * 80)
if skipped_trades:
    for st in skipped_trades:
        d = st["dir"]
        c = "+" if st["pnl"] >= 0 else ""
        print("  {} -> {} {} pnl={}{:+.2f}".format(
            st["entry"].strftime('%d/%m %H:%M') if st["entry"] is not None else "???",
            st["exit"].strftime('%d/%m %H:%M'),
            d, c, st["pnl"]))
else:
    print("Nessun trade saltato nel periodo.")

# Riepilogo
tot_skipped = len(skipped_trades)
if tot_skipped > 0:
    skipped_pnl = sum(t["pnl"] for t in skipped_trades)
    print()
    print("RIEPILOGO:")
    print("  Eventi CB: {}".format(len(cb_triggers)))
    print("  Trade saltati: {} (PnL evitato: {:+.2f} pt = {:+,.0f} EUR)".format(
        tot_skipped, skipped_pnl, skipped_pnl * 25))
