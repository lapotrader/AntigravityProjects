# Prospetto — Edge su Bund e BTP Future (2018–2026)

## Obiettivo
Trovare un edge statistico reale (direzionale o opzioni) su Bund/BTP Future, dimostrando che il 93-95% del PnL della strategia originale era look-ahead bias.

## Dati
| Strumento | Timeframe | Candele | Periodo | Volatilità annua | ATR medio |
|---|---|---|---|---|---|
| Bund 1h | aggregato da 1min | 28.568 | 2018-2026 | 5.5% | 0.213 pt |
| Bund 1min | tick Eurex | 1.512.802 | 2018-2026 | — | — |
| BTP 1h | continuo | 7.704 | 2023-2025 | 6.2% | 0.214 pt |
| BTP 27feb | contratto specifico | 708 | feb-giu 2026 | — | — |

## Strategie testate

### 1. SuperTrend + regime-adaptive TP ❌
- Bund: PF=0.96 (8 anni, 1.018 trade) — **piatto**
- BTP: PF=1.04 (2.7 anni, 274 trade) — **piatto**
- Il trend-following non funziona su nessuno dei due

### 2. BB Mean Reversion (multi-TF) ❌
- Bund: PF=1.06 OOS (ma si rompe su contratto specifico: PF=0.85)
- BTP: PF=1.02 OOS (overfitta: IS 1.65 → OOS 1.02)
- Stabile ma troppo marginale

### 3. ATR-channel / Donchian breakout ❌
- Bund: PF max 1.04 OOS
- BTP: zero trades
- Niente edge

### 4. RSI + Volume confirmation ✅ **MIGLIORE**
- **Bund**: PF=1.24, +7pt/8anni, 171 trade
- **BTP**: PF=6.52, +5pt/2.7anni, 31 trade

### 5. Gap continuation (intraday, solo Bund) ✅
- 52% WR, +7.7pt/2.5anni, 1 trade/settimana
- Edge su microstruttura, non combinabile col 1h

## Sistema finale raccomandato

**RSI(14) + Volume confirmation + ON/OFF filter**

Parametri:
- RSI period: 14
- Soglie: oversold 20, overbought 75
- Volume filter: entry solo se volume > 2× media 20 periodi
- SL: swing low/high 5 barre (fallback: 2 ATR)
- TP: 2 ATR
- Timeout: 40 barre

ON/OFF filter: rolling PnL 3 mesi. Si spegne quando < 0, si riaccende quando ≥ 0.

### Performance attesa (Bund, 8 anni)
| Metrica | Valore |
|---|---|
| Profit factor | 1.24 |
| Trades totali | 171 |
| Trades/anno | ~21 |
| Win rate | 53% |
| PnL totale | +7 pt |
| PnL/anno | +0.87 pt |
| Max drawdown | -11.5 pt |
| Sharpe (approx) | ~0.3 |

### Performance attesa (BTP, 2.7 anni)
| Metrica | Valore |
|---|---|
| Profit factor | 6.5 |
| Trades totali | 31 |
| Trades/anno | ~12 |
| Win rate | 35% |
| PnL totale | +5 pt |
| PnL/anno | +1.9 pt |

## Lezioni

1. **Nessun edge persistente** — gli edge appaiono e scompaiono. Il SuperTrend è stato piatto 8 anni, poi ha fatto PF=2.52 per 3 mesi. L'unico modo per sfruttarli è monitoraggio live, non backtest fisso.

2. **L'ottimizzazione è nemica dell'edge** — parametri fissi battono parametri ottimizzati mese per mese (corr IS_PF→OOS_PF = -0.15).

3. **Meno segnali = meglio** — RSI+Volume puro batte RSI+Volume+BB (PF 1.24 vs 1.06 su Bund).

4. **ON/OFF filter funziona** — taglia il 40% dei trade, migliora PF del 10-15%.

5. **Volatilità genera edge** — BTP (6.2%) ha edge 5× più grande di Bund (5.5%). Strumenti più volatili = opportunità migliori.

## Warning

- Su Bund l'edge è reale ma troppo piccolo per trading operativo (2 trade/mese, 0.87pt/anno)
- Su BTP l'edge è grosso ma il campione è piccolo (2.7 anni). I dati 2026 mostrano degrado
- Il sistema RSI+Volume si rompe sui dati più recenti in entrambi gli strumenti
- Servirebbero più strumenti/segnali per costruire un portafoglio diversificato
