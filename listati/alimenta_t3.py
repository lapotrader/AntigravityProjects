import urllib.request
import time
import os
import sys
from datetime import datetime, timedelta

BASE = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"
FILE = BASE + r"\dati\ultimissimi5giugno.txt"
ITEM = "FR.EUREX.2409430"
PORT = 8333
URL = f"http://localhost:{PORT}/T3OPEN/get_history"

def get_latest_dt():
    try:
        with open(FILE, "r") as f:
            last_line = f.readlines()[-1].strip()
        dt_str = last_line.split("\t")[0]
        return datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
    except:
        return None

def fetch_bars(data_da):
    params = f"?item={ITEM}&frequency=3M&dataDa={data_da}"
    req = urllib.request.Request(URL + params)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"[{now_str}] ERRORE T3: {e}")
        return None
    lines = raw.strip().split("\n")
    if not lines:
        return None
    first = lines[0]
    if not first.startswith("outcome=OK"):
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"[{now_str}] T3 errore: {first}")
        return None
    bars = []
    for line in lines[1:]:
        line = line.strip()
        if not line.startswith("element="):
            continue
        parts = line[8:].split("|")
        if len(parts) < 6:
            continue
        ts = datetime.strptime(parts[0], "%Y%m%d%H%M%S")
        dt_out = ts.strftime("%d/%m/%Y %H:%M:%S")
        bars.append(f"{dt_out}\t{parts[1]}\t{parts[2]}\t{parts[3]}\t{parts[4]}\t{parts[5]}")
    return bars

def get_bar_rhythm():
    try:
        with open(FILE, "r") as f:
            lines = f.readlines()
        if len(lines) < 20:
            return 180
        ts = []
        for line in lines:
            dt_str = line.strip().split("\t")[0]
            ts.append(datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S"))

        # raggruppa per giorno e trova il giorno più recente con almeno 50 barre
        by_date = {}
        for t in ts:
            d = t.date()
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(t)

        best_day = None
        best_count = 0
        for d, times in sorted(by_date.items(), reverse=True):
            if len(times) >= 20:
                best_day = times
                best_count = len(times)
                break

        if best_day is None:
            return 180

        gaps = [(best_day[i+1] - best_day[i]).total_seconds() for i in range(len(best_day)-1)]
        gaps = [g for g in gaps if g < 600]
        if not gaps:
            return 180
        med = sorted(gaps)[len(gaps)//2]
        return int(med)
    except:
        return 180

def next_bar_time(last_dt, interval=180):
    return last_dt + timedelta(seconds=interval) + timedelta(seconds=3)

def run():
    print("=" * 55)
    print(f"  ALIMENTATORE T3  |  {ITEM}  |  barre 3min")
    print(f"  File: {FILE}")
    print("=" * 55)

    # === FASE 1: CATCH-UP ===
    last_dt = get_latest_dt()
    if last_dt is None:
        print("\n  File vuoto o assente. Impossibile agganciarsi.")
        return

    lag = (datetime.now() - last_dt).total_seconds()
    if lag > 200:
        print(f"\n  --- CATCH-UP: ultima barra {last_dt.strftime('%d/%m/%Y %H:%M')} ({int(lag/60)} min fa) ---")
        while True:
            data_da = (last_dt - timedelta(days=1)).strftime("%Y%m%d")
            bars = fetch_bars(data_da)
            if bars is None:
                print("  T3 non risponde, riprovo tra 10s...")
                time.sleep(10)
                continue
            new_bars = []
            last_dt_str = last_dt.strftime("%d/%m/%Y %H:%M:%S")
            for bar in bars:
                if bar.split("\t")[0] > last_dt_str:
                    new_bars.append(bar)
            if len(new_bars) > 0:
                new_bars = new_bars[:-1]
            if new_bars:
                with open(FILE, "a") as f:
                    for bar in new_bars:
                        f.write(bar + "\n")
                last_dt_str = new_bars[-1].split("\t")[0]
                last_dt = datetime.strptime(last_dt_str, "%d/%m/%Y %H:%M:%S")
                print(f"  +{len(new_bars)} barre  (-> {last_dt_str})")
                lag = (datetime.now() - last_dt).total_seconds()
                if lag < 200:
                    print(f"  --- CATCH-UP COMPLETATO ---\n")
                    break
            else:
                print("  Nessuna nuova barra da T3, aspetto...")
                time.sleep(10)

    # === FASE 2: SYNC ===
    last_dt = get_latest_dt()
    interval = get_bar_rhythm()
    print(f"  Ultima barra: {last_dt.strftime('%d/%m/%Y %H:%M')}")
    print(f"  Ritmo rilevato: {interval}s  |  Prossima sveglia: {(last_dt+timedelta(seconds=interval+3)).strftime('%H:%M:%S')}")
    print()

    while True:
        target = next_bar_time(last_dt, interval)
        now = datetime.now()
        sleep_s = (target - now).total_seconds()
        if sleep_s > 0:
            time.sleep(sleep_s)
        elif sleep_s < -10:
            last_dt = get_latest_dt()
            continue

        now_t = datetime.now()
        now_str = now_t.strftime('%H:%M:%S')
        last_dt = get_latest_dt()
        data_da = (last_dt - timedelta(days=1)).strftime("%Y%m%d")

        bars = fetch_bars(data_da)
        if bars is None:
            continue

        new_bars = []
        last_dt_str = last_dt.strftime("%d/%m/%Y %H:%M:%S")
        for bar in bars:
            if bar.split("\t")[0] > last_dt_str:
                new_bars.append(bar)

        if len(new_bars) > 0:
            new_bars = new_bars[:-1]

        if new_bars:
            with open(FILE, "a") as f:
                for bar in new_bars:
                    f.write(bar + "\n")
            last_dt = get_latest_dt()
            print(f"[{now_str}] +{len(new_bars)} barre  (-> {last_dt.strftime('%H:%M:%S')})")
        else:
            print(f"[{now_str}] check  |  nessuna nuova  (prossima tra {interval}s)")

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nFermo.")
        sys.exit(0)
