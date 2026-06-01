# BUND — Risultati Finali

## Data
- BUND 1h: 28.568 candele, 2018-2026
- BUND 1min: 1.5M tick
- Contratto marzo 2026: 1.245 candele

## Cosa abbiamo testato

### 1. SuperTrend + regime-adaptive TP
- PF=0.96 su 8 anni — PIATTO
- Non c'è trend-following edge su BUND

### 2. BB Mean Reversion (multi-TF)
- PF=1.06 su 8 anni (ON/OFF filter)
- Non regge OOS su contratto specifico (PF=0.85)

### 3. ATR-channel / Donchian breakout
- Nessun edge (PF max 1.04 OOS con filtro)

### 4. RSI + Volume confirmation ✅
**MIGLIOR SISTEMA**

| Periodo | PF | Trades | PnL |
|---|---|---|---|
| IS 2018-2019 | 1.57 | 76 | +5.20 |
| VAL 2020-2022 | 1.16 | 71 | +2.26 |
| OOS 2023-2026 | 1.24 | 65 | +2.74 |
| FULL | **1.24** | **171** | **+6.96 pt** |

Parametri: RSI(14), soglie 20/75, TP=2×ATR, volume > 2× media.
ON/OFF filter: rolling PnL 3 mesi.

### 5. Gap continuation intraday
- 52% WR, +7.7pt su 2.5 anni, 1 trade/settimana
- Edge diverso, difficile combinare col 1h

## Lezioni dalla "via Simons"

1. **Gli edge sono momentanei** — lo ST era piatto 8 anni, poi ha funzionato 3 mesi sul contratto marzo 2026
2. **Niente ottimizzazione mensile** — l'IS_PF non predice l'OOS (corr = -0.15)
3. **Parametri fissi battono ottimizzati** — il sistema migliore usa RSI(14) fissi, non ottimizzati
4. **ON/OFF filter funziona** — taglia trade in mesi negativi, migliora PF da 1.13 a 1.24
5. **Più segnali non sempre meglio** — RSI+Volume puro (PF=1.24) batte RSI+Volume+BB (PF=1.06)

## Conclusione

C'è un edge su BUND 1h, ma è *reale e piccolo*:
- PF=1.24, +7pt in 8 anni
- 18.8 ticks/anno, ~2 trade/mese
- Non basta per vivere di trading

Strategia onesta, robusta (parametri fissi, non overfittata), ma non abbastanza per un edge sfruttabile.

## File prodotti
- `execution/bund_vs_btp_1h.py` — confronto BUND/BTP 1h
- `execution/bund_st_insample_os.py` — ST in-sample/OOS
- `execution/bund_walkforward_mr.py` — walk-forward mean reversion
- `execution/bund_mr_onoff.py` — MR fisso + ON/OFF
- `execution/bund_final_system.py` — sistema combinato
- `execution/bund_rsi_only.py` — RSI+Volume puro
- `execution/analyze_onoff_signal.py` — analisi ON/OFF
- `execution/bund_marzo2026_bb_oos.py` — OOS su contratto
- `execution/bund_weekly_analysis.py` — analisi opzioni settimanali
- `execution/aggregate_bund_1h.py` — aggregatore 1m→1h
- `dati/bund_1h.txt` — dati aggregati 1h
