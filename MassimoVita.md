# Strategia Massimo Vita — SuperTrend DAX 3min

## Parametri

| Parametro | Valore |
|-----------|:------:|
| Timeframe | 3min |
| Periodo ST | 10 |
| Moltiplicatore | **3.0** (max PnL) o **4.0** (meno trade) |
| TP fisso | NO (peggiora) |
| Fasce orarie | 9-11 / 15:30-17:30 |
| Commissioni | 1+1 EUR consigliate |

## Regole

- **Ingresso long**: reversal ST da -1 a +1, entro all'open della barra successiva
- **Ingresso short**: reversal ST da +1 a -1, entro all'open della barra successiva
- **Uscita**: solo inversione ST (sempre attiva, anche fuori fascia)
- **Filtro orario**: ingressi solo 9:00-11:00 e 15:30-17:30

## Backtest (gen 2023 → mag 2026, 148.647 barre 3min)

### SuperTrend(10, 3.0) — Max rendimento

| Commissioni | PF | Tot pt | Tot EUR | EUR/anno |
|:-----------:|:--:|:------:|:-------:|:--------:|
| 0 EUR/giro | 1.569 | +29.079 | +727K | +214K |
| 1+1 EUR (2 EUR) | 1.566 | +28.919 | +723K | +213K |
| 4+4 EUR (8 EUR) | 1.557 | +28.438 | +711K | +209K |

- Trade: **2.004** (~590/anno, ~2.4/giorno)
- Win rate: **46.3%**
- Avg trade: **+14.5 pt**
- Avg win: **+66.7 pt** / Avg loss: **-30.4 pt** (reward:risk ~2.2:1)

### SuperTrend(10, 4.0) — Meno trade

| Commissioni | PF | Tot pt | Tot EUR | EUR/anno |
|:-----------:|:--:|:------:|:-------:|:--------:|
| 0 EUR/giro | 1.539 | +22.497 | +562K | +165K |
| 1+1 EUR (2 EUR) | 1.537 | +22.416 | +560K | +165K |
| 4+4 EUR (8 EUR) | 1.526 | +22.065 | +552K | +162K |

- Trade: **1.349** (~400/anno, ~1.6/giorno)
- Win rate: **46.7%**
- Avg trade: **+16.7 pt**
- Avg win: **+74.5 pt** / Avg loss: **-33.1 pt** (reward:risk ~2.25:1)

### Confronto moltiplicatori

| Mult | Trade | WR | Avg pt | Tot pt | PF |
|:----:|:-----:|:--:|:------:|:------:|:--:|
| 3.0 | 2.004 | 46.3% | +14.5 | **+29.079** | **1.569** |
| 3.5 | 1.627 | 47.1% | +13.8 | +22.386 | 1.470 |
| 4.0 | 1.349 | 46.7% | **+16.7** | +22.497 | 1.539 |

## Perché il TP fisso NON funziona

Il TP taglia i vincenti (avg win ~70pt) e lascia correre i perdenti. Su un sistema trend-following con reward:risk 2.2:1, il TP distrugge l'edge.

## Limiti

- **Win rate 46%**: più perdenti che vincenti, serve disciplina
- **Solo DAX**: testato su un solo strumento
- **3.4 anni di dati**: ciclo di mercato limitato
- **Validazione OOS**: i parametri vanno validati su dati fuori campione

## Verdetto

Massimo Vita aveva ragione: **la strategia funziona bene**. Con ST(10,3.0) e commissioni 1+1 EUR fa +723K EUR in 3.4 anni, PF 1.566. Edge solido, pochi trade, alto reward:risk.

La scelta migliore: **ST(10, 3.0)** per max rendimento, **ST(10, 4.0)** se vuoi meno operatività.
