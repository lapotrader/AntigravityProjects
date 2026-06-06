import pandas as pd
import numpy as np
from numba import jit
import sys
import os
import time
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"
FILE = BASE + r"\dati\ultimissimi5giugno.txt"
COMM_PT = 3 / 5
SLIP = 1.0

def in_fascia(hr, mn):
    return (hr >= 9 and hr < 11) or (hr == 15 and mn >= 30) or (hr >= 16 and hr < 17) or (hr == 17 and mn <= 30)

def fascia_next(hr, mn):
    finestre = [(9, 0, 11, 0), (15, 30, 17, 30)]
    now_min = hr * 60 + mn
    for h1, m1, h2, m2 in finestre:
        start = h1 * 60 + m1
        end = h2 * 60 + m2
        if now_min < start:
            return start - now_min, f"{h1:02d}:{m1:02d}"
        elif now_min < end:
            return 0, "ORA"
    return (24 * 60 - now_min + finestre[0][0] * 60 + finestre[0][1]), f"domani {finestre[0][0]:02d}:{finestre[0][1]:02d}"

def is_after_22(hr):
    return hr >= 22

@jit(nopython=True)
def st(h, l, c, p, m):
    n = len(h); d = np.ones(n); tr = np.zeros(n); a = np.zeros(n); s2 = np.zeros(n)
    fu = np.zeros(n); fl = np.zeros(n)
    for i in range(1, n): tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    s = 0.0
    for i in range(1, p): s += tr[i]
    a[p] = s / p
    for i in range(p + 1, n): a[i] = (a[i - 1] * (p - 1) + tr[i]) / p
    for i in range(p, n):
        hl = (h[i] + l[i]) / 2; ub = hl + m * a[i]; lb = hl - m * a[i]
        if i == p:
            fu[i] = ub; fl[i] = lb; s2[i] = ub; d[i] = -1
        else:
            fu[i] = ub if (ub < fu[i - 1]) or (c[i - 1] > fu[i - 1]) else fu[i - 1]
            fl[i] = lb if (lb > fl[i - 1]) or (c[i - 1] < fl[i - 1]) else fl[i - 1]
            if d[i - 1] == 1:
                s2[i] = fl[i]
                if c[i] <= fl[i]: d[i] = -1; s2[i] = fu[i]
                else: d[i] = 1
            else:
                s2[i] = fu[i]
                if c[i] >= fu[i]: d[i] = 1; s2[i] = fl[i]
                else: d[i] = -1
    return d, s2, fu, fl

def run():
    while True:
        try:
            df = pd.read_csv(FILE, sep="\t", header=None, names=["datetime", "h", "l", "o", "c", "v"])
            df["dt"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M:%S")
            df = df.set_index("dt").drop(columns=["datetime"])
        except:
            os.system("cls")
            print(f"\n  ATTESA: file non trovato o in lettura...")
            time.sleep(5)
            continue

        h_arr = df["h"].values.astype(np.float64)
        l_arr = df["l"].values.astype(np.float64)
        c_arr = df["c"].values.astype(np.float64)
        o_arr = df["o"].values.astype(np.float64)
        n_bars = len(df)

        d, s2, fu, fl = st(h_arr, l_arr, c_arr, 10, 3.0)

        # ricostruisci trade + CB da capo
        pos, ep = 0, 0.0
        entry_dt, entry_bar = None, 0
        consec_losses = 0
        cooldown_rem = 0

        for i in range(20, n_bars):
            if i + 1 >= n_bars:
                continue
            dt_next = df.index[i + 1]
            hr_n, mn_n = dt_next.hour, dt_next.minute
            dt_curr = df.index[i]
            overnight_gap = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

            if pos != 0 and (is_after_22(hr_n) or overnight_gap):
                if overnight_gap and not is_after_22(hr_n):
                    ex = c_arr[i]
                else:
                    ex = o_arr[i + 1]
                if pos == 1:
                    pnl = ex - ep - COMM_PT
                else:
                    pnl = ep - ex - COMM_PT
                if cooldown_rem > 0:
                    cooldown_rem -= 1
                else:
                    if pnl < 0:
                        consec_losses += 1
                    else:
                        consec_losses = 0
                    if consec_losses >= 2:
                        cooldown_rem = 3
                        consec_losses = 0
                pos = 0

            if pos != 0:
                rev_long = (pos == 1 and d[i - 1] == 1 and d[i] == -1)
                rev_short = (pos == -1 and d[i - 1] == -1 and d[i] == 1)
                if rev_long or rev_short:
                    ex = o_arr[i + 1]
                    if pos == 1:
                        pnl = ex - ep - COMM_PT
                    else:
                        pnl = ep - ex - COMM_PT
                    if cooldown_rem > 0:
                        cooldown_rem -= 1
                    else:
                        if pnl < 0:
                            consec_losses += 1
                        else:
                            consec_losses = 0
                        if consec_losses >= 2:
                            cooldown_rem = 3
                            consec_losses = 0
                    pos = 0

            if pos == 0 and in_fascia(hr_n, mn_n):
                if d[i] == 1 and d[i - 1] == -1:
                    pos = 1
                    ep = o_arr[i + 1] + SLIP
                    entry_dt = dt_next
                    entry_bar = i + 1
                elif d[i] == -1 and d[i - 1] == 1:
                    pos = -1
                    ep = o_arr[i + 1] - SLIP
                    entry_dt = dt_next
                    entry_bar = i + 1

        last = df.index[-1]
        hr_now, mn_now = last.hour, last.minute

        st_dir = "LONG" if d[-1] == 1 else "SHORT"
        st_prev = "LONG" if d[-2] == 1 else "SHORT"
        reversal = d[-1] != d[-2]
        pos_aperta = pos != 0
        banda_su, banda_giu = fu[-1], fl[-1]
        close_now = c_arr[-1]

        dist_su = banda_su - close_now
        dist_giu = close_now - banda_giu
        dist_banda = dist_su if st_dir == "LONG" else dist_giu

        f_min, f_label = fascia_next(hr_now, mn_now)
        ok_fascia = in_fascia(hr_now, mn_now)

        fa_semaforo = (not pos_aperta and cooldown_rem == 0 and ok_fascia and reversal)

        # preparazione: close vicino banda (< 15pt) e in fascia
        allerta_reversal = False
        if not pos_aperta and not reversal and ok_fascia and cooldown_rem == 0:
            if st_dir == "LONG" and dist_giu <= 15:
                allerta_reversal = True
                allerta_verso = "SHORT"
            elif st_dir == "SHORT" and dist_su <= 15:
                allerta_reversal = True
                allerta_verso = "LONG"

        os.system("cls")
        print()
        print("  ╔══════════════════════════════════════════════════════╗")
        print("  ║  SEMAFORO MASSIMO VITA  —  SuperTrend(10,3.0) DAX 3m  ║")
        print("  ╠══════════════════════════════════════════════════════╣")
        print(f"  ║  {last.strftime('%d/%m/%Y %H:%M:%S')}  │  barre: {n_bars}")
        print(f"  ║  Item: FR.EUREX.2409430  │  Aggiornamento: ogni 10s")
        print("  ╚══════════════════════════════════════════════════════╝")
        print()

        # ST
        st_ico = "\033[92m▲\033[0m" if st_dir == "LONG" else "\033[91m▼\033[0m"
        print(f"  {st_ico}  ST: {st_dir}  ", end="")
        if reversal:
            print(f"← REVERSAL da {st_prev}")
        else:
            print(f"(stabile da {st_prev})")
        print(f"     Banda SUP: {banda_su:.1f}  Banda INF: {banda_giu:.1f}  Close: {close_now:.1f}")

        # distanza dalla banda
        if st_dir == "LONG":
            print(f"     ⬆ Distanza da inversione (banda inf): {dist_giu:.1f} pt")
        else:
            print(f"     ⬇ Distanza da inversione (banda sup): {dist_su:.1f} pt")
        print()

        # posizione
        if pos_aperta:
            durata = last - entry_dt
            print(f"  \033[93m▶ POSIZIONE APERTA: {'LONG' if pos == 1 else 'SHORT'}\033[0m")
            print(f"     Entry: {ep:.1f}  |  Aperta da: {str(durata).split('.')[0]}")
            print(f"     P&L flottante: {(close_now - ep) if pos == 1 else (ep - close_now):.1f} pt")
        else:
            print(f"  □ Posizione: CHIUSA")
        print()

        # CB
        if cooldown_rem > 0:
            print(f"  \033[91m⚠ CB ATTIVO: ancora {cooldown_rem} trade da saltare\033[0m")
        elif consec_losses == 1:
            print(f"  \033[93m⚠ CB: 1 loss consecutivo — attenzione\033[0m")
        else:
            print(f"  ✅ CB: OK (nessuna perdita)")
        print()

        # fascia
        if ok_fascia:
            print(f"  ✅ Fascia: APERTA ({hr_now:02d}:{mn_now:02d})")
        else:
            print(f"  ⏳ Fascia: CHIUSA — prossima tra {f_min} min ({f_label})")
        print()

        # === SEMAFORO + AZIONE ===
        print("  " + "─" * 52)
        if fa_semaforo:
            direz = st_dir
            print(f"  \033[92m{'🟢' * 5}  SEMAFORO VERDE  {'🟢' * 5}\033[0m")
            print(f"  \033[92m┌────────────────────────────────────────────────────┐\033[0m")
            print(f"  \033[92m│  ▶▶▶  ENTRA {direz}  ◄◄◄                               │\033[0m")
            print(f"  \033[92m└────────────────────────────────────────────────────┘\033[0m")
        elif allerta_reversal:
            print(f"  \033[93m{'🟡' * 5}  ATTENZIONE  {'🟡' * 5}\033[0m")
            print(f"  \033[93m┌────────────────────────────────────────────────────┐\033[0m")
            print(f"  \033[93m│  Close a {dist_banda:.1f} pt dalla banda — possibile reversal  │\033[0m")
            print(f"  \033[93m│  ▶  PREPARATI: prossima barra potrebbe invertire in │\033[0m")
            print(f"  \033[93m│     {allerta_verso}                               │\033[0m")
            print(f"  \033[93m└────────────────────────────────────────────────────┘\033[0m")
        else:
            print(f"  \033[91m{'🔴' * 5}  SEMAFORO ROSSO  {'🔴' * 5}\033[0m")
            motivi = []
            if reversal:
                motivi.append("reversal OK")
            else:
                motivi.append("attendi reversal")
            if ok_fascia:
                motivi.append("fascia OK")
            else:
                motivi.append(f"fuori fascia (tra {f_min}m)")
            if not pos_aperta:
                motivi.append("posizione chiusa OK")
            else:
                motivi.append(f"posizione aperta")
            if cooldown_rem == 0:
                motivi.append("CB scarico")
            else:
                skip_rimasti = cooldown_rem + (0 if not pos_aperta and not reversal else 0)
                motivi.append(f"CB attivo ({cooldown_rem} skip)")
            print(f"     Motivo: {', '.join(motivi)}")
        print("  " + "─" * 52)
        print()
        print(f"  Prossimo aggiornamento tra 10s...  (Ctrl+C per uscire)")

        time.sleep(10)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n  Semaforo fermo.")
        sys.exit(0)
