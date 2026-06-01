# BTP MACD — Sistema per Trading Live

## Parametri finali
- **MACD(5,22,3)** — crossover classico
- **TP**: 4 × ATR(30)
- **SL**: swing low/high 5 bar (fallback 2 × ATR)
- **Timeout**: 40 barre (1h)
- **Timeframe**: 1h (Eurex 08:00-21:00 CET)

## Regole
- LONG: MACD line incrocia SOPRA Signal → entro a open[i+1]
- SHORT: MACD line incrocia SOTTO Signal → entro a open[i+1]
- Nessun filtro aggiuntivo (no volume, no istogramma, no regime)

## Perché questi parametri
Trovati con robustness analysis su griglia 1.920 combinazioni:
- IS 2023 per scegliere il plateau
- OOS 2024-25 per conferma
- Dati 2026 come blind test finale (mai visti prima)
- Il plateau fast=5-6, slow=21-24, sig=3, tp=4 dà 10 combinazioni vicine tutte con PF>1.1

## Performance in EUR reali (10€/tick, 3+3€ commissioni)

| Periodo | Trades | PF lordo | PF netto | PnL netto | EUR/trade |
|---|---|---|---|---|---|
| IS 2023 | 162 | 1.24 | 1.21 | +10.818 | +67 |
| OOS 24-25 | 174 | 1.19 | 1.16 | +5.396 | +31 |
| FULL 2.7 anni | 340 | 1.20 | 1.17 | +14.920 | +44 |
| 2026 (blind test) | 30 | 2.17 | 2.13 | +8.790 | +293 |

**Proiezione annua:** +5.471 EUR netti (10-11 trade/mese, WR ~39%)

## Warning
- Dati 2026 anomali (PF=2.17), non aspettarsi lo stesso in live
- PF atteso realistico: 1.15-1.35
- Position sizing: 0.5-1% per trade, max drawdown stimato -6.4%
- Monitorare PF rolling ultimi 50 trade. Se sotto 0.9 fermarsi.

## Roadmap
1. Implementare MACD(5,22,3) su piattaforma con TP=4×ATR e SL swing
2. Forward test 1-2 mesi (carta)
3. Iniziare con posizione 1 contratto, risk 0.5%/trade
4. Tracciare PF rolling ogni 50 trade
5. Se funziona, espandere ad altri strumenti (Bund, Schatz, Bobl)

## File
- `dati/btp_1h_full.txt` — dati BTP 1h 2023-2025 (7.704 candele)
- `dati/27 febbraio.txt` — dati BTP 1h 2026 (708 candele)
- `directives/btp_macd_prospetto.html` — prospetto HTML
- `execution/btp_macd_robustness.py` — script robustness analysis
