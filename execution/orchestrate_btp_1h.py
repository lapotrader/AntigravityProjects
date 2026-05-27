import subprocess
import json
import csv
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')
EXECUTION_DIR = os.path.join(BASE_DIR, 'execution')
DATI_DIR = os.path.join(BASE_DIR, 'dati')

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def run_script(script_name, script_dir):
    script_path = os.path.join(script_dir, script_name)
    if not os.path.exists(script_path):
        print(f"[WARNING] Script non trovato: {script_path}")
        return False
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"[WARNING] {script_name} terminato con errore (codice {result.returncode})")
        print(f"  stderr: {result.stderr.strip()[:200]}")
        return False
    print(f"[OK] {script_name} eseguito con successo")
    if result.stdout.strip():
        for line in result.stdout.strip().split('\n')[-3:]:
            print(f"  | {line}")
    return True

def load_json(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        print(f"[WARNING] File non trovato: {path}")
        return []
    with open(path, 'r') as f:
        return json.load(f)

def generate_fake_setups():
    fake_signals = [
        {"data": "27/05/2026 09:00", "tipo": "LONG", "entry": 124.50},
        {"data": "27/05/2026 12:00", "tipo": "SHORT", "entry": 124.80},
        {"data": "27/05/2026 15:00", "tipo": "LONG", "entry": 124.30},
    ]
    fake_setups = [
        {"data": "27/05/2026 09:00", "tipo": "LONG", "entry": 124.50, "sl": 124.10, "tp": 125.20},
        {"data": "27/05/2026 12:00", "tipo": "SHORT", "entry": 124.80, "sl": 125.20, "tp": 124.10},
        {"data": "27/05/2026 15:00", "tipo": "LONG", "entry": 124.30, "sl": 123.90, "tp": 124.90},
    ]
    return fake_signals, fake_setups

def compute_rr(setup):
    risk = abs(setup['entry'] - setup['sl'])
    reward = abs(setup['tp'] - setup['entry'])
    rr = reward / risk if risk > 0 else float('nan')
    return round(risk, 2), round(reward, 2), round(rr, 2)

def build_trade_plan(signals, setups):
    setup_lookup = {}
    for s in setups:
        key = s.get('timestamp', s.get('data', ''))
        setup_lookup[key] = s

    plan = []
    for sig in signals:
        key = sig.get('data', '')
        s = setup_lookup.get(key, {})
        entry = sig.get('prezzo_entry', sig.get('entry', s.get('entry', 0)))
        direzione = sig.get('direzione', sig.get('tipo', ''))
        sl = s.get('sl', None)
        tp = s.get('tp', None)
        if sl is None or tp is None or entry == 0:
            continue
        risk, reward, rr = compute_rr({'entry': entry, 'sl': sl, 'tp': tp})
        plan.append({
            'data': key,
            'direzione': direzione,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'rischio_punti': risk,
            'reward_punti': reward,
            'rr_ratio': rr,
        })
    return plan

def print_report(plan):
    if not plan:
        print("\n=== NESSUN SETUP DISPONIBILE ===")
        return

    print("\n" + "=" * 100)
    print("TRADE PLAN BTP 1h")
    print("=" * 100)
    header = f"{'Data':<22} {'Dir':<8} {'Entry':<10} {'SL':<10} {'TP':<10} {'Risk(pt)':<10} {'Rew(pt)':<10} {'R/R':<8}"
    print(header)
    print("-" * 100)
    for t in plan:
        print(f"{t['data']:<22} {t['direzione']:<8} {t['entry']:<10.2f} {t['sl']:<10.2f} {t['tp']:<10.2f} {t['rischio_punti']:<10.2f} {t['reward_punti']:<10.2f} {t['rr_ratio']:<8.2f}")
    print("-" * 100)

    rr_values = [t['rr_ratio'] for t in plan if t['rr_ratio'] == t['rr_ratio']]
    long_count = sum(1 for t in plan if t['direzione'] == 'LONG')
    short_count = sum(1 for t in plan if t['direzione'] == 'SHORT')
    avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
    prevalent = 'LONG' if long_count >= short_count else 'SHORT'

    print(f"\nRIEPILOGO:")
    print(f"  Setup totali:      {len(plan)}")
    print(f"  LONG:              {long_count}")
    print(f"  SHORT:             {short_count}")
    print(f"  R/R medio:         {avg_rr:.2f}")
    print(f"  Tipo prevalente:   {prevalent}")
    print("=" * 100)

def save_json(plan, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w') as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    print(f"[OK] Salvato: {path}")

def save_csv(plan, filename):
    if not plan:
        return
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=plan[0].keys())
        writer.writeheader()
        writer.writerows(plan)
    print(f"[OK] Salvato: {path}")

def main():
    print("=" * 60)
    print("ORCHESTRATOR BTP 1h — Trade Plan")
    print(f"Esecuzione: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    ensure_output_dir()

    phase_ok = True

    print("\n--- FASE 1: SuperTrend Signals 1h ---")
    st_ok = run_script('supertrend_signals_1h.py', EXECUTION_DIR)
    if not st_ok:
        run_script('test_segnali_1h.py', SCRIPTS_DIR)

    print("\n--- FASE 2: Classic Pivots SL/TP 1h ---")
    pivots_ok = run_script('classic_pivots_sltp_1h.py', EXECUTION_DIR)

    print("\n--- FASE 3: Consolidamento Trade Plan ---")
    raw_signals = load_json('supertrend_signals_1h.json')
    signals = raw_signals.get('segnali', raw_signals) if isinstance(raw_signals, dict) else raw_signals
    setups = load_json('trade_setup_1h.json')

    if not signals or not setups:
        print("[INFO] Dati reali non trovati — uso segnali simulati per test")
        signals, setups = generate_fake_setups()

    plan = build_trade_plan(signals, setups)

    print(f"Segnali grezzi:     {len(signals)}")
    print(f"Setup con SL/TP:    {len(setups)}")
    print(f"Trade plan pronti:  {len(plan)}")

    print("\n--- FASE 4: Report e Salvataggio ---")
    print_report(plan)
    save_json(plan, 'trade_plan_1h.json')
    save_csv(plan, 'trade_plan_1h.csv')

    print("\nOrchestrazione completata.")

if __name__ == '__main__':
    main()
