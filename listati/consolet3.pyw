import urllib.request
import time
import os
import sys
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from numba import jit

BASE = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"
FILE = BASE + r"\dati\ultimissimi5giugno.txt"
ITEM = "FR.EUREX.2409430"
PORT = 8333
URL = f"http://localhost:{PORT}/T3OPEN/get_history"
COMM_PT = 3 / 5
SLIP = 1.0

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

# pre-compila numba subito (first launch: ~5-10s, poi in cache)
st(np.array([1.0, 2.0, 3.0], dtype=np.float64), np.array([1.0, 2.0, 3.0], dtype=np.float64),
   np.array([1.0, 2.0, 3.0], dtype=np.float64), 2, 3.0)

def in_fascia(hr, mn):
    return (hr >= 9 and hr < 11) or (hr == 15 and mn >= 30) or (hr >= 16 and hr < 17) or (hr == 17 and mn <= 30)

def fascia_info(hr, mn):
    finestre = [(9, 0, 11, 0), (15, 30, 17, 30)]
    now_min = hr * 60 + mn
    for h1, m1, h2, m2 in finestre:
        start = h1 * 60 + m1
        end = h2 * 60 + m2
        if now_min < start:
            return "CHIUSA", start - now_min, f"{h1:02d}:{m1:02d}"
        elif now_min < end:
            return "APERTA", 0, ""
    return "CHIUSA", 24 * 60 - now_min + finestre[0][0] * 60, f"domani {finestre[0][0]:02d}:{finestre[0][1]:02d}"

def is_after_22(hr):
    return hr >= 22

def bar_interval():
    try:
        with open(FILE, "r") as f:
            lines = f.readlines()
        if len(lines) < 20:
            return 180
        ts = []
        for line in lines:
            ts.append(datetime.strptime(line.strip().split("\t")[0], "%d/%m/%Y %H:%M:%S"))
        by_date = {}
        for t in ts:
            by_date.setdefault(t.date(), []).append(t)
        best = None
        for d in sorted(by_date, reverse=True):
            if len(by_date[d]) >= 20:
                best = by_date[d]; break
        if not best:
            return 180
        gaps = [(best[i+1] - best[i]).total_seconds() for i in range(len(best)-1) if (best[i+1] - best[i]).total_seconds() < 600]
        if not gaps:
            return 180
        med = sorted(gaps)[len(gaps)//2]
        return int(med)
    except:
        return 180

QUOTES_URL = f"http://localhost:{PORT}/T3OPEN/get_quotes"

def fetch_quote():
    params = f"?item={ITEM}&schema=last_price;best_bid1;best_ask1;percentage_change;trade_volume_bi;trade_time"
    req = urllib.request.Request(QUOTES_URL + params)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        return None, str(e)
    lines = raw.strip().split("\n")
    if not lines or not lines[0].startswith("outcome=OK"):
        return None, "no data"
    for line in lines[1:]:
        line = line.strip()
        if line.startswith("element="):
            parts = line[8:].split("|")
            if len(parts) >= 6:
                return {
                    "last": parts[0],
                    "bid": parts[1],
                    "ask": parts[2],
                    "chg": parts[3],
                    "vol": parts[4],
                    "time": parts[5],
                }, None
    return None, "no element"

def fetch_bars(data_da):
    params = f"?item={ITEM}&frequency=3M&dataDa={data_da}"
    req = urllib.request.Request(URL + params)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        return None, str(e)
    lines = raw.strip().split("\n")
    if not lines:
        return None, "risposta vuota"
    if not lines[0].startswith("outcome=OK"):
        return None, lines[0]
    bars = []
    for line in lines[1:]:
        line = line.strip()
        if not line.startswith("element="):
            continue
        parts = line[8:].split("|")
        if len(parts) < 6:
            continue
        ts = datetime.strptime(parts[0], "%Y%m%d%H%M%S")
        bars.append(f"{ts.strftime('%d/%m/%Y %H:%M:%S')}\t{parts[1]}\t{parts[2]}\t{parts[3]}\t{parts[4]}\t{parts[5]}")
    return bars, None

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("console t3")
        self.geometry("800x600")
        self.configure(bg="#1a1a2e")
        self.resizable(False, False)

        self.bar_int = bar_interval()
        self.lock = threading.Lock()
        self.running = True

        self._build_ui()
        self.log("Avviato — ritmo barre: {}s".format(self.bar_int))
        self._ready = False
        self._last_fetch = datetime.now()
        self.after(100, self._init)
        self.after(1000, self._quote_poll)

    def _build_ui(self):
        # === SEMAFORO ===
        self.sema_frame = tk.Frame(self, bg="#1a1a2e")
        self.sema_frame.pack(fill="x", padx=15, pady=(15, 5))

        self.sema_canvas = tk.Canvas(self.sema_frame, width=100, height=100, bg="#1a1a2e", highlightthickness=0)
        self.sema_canvas.pack(side="left", padx=(0, 15))
        self._draw_tl("red")

        self.info_frame = tk.Frame(self.sema_frame, bg="#1a1a2e")
        self.info_frame.pack(side="left", fill="x", expand=True)

        self.lbl_action = tk.Label(self.info_frame, text="INIZIALIZZAZIONE...", font=("Segoe UI", 20, "bold"),
                                   fg="#888888", bg="#1a1a2e", anchor="w")
        self.lbl_action.pack(fill="x")

        self.lbl_st = tk.Label(self.info_frame, text="ST: --", font=("Segoe UI", 12), fg="#cccccc", bg="#1a1a2e", anchor="w")
        self.lbl_st.pack(fill="x")

        self.lbl_bands = tk.Label(self.info_frame, text="Bande: --  Close: --", font=("Segoe UI", 11),
                                  fg="#aaaaaa", bg="#1a1a2e", anchor="w")
        self.lbl_bands.pack(fill="x")

        self.lbl_dist = tk.Label(self.info_frame, text="", font=("Segoe UI", 11), fg="#aaaaaa", bg="#1a1a2e", anchor="w")
        self.lbl_dist.pack(fill="x")

        # === LIVE DAX ===
        self.live_frame = tk.Frame(self, bg="#1a1a2e", bd=1, relief="solid", highlightbackground="#333355", highlightthickness=1)
        self.live_frame.pack(fill="x", padx=15, pady=(5, 0))

        tk.Label(self.live_frame, text="DAX FUTURE", font=("Segoe UI", 9, "bold"),
                 fg="#888888", bg="#1a1a2e").pack(anchor="w", padx=8, pady=(4, 0))

        live_row = tk.Frame(self.live_frame, bg="#1a1a2e")
        live_row.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_last = tk.Label(live_row, text="---", font=("Segoe UI", 22, "bold"), fg="#ffffff", bg="#1a1a2e")
        self.lbl_last.pack(side="left", padx=(0, 15))

        self.lbl_bidask = tk.Label(live_row, text="Bid: ---  Ask: ---", font=("Segoe UI", 11), fg="#aaaaaa", bg="#1a1a2e")
        self.lbl_bidask.pack(side="left", padx=(0, 15))

        self.lbl_chg = tk.Label(live_row, text="", font=("Segoe UI", 11), fg="#aaaaaa", bg="#1a1a2e")
        self.lbl_chg.pack(side="left", padx=(0, 15))

        self.lbl_vol = tk.Label(live_row, text="Vol: ---", font=("Segoe UI", 10), fg="#888888", bg="#1a1a2e")
        self.lbl_vol.pack(side="left", padx=(0, 15))

        self.lbl_livetime = tk.Label(live_row, text="", font=("Segoe UI", 10), fg="#555555", bg="#1a1a2e")
        self.lbl_livetime.pack(side="right")

        # === STATI ===
        self.stati_frame = tk.Frame(self, bg="#1a1a2e")
        self.stati_frame.pack(fill="x", padx=15, pady=(5, 5))

        self.lbl_pos = tk.Label(self.stati_frame, text="Posizione: --", font=("Segoe UI", 11), fg="#cccccc", bg="#1a1a2e")
        self.lbl_pos.pack(side="left", padx=(0, 30))

        self.lbl_cb = tk.Label(self.stati_frame, text="CB: --", font=("Segoe UI", 11), fg="#cccccc", bg="#1a1a2e")
        self.lbl_cb.pack(side="left", padx=(0, 30))

        self.lbl_fascia = tk.Label(self.stati_frame, text="Fascia: --", font=("Segoe UI", 11), fg="#cccccc", bg="#1a1a2e")
        self.lbl_fascia.pack(side="left")

        # === ORA / FILE ===
        self.lbl_info = tk.Label(self, text="Ultima barra: --  |  File: -- barre", font=("Segoe UI", 10),
                                 fg="#888888", bg="#1a1a2e")
        self.lbl_info.pack(padx=15, pady=(2, 5), anchor="w")

        # === LOG ===
        log_frame = tk.Frame(self, bg="#0d0d1a")
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        tk.Label(log_frame, text="RILEVAZIONI", font=("Segoe UI", 10, "bold"), fg="#666666", bg="#0d0d1a").pack(anchor="w")
        self.log_text = tk.Text(log_frame, font=("Consolas", 9), bg="#0d0d1a", fg="#00cc66", bd=0,
                                wrap="word", height=12)
        self.log_text.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _draw_tl(self, color):
        self.sema_canvas.delete("all")
        c = self.sema_canvas
        cx, cy, r = 50, 50, 40
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="#555555", width=2)
        if color == "green":
            c.create_text(cx, cy, text="V", font=("Segoe UI", 36, "bold"), fill="white")
        elif color == "red":
            c.create_text(cx, cy, text="X", font=("Segoe UI", 36, "bold"), fill="white")
        elif color == "yellow":
            c.create_text(cx, cy, text="!", font=("Segoe UI", 36, "bold"), fill="black")

    def log(self, msg):
        self.after(0, self._log, msg)

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("1.0", f"[{ts}] {msg}\n")
        if int(self.log_text.index("end-1c").split(".")[0]) > 500:
            self.log_text.delete("end-1l linestart", "end-1l")

    def _init(self):
        need_catchup = False
        try:
            with open(FILE, "r") as f:
                lines = f.readlines()
            last_line = lines[-1].strip()
            last_dt = datetime.strptime(last_line.split("\t")[0], "%d/%m/%Y %H:%M:%S")
            last_day = last_dt.date()

            # pulisci ultimo giorno: cancella tutte le barre del giorno dell'ultima barra
            kept = []
            removed = 0
            for line in lines:
                dt_bar = datetime.strptime(line.strip().split("\t")[0], "%d/%m/%Y %H:%M:%S")
                if dt_bar.date() == last_day:
                    removed += 1
                else:
                    kept.append(line)
            if removed > 0:
                with open(FILE, "w") as f:
                    f.writelines(kept)
                self.log(f"Pulito ultimo giorno ({last_day}): rimosse {removed} barre, riscarico da T3")

            # rileggi ultima data dopo pulizia
            if kept:
                last_bar = kept[-1].strip().split("\t")[0]
                last_dt = datetime.strptime(last_bar, "%d/%m/%Y %H:%M:%S")
                self.log(f"Ultima barra preservata: {last_dt.strftime('%d/%m/%Y %H:%M')}")
                need_catchup = True
            else:
                self.log("File svuotato — parto da zero")
                need_catchup = True
                last_dt = datetime.now() - timedelta(days=28)

        except Exception as e:
            self.log(f"ERRORE init: {e}")
            self._ready = True
            self._tick()
            return

        threading.Thread(target=self._do_catch_up, args=(last_dt,), daemon=True).start()

    def _do_catch_up(self, start_dt):
        last_dt = start_dt
        while self.running:
            min_da = datetime.now() - timedelta(days=28)
            fetch_da = max(last_dt - timedelta(days=1), min_da)
            data_da = fetch_da.strftime("%Y%m%d")
            bars, err = fetch_bars(data_da)
            if err:
                self.log(f"T3 errore: {err}")
                time.sleep(10)
                continue
            new_bars = []
            for b in bars:
                bt = datetime.strptime(b.split("\t")[0], "%d/%m/%Y %H:%M:%S")
                if bt > last_dt:
                    new_bars.append(b)
            if len(new_bars) > 0:
                new_bars = new_bars[:-1]
            if new_bars:
                with self.lock:
                    with open(FILE, "a") as f:
                        for b in new_bars:
                            f.write(b + "\n")
                last_dt = datetime.strptime(new_bars[-1].split("\t")[0], "%d/%m/%Y %H:%M:%S")
                self.log(f"+{len(new_bars)} barre (-> {last_dt.strftime('%H:%M')})")
                if (datetime.now() - last_dt).total_seconds() < 200:
                    self.log("CATCH-UP completato")
                    self._ready = True
                    self.after(0, self._tick)
                    return
            else:
                time.sleep(10)

    def _tick(self):
        if not self.running:
            return

        self._update_semaforo()

        if self._ready:
            now = datetime.now()
            sec = now.minute * 60 + now.second
            if sec % self.bar_int < 8:
                if (now - self._last_fetch).total_seconds() > self.bar_int - 10:
                    self._last_fetch = now
                    threading.Thread(target=self._fetch_and_update, daemon=True).start()

        self.after(4000, self._tick)

    def _fetch_and_update(self):
        if not self.running:
            return
        try:
            with open(FILE, "r") as f:
                last_line = f.readlines()[-1].strip()
            last_dt = datetime.strptime(last_line.split("\t")[0], "%d/%m/%Y %H:%M:%S")
        except:
            return
        min_da = datetime.now() - timedelta(days=28)
        fetch_da = max(last_dt - timedelta(days=1), min_da)
        data_da = fetch_da.strftime("%Y%m%d")
        bars, err = fetch_bars(data_da)
        if err:
            self.log(f"T3: {err}")
            return
        new_bars = []
        for b in bars:
            bt = datetime.strptime(b.split("\t")[0], "%d/%m/%Y %H:%M:%S")
            if bt > last_dt:
                new_bars.append(b)
        if len(new_bars) > 0:
            new_bars = new_bars[:-1]
        if new_bars:
            with self.lock:
                with open(FILE, "a") as f:
                    for b in new_bars:
                        f.write(b + "\n")
            last_bar = new_bars[-1].split("\t")[0]
            self.log(f"+{len(new_bars)} barre (-> {last_bar})")

    def _quote_poll(self):
        if not self.running:
            return
        threading.Thread(target=self._update_quote, daemon=True).start()
        self.after(5000, self._quote_poll)

    def _update_quote(self):
        q, err = fetch_quote()
        if err or q is None:
            return
        try:
            last = float(q["last"])
            bid = float(q["bid"])
            ask = float(q["ask"])
            chg = float(q["chg"])
            vol = int(float(q["vol"]))
            spread = ask - bid
            chg_str = f"{chg:+.2f}%"
            chg_color = "#00ff88" if chg >= 0 else "#ff4444"
        except:
            return
        self.after(0, lambda: self._apply_quote(last, bid, ask, chg_str, chg_color, vol, spread, q["time"]))

    def _apply_quote(self, last, bid, ask, chg_str, chg_color, vol, spread, t_time):
        self.lbl_last.config(text=f"{last:.1f}")
        self.lbl_bidask.config(text=f"Bid: {bid:.1f}  Ask: {ask:.1f}  Spr: {spread:.1f}")
        self.lbl_chg.config(text=chg_str, fg=chg_color)
        self.lbl_vol.config(text=f"Vol: {vol}")
        self.lbl_livetime.config(text=t_time if t_time else "")

    def _update_semaforo(self):
        try:
            with self.lock:
                df = pd.read_csv(FILE, sep="\t", header=None, names=["datetime", "h", "l", "o", "c", "v"])
                df["dt"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M:%S")
                df = df.set_index("dt").drop(columns=["datetime"])
        except:
            return

        n_bars = len(df)
        h_arr = df["h"].values.astype(np.float64)
        l_arr = df["l"].values.astype(np.float64)
        c_arr = df["c"].values.astype(np.float64)
        o_arr = df["o"].values.astype(np.float64)

        d, s2, fu, fl = st(h_arr, l_arr, c_arr, 10, 3.0)

        pos, ep = 0, 0.0
        entry_dt = None
        consec_losses = 0
        cooldown_rem = 0

        for i in range(20, n_bars):
            if i + 1 >= n_bars: continue
            dt_next = df.index[i + 1]
            hr_n, mn_n = dt_next.hour, dt_next.minute
            dt_curr = df.index[i]
            og = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

            if pos != 0 and (is_after_22(hr_n) or og):
                ex = c_arr[i] if (og and not is_after_22(hr_n)) else o_arr[i + 1]
                pnl = (ex - ep - COMM_PT) if pos == 1 else (ep - ex - COMM_PT)
                if cooldown_rem > 0:
                    cooldown_rem -= 1
                else:
                    if pnl < 0: consec_losses += 1
                    else: consec_losses = 0
                    if consec_losses >= 2: cooldown_rem = 3; consec_losses = 0
                pos = 0

            if pos != 0:
                rev = (pos == 1 and d[i-1] == 1 and d[i] == -1) or (pos == -1 and d[i-1] == -1 and d[i] == 1)
                if rev:
                    ex = o_arr[i + 1]
                    pnl = (ex - ep - COMM_PT) if pos == 1 else (ep - ex - COMM_PT)
                    if cooldown_rem > 0: cooldown_rem -= 1
                    else:
                        if pnl < 0: consec_losses += 1
                        else: consec_losses = 0
                        if consec_losses >= 2: cooldown_rem = 3; consec_losses = 0
                    pos = 0

            if pos == 0 and in_fascia(hr_n, mn_n):
                if d[i] == 1 and d[i-1] == -1:
                    pos = 1; ep = o_arr[i+1] + SLIP; entry_dt = dt_next
                elif d[i] == -1 and d[i-1] == 1:
                    pos = -1; ep = o_arr[i+1] - SLIP; entry_dt = dt_next

        last = df.index[-1]
        hr, mn = last.hour, last.minute
        st_dir = "LONG" if d[-1] == 1 else "SHORT"
        st_prev = "LONG" if d[-2] == 1 else "SHORT"
        reversal = d[-1] != d[-2]
        bu, bl = fu[-1], fl[-1]
        close = c_arr[-1]

        dist_su = bu - close
        dist_giu = close - bl

        fas_stato, fas_min, fas_label = fascia_info(hr, mn)
        ok_fascia = fas_stato == "APERTA"
        pos_open = pos != 0
        can_trade = not pos_open and cooldown_rem == 0 and ok_fascia and reversal

        # allerta pre-reversal
        allerta = False
        allerta_verso = ""
        if not pos_open and not reversal and ok_fascia and cooldown_rem == 0:
            if st_dir == "LONG" and dist_giu <= 15:
                allerta = True; allerta_verso = "SHORT"
            elif st_dir == "SHORT" and dist_su <= 15:
                allerta = True; allerta_verso = "LONG"

        # === AGGIORNA UI ===
        if can_trade:
            self._draw_tl("green")
            self.lbl_action.config(text=f"▶▶▶ ENTRA {st_dir} ◄◄◄", fg="#00ff88")
        elif allerta:
            self._draw_tl("yellow")
            self.lbl_action.config(text=f"PREPARATI: possibile reversal {allerta_verso}", fg="#ffcc00")
        else:
            self._draw_tl("red")
            self.lbl_action.config(text="ASpetta", fg="#ff4444")

        rev_text = f"← reversal da {st_prev}" if reversal else "(stabile)"
        st_ico = "▲" if st_dir == "LONG" else "▼"
        self.lbl_st.config(text=f"ST: {st_ico} {st_dir}  {rev_text}")

        self.lbl_bands.config(text=f"Banda SUP: {bu:.1f}  INF: {bl:.1f}  Close: {close:.1f}")

        if st_dir == "LONG":
            self.lbl_dist.config(text=f"⬆ Distanza da inversione (banda inf): {dist_giu:.1f} pt")
        else:
            self.lbl_dist.config(text=f"⬇ Distanza da inversione (banda sup): {dist_su:.1f} pt")

        if pos_open:
            dur = last - entry_dt
            pnl_f = (close - ep) if pos == 1 else (ep - close)
            self.lbl_pos.config(text=f"Posizione: ◀ {'LONG' if pos==1 else 'SHORT'}  Entry: {ep:.1f}  P&L: {pnl_f:.1f} pt",
                                fg="#ffaa00")
        else:
            self.lbl_pos.config(text="Posizione: □ CHIUSA", fg="#cccccc")

        if cooldown_rem > 0:
            self.lbl_cb.config(text=f"CB: ⚠ attivo ({cooldown_rem} skip)", fg="#ff4444")
        elif consec_losses == 1:
            self.lbl_cb.config(text="CB: ⚠ 1 loss consecutivo", fg="#ffaa00")
        else:
            self.lbl_cb.config(text="CB: ✅ OK", fg="#00ff88")

        if ok_fascia:
            self.lbl_fascia.config(text=f"Fascia: ✅ APERTA ({hr:02d}:{mn:02d})", fg="#00ff88")
        else:
            self.lbl_fascia.config(text=f"Fascia: ⏳ CHIUSA (tra {fas_min} min alle {fas_label})", fg="#ffaa00")

        self.lbl_info.config(text=f"Ultima barra: {last.strftime('%d/%m/%Y %H:%M')}  |  File: {n_bars} barre  |  Item: {ITEM}")

    def destroy(self):
        self.running = False
        super().destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
