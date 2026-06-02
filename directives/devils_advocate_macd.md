# Devil's Advocate — MACD V2: "Ristudiato" senza look-ahead

## Risultato: Il MACD su BTP 1h NON HA UN EDGE ROBUSTO dopo costi reali

Dopo aver riscritto da zero il sistema MACD con:
- **Zero look-ahead**: indicatori shiftati, entry a open[i] dopo crossover confermato
- **Costi reali**: slippage 1 tick (0.01pt), commissioni 3+3€, gap through
- **Split cronologico**: IS=2023 → OOS=2024 → FWD=2025 → Blind=2026
- **Due modalità SL**: swing 5-bar (originale) + pure ATR (nuovo)
- **Griglia estesa**: 720 combinazioni tra fast/slow/signal/tp/SL

---

## 1. I numeri veri (dopo costi, nessun look-ahead)

### Miglior sistema trovato: MACD(5,30,3) TP=5x ATR, SL=2x ATR (pure ATR, no swing)

| Periodo | Trade | PF | PnL | WR | DD max | Avg/trade |
|---------|-------|----|----|-----|--------|----------|
| IS 2023 | 92 | 1.20 | +6.438€ | 39% | 9.451€ | +70€ |
| OOS 2024 | 121 | 1.02 | +811€ | 36% | 4.077€ | +7€ |
| FWD 2025 | 115 | 1.10 | +2.445€ | 33% | 5.433€ | +21€ |
| Blind 2026 | 27 | 1.62 | +5.551€ | 56% | 2.931€ | +206€ |
| **TOTALE** | **354** | **1.16** | **+15.700€** | **37%** | **9.451€** | **+44€** |

### Il sistema originale V1: MACD(5,22,3) TP=4x con costi reali

| Periodo | PF | PnL |
|---------|----|----|
| IS 2023 | 1.38 | +12.737€ |
| OOS 2024 | 0.89 | -4.079€ |
| FWD 2025 | 0.81 | -5.535€ |
| Blind 2026 | 1.07 | +877€ |
| **TOTALE** | **1.03** | **+3.290€** |

Il sistema V1 originale **perde soldi** su OOS e FWD quando si applicano costi reali.

---

## 2. Sensitivity allo slippage (sistema migliore)

| Slippage | PF | PnL | Note |
|----------|----|----|------|
| 0 tick | 1.18 | +17.355€ | Utopia |
| **1 tick** | **1.16** | **+15.700€** | **Scenario realistico** |
| 2 tick | 1.08 | +7.720€ | Mercato veloce |
| 3 tick | **0.94** | **-6.557€** | **MARGINE NEGATIVO** |

A 3 tick di slippage (0.03pt = 30€), il sistema diventa NEGATIVO. L'edge è
talmente sottile che basta uno slippage extra di 2 tick per ucciderlo.

---

## 3. Non esiste un sistema MACD robusto su BTP 1h

Abbiamo cercato su 720 combinazioni (fast 5/8/12, slow 16/19/22/26/30,
signal 3/5/9, tp 2/3/4/5, sl 2.0/2.5, swing/atr). **Nessuna** ha PF>1.05
su tutti e 4 i periodi.

La TOP 10 della grid search (scelta su IS×OOS) **MUORE TUTTA su FWD 2025**:

``` 
#1 MACD(8,16,5) tp=4    FWD PF=0.75  Blind PF=1.13
#4 MACD(5,19,3) tp=5    FWD PF=0.97  Blind PF=1.12  ← il "meno peggio"
```

Il sistema migliore (MACD(5,30,3) tp=5) è stato trovato cercando su TUTTI
e 4 i periodi — ma questa è una forma di data snooping. Il vero edge è
quasi zero.

### Perché il 2025 è il problema

Il 2025 è stato probabilmente un anno laterale/range-bound per il BTP.
Il MACD crossover è un sistema trend-following: in range perde soldi.
Il fatto che TUTTE le combinazioni muoiano sul 2025 indica che **il problema
non è nei parametri ma nella strategia stessa**.

---

## 4. Perché il V1 originale sembrava funzionare

| Differenza | V1 originale | V2 realistico | Impatto |
|-----------|-------------|--------------|---------|
| Commissioni | Non modellate | 3+3€/trade | -0.02 PF |
| Slippage | 0 | 1 tick (0.01pt) | -0.10 PF |
| Gap through | Ignorato | Modellato | -0.03 PF |
| Split cronologico | 50/50 random | IS/OOS/FWD/Blind | Mascherava overfitting |
| Parametro finale | Non nella griglia | Nella griglia | Trovato per caso |

Il V1 originale dava PF netto 1.17 su 2.7 anni. Il V2 realistico dà PF 1.16
sul migliore scenario — ma su FWD 2025 il PF scende a 0.75.

**Il V1 era un artefatto statistico + costi non modellati.**

---

## 5. Raccomandazione

### NON andare live con MACD crossover su BTP 1h

L'edge non esiste dopo costi reali. Il sistema:
- Perde sul 2025 (PF=0.75-0.97 per tutte le combo)
- È estremamente sensibile allo slippage (basta +2 tick per ucciderlo)
- Ha WR 37% — psicologicamente devastante
- Guadagna solo da pochi TP grossi che coprono tante SL piccole

### Prossimi passi possibili

1. **Altri timeframe**: MACD su 4h o daily potrebbe avere più segnale
2. **Altri strumenti**: provare su Bund (più liquido, meno spread)
3. **Filtro regime**: aggiungere HMM o volatility filter per evitare range
4. **Strategie non trend-following**: mean reversion, breakout, order flow
5. **Multi-timeframe**: conferma su timeframe superiore prima di entrare

### File aggiornati

- `macd_v2.py` — backtest pulito (nessun look-ahead, costi reali, 720 combo)
- `risultati_macd_v2_best.txt` — risultati completi del miglior sistema
- `directives/devils_advocate_macd.md` — questa analisi
