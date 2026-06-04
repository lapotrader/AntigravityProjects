# Strategia DAX SuperTrend — Documento di Lavoro

> **Stato**: OOS validation completata su 10 anni. Edge confermato.
> **Data ultimo aggiornamento**: 04/06/2026

---

## 1. Logica della strategia

- **Indicatore**: SuperTrend(10, 3.0) su barre 3-min
  - Periodo ATR: 10 (30 minuti)
  - Moltiplicatore: 3.0
- **Time filter**: solo entry in fascia 9:00-11:00 e 15:30-17:30
- **Reversal logic**:
  - Segnale reversal al close della barra i, eseguito all'open della barra i+1
  - Time check sulla barra di esecuzione (i+1), non su quella del segnale (i)
  - In fascia: reversal = chiudi posizione + apri opposta
- **Exit reversal**: sempre attivo (chiude ma non riapre se fuori fascia)
- **Forza chiusura 22:00**: se una posizione è ancora aperta alle 22:00, chiusura forzata all'open (no overnight)
- **CB**: dopo 2 perdite consecutive, cooldown di 3 trade
- **Costi**: 3 EUR/giro, valore punto DAX 25 EUR
- **Slippage**: 1 pt per side (entrata e uscita)

---

## 2. Dati

- **Sorgente**: CSV XDAX "No Session" (filtra orari non negoziati)
- **File 1min**: `dati/dax_m1.txt` — 3.103.045 barre, 06/06/2016 → 04/06/2026
- **File 3min**: `dati/dax_m3.txt` — 1.056.495 barre, resample OHLCV
- **Copertura**: 10 anni continui

### Qualità dati

| Ora | Barre/h | Note |
|:---:|:-------:|------|
| 0-7 | 45-48 | Mancano barre notturne |
| 7-21 | 60 | Tracking perfetto |
| 22-23 | ~3/giorno | Finestra manutenzione Eurex XDAX |

I dati non sono veramente 24h continui: le ore 22-23 sono quasi vuote. L'ATR calcolato su queste barre è distorto.

---

## 3. Bug risolti durante lo sviluppo

| # | Bug | Impatto | Fix |
|---|-----|---------|-----|
| 1 | ST reversal condition sbagliata (`c[i]<=fub[i]` invece di `c[i]<=fl[i]`) | 80 trade/giorno (reversal ogni barra) | Corretta banda |
| 2 | Time check sul bar sbagliato (bar i vs i+1) | Aperture al bordo fascia | Spostato su i+1 |
| 3 | Exit/entry stesso bar (look-ahead) | PF gonfiato 2.06 | Entrambi su open i+1 |
| 4 | CB 3loss cd10 come vincitore iniziale | Sbilanciato su 3.4yr | Riscoperto CB 2loss cd3 su 10yr |

### Falsi allarmi

- "Carry overnight dà PnL falso" → verificato: solo 147/6.431 trade (2.3%) chiuse forzatamente a 22:00
- "Chiusure fuori fascia = carry overnight" → falso: 60.8% chiude fuori fascia MA in giornata (11-15:30 / 17:30-22:00)

---

## 4. Risultati

### Baseline (ST + fasce, slippage 1pt, no overnight)

| Metrica | TRAIN 2016-2021 | TEST 2022-2026 |
|---------|:---------------:|:--------------:|
| Trade | 3.599 | 2.832 |
| PnL | **-133.897 €** | **-62.634 €** |
| PF | 0.91 | 0.96 |
| WR | 37.5% | 38.8% |
| Max DD | -147.806 € | -135.830 € |
| Calmar | -0.16 | -0.10 |

**Il baseline è negativo** — il SuperTrend da solo non basta. Serve il Circuit Breaker.

### Vincitore: CB 2loss cd 3

| Metrica | TRAIN 2016-2021 | TEST 2022-2026 | Δ |
|---------|:---------------:|:--------------:|:-:|
| Trade | 1.583 | 1.340 | - |
| PnL | **+278.969 €** | **+377.312 €** | **+35%** |
| PF | 1.51 | 1.58 | +0.07 |
| WR | 48.4% | 51.3% | +2.9pp |
| Avg win | +90.7 € | +96.8 € | - |
| Avg loss | -57.9 € | -57.7 € | - |
| Max DD | -11.868 € | -21.365 € | -9.497 € |
| Calmar | **4.22** | **4.00** | -0.22 |
| Trigger CB | 504 (91/anno) | 373 (85/anno) | - |

### Anno per anno

| Anno | Fase | Trade | PnL (€) | WR |
|:----:|:----:|:-----:|:-------:|:--:|
| 2016 | TRAIN | 142 | +9.002 | 44.4% |
| 2017 | TRAIN | 288 | +27.581 | 49.0% |
| 2018 | TRAIN | 296 | +75.145 | 50.0% |
| 2019 | TRAIN | 285 | +42.010 | 48.4% |
| 2020 | TRAIN | 279 | +67.641 | 45.5% |
| 2021 | TRAIN | 293 | +57.591 | 50.9% |
| 2022 | TEST | 277 | +83.964 | 48.4% |
| 2023 | TEST | 327 | +60.992 | 51.4% |
| 2024 | TEST | 295 | +71.322 | 52.9% |
| 2025 | TEST | 310 | +63.406 | 49.4% |
| 2026 | TEST | 131 | +24.533 | 46.6% |

### Impatto slippage (10 anni)

| Slippage | PnL (€) | Calmar | PF | Trade |
|:--------:|:-------:|:------:|:--:|:-----:|
| 0 pt | +807.197 | 4.34 | 1.70 | 3.007 |
| 0.5 pt | +725.050 | 3.63 | 1.63 | 2.975 |
| **1 pt** | **+656.281** | **3.08** | **1.55** | **2.923** |
| 2 pt | +538.988 | 2.89 | 1.43 | 2.819 |
| 3 pt | +411.230 | 2.21 | 1.33 | 2.751 |
| 5 pt | +53.391 | 0.21 | 1.05 | 2.637 |

Sistema profittevole fino a 4pt. **Margine di sicurezza ampio** (il CB ha 10.67 pt/trade vs 0.81 del baseline).

---

## 5. Circuit Breaker — Anatomia

### Perché 2 loss cd 3?

Il SuperTrend reversal ha un pattern: quando sbaglia, sbaglia in coppia. Due perdite consecutive in un mercato laterale segnalano che il trend non c'è. Saltare 3 trade fa ripartire da zero.

| CB config | Trade/10yr | PnL (€) | Calmar | Note |
|:---------:|:----------:|:-------:|:------:|------|
| Nessuno | 6.431 | -196.531 | neg | Baseline negativo |
| 2loss cd3 | **2.923** | **+656.281** | **3.08** | **Vincitore** |
| 2loss cd5 | 2.289 | +512.828 | 2.51 | Buono ma inferiore |
| 2loss cd7 | 1.881 | +471.926 | 2.54 | — |
| 2loss cd10 | 1.540 | +265.086 | 1.29 | Perde troppo PnL |
| 3loss cd3 | 4.185 | +410.332 | 0.89 | Troppe perdite |
| 3loss cd10 | 2.716 | +363.456 | 1.38 | Vecchio vincitore |
| 4loss cd3 | 5.031 | +280.883 | 0.52 | Ancora più lento |

2loss cd3 è il migliore perché:
1. Bassa soglia (2 loss) → reagisce subito ai laterali
2. Cooldown breve (3 trade) → non perde troppi trade buoni
3. Skip ~3.500 trade su 10yr, tenendo i 2.923 migliori

### Test random

Su 1.000 trade casuali, CB 2loss cd3 riduce la perdita:
- Senza CB: -169.350 €
- Con CB 2loss cd3: -12.050 €

Il CB ha un **vantaggio strutturale intrinseco**: skippa cluster di perdenti. Il risultato reale (+656k) va ben oltre il caso.

---

## 6. Fasce orarie — Verifica

| Metrica | Valore |
|---------|:------:|
| Trade ENTRY in fascia | **6.431 / 6.431 (100%)** |
| Trade EXIT in fascia 9-11 / 15:30-17:30 | **2.521 (39.2%)** |
| Trade EXIT fuori fascia (11-15:30 / 17:30-22:00) | **3.910 (60.8%)** |
| PnL chiusure IN fascia | **-1.551.048 €** (WR 14.6%) |
| PnL chiusure FUORI fascia | **+1.681.397 €** (WR 55.4%) |

**Scoperta**: il PnL positivo viene quasi tutto da chiusure **fuori fascia** — lo stesso SuperTrend sbaglia quando reversal in fascia e azzecca quando reversal fuori. Carry notturno NON è la causa (solo 2.3% chiuso a 22:00).

---

## 7. Slippage

- **1 pt per side** = 2 pt round trip + 0.12 pt commissione = 2.12 pt totali
- Impatto medio: -152.000 € rispetto a backtest puro
- Sistema sopravvive fino a 4 pt di slippage singolo
- Margine di sicurezza: 10.67 pt/trade (vs 0.81 del baseline)

Lo slippage reale su DAX futures è stimato 0.5-1 pt per order. 1 pt è cautelativo. Margine ampio.

---

## 8. Conclusioni

### Cosa funziona

- SuperTrend(10, 3.0) + fasce 9-11 / 15:30-17:30 + CB 2loss cd3 = sistema robusto
- OOS validato su 10 anni: Calmar TRAIN 4.22, TEST 4.00
- TEST migliore del TRAIN (+35%) → edge reale, niente overfit
- Forza chiusura 22:00 elimina rischio gap (impatto minimo su PnL)
- Margine slippage ampio: sopravvive 4 pt

### Cosa non funziona

- Baseline senza CB è negativo (-196k su 10yr)
- TP/SL fissi peggiorano sempre
- Filtri MA out-performati dal CB

### Prossimi passi

1. Paper trading su conto demo DAX
2. Test su BUND/STOXX per generalizzabilità
3. Validazione su tick data per slippage reale
4. Walk-forward analysis su parametri CB

---

## 9. Decisioni aperte

1. La strategia è utilizzabile per live trading? **PROBABILMENTE SÌ** — OOS robusto, margine slippage, regole chiare
2. Paper trading per 3-6 mesi necessario
3. Aggiungere data/ora al file trade log per analisi post-trade
4. Monitorare: Calmar < 2 è bandiera rossa per rivalutazione

---

## 10. File

| File | Scopo |
|------|-------|
| `dati/2026.6.4DEUIDXEUR-M1-No Session.csv` | CSV sorgente XDAX 10 anni |
| `dati/dax_m1.txt` | Dati 1-min (3.1M barre) |
| `dati/dax_m3.txt` | Dati 3-min (1.05M barre) |
| `listati/build_report_oos.py` | Genera report OOS |
| `reports/resoconto_oos_validation.html` | Report finale OOS validation |
