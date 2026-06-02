# Riepilogo Strategia BTP Future 1h — ST(30, 1.5) + Pivot Trailing

## Dati
- **Fonte:** Tick data (6.2M records, 2023-03-20 → 2025-12-10)
- **Aggregazione:** Candele 1h via `execution/aggregate_ticks_to_1h.py`
- **Dataset finale:** 7.704 candele in `dati/btp_1h_full.txt`
- **Struttura:** `data\topen\thigh\tlow\tclose\tvolume`

## Strategia
- **Entry:** SuperTrend(30, 1.5) — flip rilevato alla chiusura, entry all'open successivo
- **SL:** Ultimo pivot passato (confermato, lookback=5) ± 0.5 × ATR
- **TP:** Prossimo pivot dopo l'entry (trailing strutturale: emerge durante il trade)
- **Costi:** 3€ entry + 3€ exit = 6€/trade
- **1 punto BTP = 1000€**

## Risultati (2,7 anni, 559 trade)

| Metrica | Valore |
|---------|--------|
| Trade totali | 559 (279L / 280S) |
| Win rate | 81.4% (455W / 104L) |
| PnL netto | +181.156 € |
| Avg win | +541 € |
| Avg loss | -626 € |
| Profit Factor | 3.78 |
| Max Drawdown | 2.036 € (32,8%) |
| Bars held avg | 9,2 |
| Sharpe | 10,17 |

## Architettura a 3 Livelli

### Livello 1 — Direttive (`directives/`)
| File | Descrizione |
|------|-------------|
| `supertrend_signals.md` | SOP calcolo SuperTrend e rilevamento flip |
| `classic_pivots_sltp.md` | SOP identificazione pivot e calcolo SL/TP |
| `orchestrate_btp_1h.md` | SOP orchestrazione 4 fasi |

### Livello 2 — Esecuzione (`execution/`)
| File | Descrizione |
|------|-------------|
| `aggregate_ticks_to_1h.py` | Aggrega tick data → candele 1h |
| `supertrend_signals_1h.py` | ST(14, 3.0) segnali su vecchio dataset |
| `classic_pivots_sltp_1h.py` | Pivot lookback=5 + SL/TP |
| `orchestrate_btp_1h.py` | Orchestratore 4 fasi |
| `optimize_btp_1h_full.py` | Grid search ST period×mult×TP strategy |
| `btp_1h_strategy_live.py` | Strategia finale ST(30, 1.5) + pivot |
| `equity_curve_btp_1h.py` | Equity curve con costi, grafici |
| `gen_html_equity.py` | Genera report HTML con dati embedded |

### Livello 3 — Output (`output/`)
| File | Descrizione |
|------|-------------|
| `btp_1h_equity_report.html` | Report interattivo (equity, DD, PnL, trades) |
| `btp_1h_equity_summary.json` | Dati completi (stats + 559 trade + equity) |
| `btp_1h_equity_curve.png` | Grafico equity curve |
| `btp_1h_equity_segments.png` | Equity con segmenti trade colorati |
| `optimization_full_results.csv` | 375 combinazioni grid search |
| `best_config_trades.json` | Dettaglio 567 trade best config |
| `trade_setup_live.json` / `.csv` | Setup pronti per live |
| `pivot_levels_1h.json` | 72+ pivot identificati |

## Note Operative
- Il next_pivot **non è noto all'entry**: è un trailing strutturale. Il TP viene aggiornato quando il nuovo swing si forma e viene confermato (5 barre dopo).
- La strategia è interamente replicabile in live: pivot passati confermati, SL deterministico, TP dinamico.
- Costi reali indicativi (future BTP): entry 3€ + exit 3€ = 6€/trade, trascurabili sui volumi.

## Da Fare — Prossima Sessione

### Filtri Aggiuntivi (ridurre drawdown, aumentare robustezza)
- [ ] **Filtro HMM regime** (2-3 stati: trend/range/volatile) — saltare entry in regime sfavorevole
  - Script di riferimento: `riepilogo_hmm_2026-05-26.md`
- [ ] **Filtro volatilità** — saltare entry se ATR < 20ma o beyond dev std
- [ ] **Filtro trend macro** — correlazione con Bund, spread BTP-Bund
- [ ] **Filtro orario** — analizzare performance per ora del giorno, saltare ore deboli
- [ ] **Integrazione filtri in `btp_1h_strategy_live.py`** + test retrospettivo

### Ottimizzazioni
- [ ] **Ricalibrare stop-loss dinamico** (ATR multiplier, trailing activation)
- [ ] **Test su timeframe 30min** per maggiori segnali
- [ ] **Test su altri mercati** (Bund, EuroStoxx) per generalizzazione

### Monitoring & Automazione
- [ ] **Alert automatico** via Telegram/email su nuovi segnali ST(30,1.5)
- [ ] **Dashboard live** con equity, DD, ultimi trade
- [ ] **Backtest automatico** settimanale su nuovi dati
