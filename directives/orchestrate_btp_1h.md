# SOP: Orchestrator BTP 1h — Trade Plan Consolidato

Flusso orchestrato in 4 fasi per generare un trade plan completo unendo segnali SuperTrend con livelli SL/TP da pivot classici.

## Fase 1 — Segnali SuperTrend
- Eseguire `execution/supertrend_signals_1h.py` via subprocess
- Lo script carica `dati/1oraprova.txt`, calcola ST(14, 3.0), rileva i flip LONG/SHORT
- Output salvato in `output/supertrend_signals_1h.json`
- Se lo script non esiste o fallisce, loggare l'errore e procedere con dati finti per test

## Fase 2 — Pivot e SL/TP
- Eseguire `execution/classic_pivots_sltp_1h.py` via subprocess
- Lo script calcola pivot giornalieri/settimanali e abbina SL/TP a ogni segnale
- Output salvato in `output/trade_setup_1h.json`
- Se lo script non esiste o fallisce, loggare l'errore e procedere con dati finti per test

## Fase 3 — Consolidamento Trade Plan
- Caricare `output/supertrend_signals_1h.json` (segnali grezzi)
- Caricare `output/trade_setup_1h.json` (setup con SL/TP)
- Unire i due dataset sulla data/ora di entry
- Per ogni setup calcolare:
  - Direzione (LONG/SHORT)
  - Prezzo entry
  - Stop Loss (SL)
  - Take Profit (TP)
  - Rischio in punti = |entry - SL|
  - Reward in punti = |TP - entry|
  - Rapporto R/R = Reward / Risk
  - Distanza dalla candela corrente (opzionale)

## Fase 4 — Report e Salvataggio
- Stampare a console tabella ben formattata con tutti i setup
- Salvare il trade plan completo in `output/trade_plan_1h.json`
- Opzionalmente salvare `output/trade_plan_1h.csv` per apertura in Excel
- Stampare riepilogo con: numero setup, R/R medio, tipo prevalente

## Casi Limite
- **Script mancante**: loggare warning, usare dati simulati
- **File JSON mancante**: gestire con file vuoto / segnali simulated
- **Divisione per zero in R/R**: se Risk == 0, impostare R/R = NaN
- **Nessun segnale**: stampare "Nessun setup disponibile"
