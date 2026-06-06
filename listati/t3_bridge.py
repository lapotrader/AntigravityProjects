import json
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP

BASE = Path(r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects")
T3_URL = "http://localhost:8333/T3OPEN"
ITEM = "FR.EUREX.2409430"
DATA_FILE = BASE / "dati" / "ultimissimi5giugno.txt"

mcp = FastMCP("T3 Bridge Locale")


def _fetch_quote():
    params = f"?item={ITEM}&schema=last_price;best_bid1;best_ask1;percentage_change;trade_volume_bi;trade_time"
    req = urllib.request.Request(f"{T3_URL}/get_quotes{params}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        return {"error": str(e)}
    for line in raw.strip().split("\n")[1:]:
        line = line.strip()
        if line.startswith("element="):
            parts = line[8:].split("|")
            if len(parts) >= 6:
                return {
                    "last": parts[0], "bid": parts[1], "ask": parts[2],
                    "chg": parts[3], "vol": parts[4], "time": parts[5],
                }
    return {"error": "no element"}


def _fetch_bars(data_da):
    params = f"?item={ITEM}&frequency=3M&dataDa={data_da}"
    req = urllib.request.Request(f"{T3_URL}/get_history{params}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        return None, str(e)
    lines = raw.strip().split("\n")
    if not lines or not lines[0].startswith("outcome=OK"):
        return None, lines[0] if lines else "empty"
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


@mcp.tool()
def get_quote() -> str:
    """Ottieni la quotazione live DAX Future da T3OPEN (last, bid, ask, variazione %, volume)"""
    return json.dumps(_fetch_quote(), indent=2)


@mcp.tool()
def fetch_new_bars() -> str:
    """Scarica nuove barre da T3OPEN e aggiorna il file dati locale"""
    try:
        with open(DATA_FILE, "r") as f:
            lines = f.readlines()
        last_bar = lines[-1].strip() if lines else None
    except (FileNotFoundError, IndexError):
        last_bar = None

    if last_bar:
        last_dt = datetime.strptime(last_bar.split("\t")[0], "%d/%m/%Y %H:%M:%S")
    else:
        last_dt = datetime.now() - timedelta(days=28)

    fetch_da = max(last_dt - timedelta(days=1), datetime.now() - timedelta(days=28))
    bars, err = _fetch_bars(fetch_da.strftime("%Y%m%d"))
    if err:
        return f"Errore T3: {err}"

    new = []
    for b in bars:
        bt = datetime.strptime(b.split("\t")[0], "%d/%m/%Y %H:%M:%S")
        if bt > last_dt:
            new.append(b)

    if not new:
        return "Nessuna barra nuova."

    with open(DATA_FILE, "a") as f:
        for b in new:
            f.write(b + "\n")

    return f"Scaricate {len(new)} nuove barre (-> {new[-1].split()[0]})"


if __name__ == "__main__":
    mcp.run(transport="stdio")
