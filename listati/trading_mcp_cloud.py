import subprocess
import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import numpy as np
import pandas as pd
from mcp.server.fastmcp import FastMCP

BASE = Path(__file__).resolve().parent.parent
DATI = BASE / "dati"
LISTATI = BASE / "listati"
REPORTS = BASE / "reports"
DATA_FILE = DATI / "ultimissimi5giugno.txt"
COMM_PT = 3 / 5
SLIP = 1.0

mcp = FastMCP("Trading Console Cloud")


def _in_fascia(hr, mn):
    return (hr >= 9 and hr < 11) or (hr == 15 and mn >= 30) or (hr >= 16 and hr < 17) or (hr == 17 and mn <= 30)


def _is_after_22(hr):
    return hr >= 22


@mcp.tool()
def supertrend_status() -> str:
    """Calcola il SuperTrend(10, 3.0) sulle ultime barre e restituisce direzione, bande, close, alert reversal"""
    try:
        df = pd.read_csv(DATA_FILE, sep="\t", header=None,
                         names=["datetime", "h", "l", "o", "c", "v"])
        df["dt"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M:%S")
        df = df.set_index("dt").drop(columns=["datetime"])
    except Exception as e:
        return f"Errore lettura file: {e}"

    h = df["h"].values.astype(np.float64)
    l = df["l"].values.astype(np.float64)
    c = df["c"].values.astype(np.float64)
    o = df["o"].values.astype(np.float64)
    n = len(df)

    d, s2, fu, fl = st(h, l, c, 10, 3.0)

    last = df.index[-1]
    dir_now = "LONG" if d[-1] == 1 else "SHORT"
    dir_prev = "LONG" if d[-2] == 1 else "SHORT"
    reversal = d[-1] != d[-2]
    bu, bl = fu[-1], fl[-1]
    close = c[-1]
    dist_su = bu - close
    dist_giu = close - bl

    pos, ep = 0, 0.0
    consec_losses = 0
    cooldown_rem = 0

    for i in range(20, n):
        if i + 1 >= n:
            continue
        dt_next = df.index[i + 1]
        hr_n, mn_n = dt_next.hour, dt_next.minute
        dt_curr = df.index[i]
        og = (hr_n < 9 and dt_curr.hour >= 21) or (dt_next - dt_curr).total_seconds() > 3600

        if pos != 0 and (_is_after_22(hr_n) or og):
            ex = c[i] if (og and not _is_after_22(hr_n)) else o[i + 1]
            pnl = (ex - ep - COMM_PT) if pos == 1 else (ep - ex - COMM_PT)
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
            rev = (pos == 1 and d[i - 1] == 1 and d[i] == -1) or (pos == -1 and d[i - 1] == -1 and d[i] == 1)
            if rev:
                ex = o[i + 1]
                pnl = (ex - ep - COMM_PT) if pos == 1 else (ep - ex - COMM_PT)
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

        if pos == 0 and _in_fascia(hr_n, mn_n):
            if d[i] == 1 and d[i - 1] == -1:
                pos = 1
                ep = o[i + 1] + SLIP
            elif d[i] == -1 and d[i - 1] == 1:
                pos = -1
                ep = o[i + 1] - SLIP

    hr, mn = last.hour, last.minute
    ok_fascia = _in_fascia(hr, mn)
    can_trade = pos == 0 and cooldown_rem == 0 and ok_fascia and reversal

    alert = False
    alert_dir = ""
    if pos == 0 and not reversal and ok_fascia and cooldown_rem == 0:
        if dir_now == "LONG" and dist_giu <= 15:
            alert = True; alert_dir = "SHORT"
        elif dir_now == "SHORT" and dist_su <= 15:
            alert = True; alert_dir = "LONG"

    return json.dumps({
        "timestamp": last.strftime("%d/%m/%Y %H:%M:%S"),
        "direction": dir_now,
        "previous_direction": dir_prev,
        "reversal": bool(reversal),
        "banda_sup": round(bu, 1),
        "banda_inf": round(bl, 1),
        "close": round(close, 1),
        "distanza_banda_sup": round(dist_su, 1),
        "distanza_banda_inf": round(dist_giu, 1),
        "posizione_aperta": pos != 0,
        "posizione_tipo": "LONG" if pos == 1 else "SHORT" if pos == -1 else "CHIUSA",
        "entry_price": round(ep, 1) if pos != 0 else None,
        "cooldown_cb": cooldown_rem,
        "fascia_aperta": ok_fascia,
        "semaforo_verde": can_trade,
        "allerta_reversal": alert,
        "allerta_verso": alert_dir,
    }, indent=2)


@mcp.tool()
def semaforo_signal() -> str:
    """Restituisce il segnale semaforico: VERDE (entra), GIALLO (preallerta), ROSSO (aspetta)"""
    result = json.loads(supertrend_status())
    if result.get("semaforo_verde"):
        return f"SEMAFORO VERDE — ENTRA {result['direction']}"
    elif result.get("allerta_reversal"):
        verso = result["allerta_verso"]
        dist = result.get("distanza_banda_inf") if verso == "SHORT" else result.get("distanza_banda_sup")
        return f"ALLERTA — possibile reversal {verso} (close a {dist} pt dalla banda)"
    else:
        reasons = []
        if not result.get("reversal"):
            reasons.append("attendi reversal")
        if not result.get("fascia_aperta"):
            reasons.append("fuori fascia")
        if result.get("posizione_aperta"):
            reasons.append(f"posizione {result['posizione_tipo']} aperta")
        if result.get("cooldown_cb", 0) > 0:
            reasons.append(f"CB attivo ({result['cooldown_cb']} skip)")
        return f"SEMAFORO ROSSO — {', '.join(reasons)}"


@mcp.tool()
def list_data_files() -> str:
    """Elenca tutti i file dati disponibili nella cartella dati/"""
    files = [f.name for f in sorted(DATI.iterdir()) if f.is_file()]
    return "\n".join(files)


@mcp.tool()
def read_data_file(filename: str) -> str:
    """Legge un file dalla cartella dati/"""
    filepath = DATI / filename
    if not filepath.exists():
        available = [f.name for f in DATI.iterdir() if f.is_file()]
        return f"File '{filename}' non trovato. Disponibili: {', '.join(available)}"
    try:
        with open(filepath, "r") as f:
            return f.read()
    except Exception as e:
        return f"Errore lettura: {e}"


@mcp.tool()
def get_recent_bars(count: int = 20) -> str:
    """Legge le ultime N barre DAX 3min dal file dati locale"""
    try:
        df = pd.read_csv(DATA_FILE, sep="\t", header=None,
                         names=["datetime", "high", "low", "open", "close", "volume"])
        return df.tail(count).to_string(index=False)
    except Exception as e:
        return f"Errore: {e}"


@mcp.tool()
def list_scripts() -> str:
    """Elenca gli script Python disponibili in listati/"""
    scripts = [f.stem for f in sorted(LISTATI.glob("*.py")) if f.stem != "trading_mcp_server" and f.stem != "trading_mcp_cloud"]
    return "\n".join(scripts)


@mcp.tool()
def read_report() -> str:
    """Legge il report OOS validation dalla cartella reports/"""
    html_files = list(REPORTS.glob("*.html"))
    if not html_files:
        return "Nessun report trovato."
    with open(html_files[0], "r") as f:
        return f.read()


@mcp.tool()
def run_script(script_name: str, args: str = "") -> str:
    """Esegue uno script Python da listati/ e restituisce l'output"""
    script_path = LISTATI / f"{script_name}.py"
    if not script_path.exists():
        available = [f.stem for f in LISTATI.glob("*.py")]
        return f"Script '{script_name}' non trovato. Disponibili: {', '.join(available)}"
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args.split(),
            capture_output=True, text=True, timeout=120, cwd=BASE
        )
        out = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        err = result.stderr[-1000:] if result.stderr else ""
        if result.returncode != 0:
            return f"ERRORE (codice {result.returncode}):\n{err}\n{out}"
        return out if out else "OK (nessun output)"
    except subprocess.TimeoutExpired:
        return "Timeout: script eseguito oltre 120s"
    except Exception as e:
        return f"Errore esecuzione: {e}"


def st(h, l, c, p, m):
    n = len(h)
    d = np.ones(n)
    tr = np.zeros(n)
    a = np.zeros(n)
    s2 = np.zeros(n)
    fu = np.zeros(n)
    fl = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    s = 0.0
    for i in range(1, p):
        s += tr[i]
    a[p] = s / p
    for i in range(p + 1, n):
        a[i] = (a[i - 1] * (p - 1) + tr[i]) / p
    for i in range(p, n):
        hl = (h[i] + l[i]) / 2
        ub = hl + m * a[i]
        lb = hl - m * a[i]
        if i == p:
            fu[i] = ub; fl[i] = lb; s2[i] = ub; d[i] = -1
        else:
            fu[i] = ub if (ub < fu[i - 1]) or (c[i - 1] > fu[i - 1]) else fu[i - 1]
            fl[i] = lb if (lb > fl[i - 1]) or (c[i - 1] < fl[i - 1]) else fl[i - 1]
            if d[i - 1] == 1:
                s2[i] = fl[i]
                if c[i] <= fl[i]:
                    d[i] = -1; s2[i] = fu[i]
                else:
                    d[i] = 1
            else:
                s2[i] = fu[i]
                if c[i] >= fu[i]:
                    d[i] = 1; s2[i] = fl[i]
                else:
                    d[i] = -1
    return d, s2, fu, fl


async def health(request):
    return PlainTextResponse("OK")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app = mcp.sse_app()
    app.router.routes.insert(0, Route("/", endpoint=health))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
