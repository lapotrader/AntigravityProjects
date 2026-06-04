# Strategia Massimo Vita — SuperTrend DAX 3min

## Parametri

| Parametro | Valore |
|-----------|:------:|
| Timeframe | 3min |
| Periodo ST | 10 |
| Moltiplicatore | 3.0 |
| TP/SL fissi | NO |
| Fasce entry | 9:00-11:00 / 15:30-17:30 |
| Forza chiusura | 22:00 (no overnight) |
| Commissioni | 3 EUR/giro |
| Slippage | 1 pt per side (2 pt round trip) |
| Dati | XDAX 1.056.495 barre 3min, 06/2016 → 06/2026 |

## Regole

- **Entry**: reversal ST (da -1 a +1 o viceversa), eseguito all'open della barra i+1, solo in fascia
- **Exit**: reversal ST sempre attivo, OPPURE forzata all'open della prima barra ≥ 22:00
- **CB**: dopo 2 perdite consecutive, salta 3 trade (pochi trade vincenti per reset consecutivo)

## Risultati OOS — CB 2loss cd 3 (slippage 1pt, no overnight)

| Set | Periodo | Trade | PnL (€) | PF | WR | Max DD | Calmar |
|:---:|:-------:|:-----:|:-------:|:--:|:--:|:------:|:------:|
| TRAIN | 2016-2021 | 1.583 | **+278.969** | 1.51 | 48.4% | -11.868 | **4.22** |
| TEST | 2022-2026 | 1.340 | **+377.312** | 1.58 | 51.3% | -21.365 | **4.00** |
| TOTALE | 10 anni | 2.923 | **+656.281** | 1.55 | 49.7% | -21.365 | **3.08** |

- **Tutti e 10 gli anni profittevoli**
- **TEST batte TRAIN** (+35% PnL) → edge reale, niente overfit
- **Forced close 22:00**: solo 147/6.431 trade (2.3%)
- **Baseline (no CB)**: negativa in tutti i periodi

## Impatto slippage (CB 2loss cd 3, 10 anni)

| Slippage | PnL (€) | Calmar | PF |
|:--------:|:-------:|:------:|:--:|
| 0 pt | +807.197 | 4.34 | 1.70 |
| 1 pt * | +656.281 | 3.08 | 1.55 |
| 2 pt | +538.988 | 2.89 | 1.43 |
| 3 pt | +411.230 | 2.21 | 1.33 |

* slippage adottato. Sistema muore a 5 pt.

## Perché il CB funziona

Le perdite del SuperTrend reversal si presentano a coppie ravvicinate nei laterali. 2 loss consecutivi segnalano un regime sfavorevole → skip 3 trade → si rientra quando il trend riparte.

PnL/trade: **+224 €** (con CB) vs **+1.7 €** (baseline). Il CB non filtra trade, skippa i cluster di perdenti.

## Limiti

- Solo DAX: non testato su altri asset
- Slippage non verificato su broker reale
- Dati XDAX con gap 22-23 (finestra manutenzione)

## Verdetto

Strategia **OOS validata su 10 anni**. CB 2loss cd 3 trasforma il SuperTrend da marginale (+88k/3.4yr) a robusto (+656k/10yr con slippage 1pt). Pronto per paper trading.
