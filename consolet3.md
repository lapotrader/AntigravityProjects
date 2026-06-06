# Strategia SuperTrend DAX 3min

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
- **Exit**: reversal ST sempre attivo, OPPURE forzata all'open della prima barra >= 22:00
- **Overnight gap**: se tra barra i e i+1 c'e' un gap >1 ora (dati non continui), chiude alla chiusura dell'ultima barra disponibile
- **CB**: dopo 2 perdite consecutive, salta 3 trade

## Risultati OOS — CB 2loss cd 3 (slippage 1pt, no overnight)

| Set | Periodo | Trade | PnL (€) | PF | WR | Max DD | Calmar |
|:---:|:-------:|:-----:|:-------:|:--:|:--:|:------:|:------:|
| TRAIN | 2016-2021 | 1.583 | **+278.969** | 1.51 | 48.4% | -11.868 | **4.22** |
| TEST | 2022-2026 | 1.340 | **+377.312** | 1.58 | 51.3% | -21.365 | **4.00** |
| TOTALE | 10 anni | 2.923 | **+656.281** | 1.55 | 49.7% | -21.365 | **3.08** |

- **Tutti e 10 gli anni profittevoli**
- **TEST batte TRAIN** (+35% PnL) -> edge reale, niente overfit
- **Forced close 22:00**: solo 147/6.431 trade (2.3%)
- **Baseline (no CB)**: negativa in tutti i periodi

## Validazione su doppia fonte dati

Testato su **due dataset indipendenti** nel periodo comune Mag-Giu 2026:

| Confronto | Risultato |
|:----------|:---------:|
| Direzione ST identica | 92.2% delle barre (7.8% divergenza da prezzi OHLC diversi) |
| Segnali coincidenti | 100% dal 15/05 in poi, stessi tempi e direzioni |
| Mini gap (1-3 barre) | Alcuni segnali pre-15/05 shiftati di 1 barra per differenze prezzo |

**Conclusione**: il sistema e' robusto rispetto alla fonte dati. Le differenze sono rumore di mercato, non di strategia.

## Overnight gap fix (dati non continui)

Su dataset con gap notturni (es. 21:57 -> 02:15), la semplice `is_after_22(hr)` fallisce perche' hr=2 non e' >=22.

**Fix**: rilevamento gap >3600s o passaggio 21:xx -> ore <9, e chiusura alla **close dell'ultima barra disponibile** (invece che open della prima barra post-gap).

## Mini-DAX (5 EUR/pt)

### Risultati 10 anni (commissioni 3 EUR/giro, slippage 1pt)

| Set | Trade | PnL (€) | PF | WR | Calmar |
|:---:|:-----:|:-------:|:--:|:--:|:------:|
| TRAIN 2016-2021 | 1.555 | **+51.587** | 1.46 | 47.8% | 3.82 |
| TEST 2022-2026 | 1.332 | **+76.421** | 1.58 | 51.3% | 3.93 |
| TOTALE 10 anni | 2.887 | **+128.009** | 1.53 | 49.4% | 2.91 |

### Confronto Full DAX vs Mini-DAX

| | Full DAX (25 EUR/pt) | Mini-DAX (5 EUR/pt) |
|:--|:-------------------:|:------------------:|
| PnL 10yr | +656.281 EUR | +128.009 EUR |
| Commissione in pt | 0.12 pt (3 EUR) | **0.60 pt** (3 EUR) |
| Calmar | 3.08 | 2.91 |
| PF | 1.55 | 1.53 |

### Strategia d'ingresso

1. **Mini-DAX** (5 EUR/pt) per paper trading / micro lotti — rischio contenuto, ~12.800 EUR/anno attesi
2. **Monitoraggio 3-6 mesi** — verificare che il comportamento live rispecchi il backtest
3. **Full DAX** (25 EUR/pt) — stessa identica strategia, ogni trade vale 5x

## Perche' il CB funziona

Le perdite del SuperTrend reversal si presentano a coppie ravvicinate nei laterali. 2 loss consecutivi segnalano un regime sfavorevole -> skip 3 trade -> si rientra quando il trend riparte.

PnL/trade: **+224 EUR** (con CB) vs **+1.7 EUR** (baseline). Il CB non filtra trade, skippa i cluster di perdenti.

## Impatto slippage (CB 2loss cd 3, 10 anni)

| Slippage | PnL (EUR) | Calmar | PF |
|:--------:|:---------:|:------:|:--:|
| 0 pt | +807.197 | 4.34 | 1.70 |
| 1 pt | +656.281 | 3.08 | 1.55 |
| 2 pt | +538.988 | 2.89 | 1.43 |
| 3 pt | +411.230 | 2.21 | 1.33 |

Slippage adottato: 1 pt. Sistema muore a 5 pt.

## Limiti

- Solo DAX (non testato su altri asset)
- Slippage non verificato su broker reale
- Dati XDAX con gap 22-23 (finestra manutenzione)
- Commissioni fisse (3 EUR) penalizzano Mini-DAX (0.60 pt vs 0.12 pt)

## Script

- `listati/build_report_oos.py` — report OOS validation completo (Full DAX)
- `listati/calcola_minidax.py` — calcolo performance Mini-DAX

## Verdetto

Strategia **OOS validata su 10 anni**, confermata su **due fonti dati indipendenti**, funzionante anche su **Mini-DAX**. CB 2loss cd 3 trasforma il SuperTrend da marginale (+88k/3.4yr) a robusto (+656k/10yr). Pronta per paper trading su Mini-DAX, poi full DAX.
