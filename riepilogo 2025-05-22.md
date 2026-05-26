# BTP / Trading Analysis — Full Project Inventory

## Panoramica

Progetto di analisi quantitativa su **BTP Future**, **BUND**, **DAX**, **STOXX 50**, **MiniDAX**. Strategia principale: **Supertrend** con ricostruzione barre intraday custom (220m, 3h, 1h). Include aggregazione dati, ottimizzazione parametri, backtesting, report HTML, e codici ProRealTime 10.3.

---

## Asset Coperti

| Asset | File Dati | Barre | Timeframe |
|-------|-----------|-------|-----------|
| BTP Future | `dati/btp_220m.txt` | 2.086 | 220m ricostruito |
| BTP Future | `dati/btp3h.txt` | 2.086 | 3h ricostruito |
| BTP Future | `dati/giornaliero btp.txt` | 2.403 | Daily |
| BTP Future | `dati/1oraprova.txt` | 692 | 1h diretto |
| BTP Future | `dati/btp 2023-25.txt` | ~6.23M righe | Tick grezzo 2023→2025 (190 MB) |
| BUND | `dati/bund_220m.txt` | 6.127 | 220m ricostruito |
| BUND | `dati/bund_m1.txt` | ~1.51M righe | M1 grezzo |
| DAX | `dati/dax_220m.txt` | 2.611 | 220m ricostruito |
| DAX | `dati/dax_m1.txt` | ~1.13M righe | M1 grezzo |
| STOXX 50 | `dati/stoxx_220m.txt` | 2.571 | 220m ricostruito |
| STOXX 50 | `dati/stoxx_m1.txt` | ~619K righe | M1 grezzo |

---

## Categorie File

Tutti gli script Python sono in `scripts/`.

### 1. Aggregazione Dati (raw → OHLC intraday)

| File | Timeframe | Asset | Descrizione |
|------|-----------|-------|-------------|
| `scripts/aggregate_intraday_220m.py` | 220m | BTP | Aggrega tick in barre 220m (3 bin: 8-11, 11-15, 15-19) |
| `scripts/aggregate_intraday_3h.py` | 3h | BTP | Aggrega tick in barre 3h (3 bin: 8-11, 11-14, 14-17) |
| `scripts/aggregate_intraday_1h.py` | 1h | BTP | Aggrega tick in barre 1h |
| `scripts/aggregate_intraday_220m_bund.py` | 220m | BUND | Aggrega tick in barre 220m |
| `scripts/aggregate_intraday_220m_dax.py` | 220m | DAX | Legge M1 → barre 220m |
| `scripts/aggregate_intraday_220m_stoxx.py` | 220m | STOXX | Legge M1 → barre 220m |

### 2. Ottimizzazione Parametri Supertrend (grid search)

| File | Timeframe | Asset | Descrizione |
|------|-----------|-------|-------------|
| `scripts/optimize_supertrend.py` | Daily | BTP | Grid period×multiplier su daily |
| `scripts/optimize_supertrend_ma.py` | Daily | BTP | Grid ST + MA filter su daily |
| `scripts/optimize_supertrend_220m_bund.py` | 220m | BUND | Grid ST su BUND |
| `scripts/optimize_supertrend_220m_dax.py` | 220m | DAX | Grid ST su DAX |
| `scripts/optimize_supertrend_220m_minidax.py` | 220m | MiniDAX | Grid ST su MiniDAX |
| `scripts/optimize_supertrend_220m_stoxx.py` | 220m | STOXX | Grid ST su STOXX |
| `scripts/optimize_supertrend_3h_btp.py` | 3h | BTP | Grid ST su BTP 3h (480 test) |

### 3. Backtesting

| File | Timeframe | Asset | Descrizione |
|------|-----------|-------|-------------|
| `scripts/backtest_supertrend.py` | Daily | BTP | Backtest con Plotly |
| `scripts/backtest_supertrend_220m_bund.py` | 220m | BUND | Backtest BUND |
| `scripts/backtest_supertrend_220m_stable.py` | 220m | BTP | Variante "stable" (conferma) |
| `scripts/backtest_comparison.py` | Daily | BTP | Confronto varianti side-by-side |

### 4. Portfolio Backtest (multi-asset 220m)

| File | Descrizione |
|------|-------------|
| `scripts/portfolio_backtest_220m.py` | Multi-asset con commissioni |
| `scripts/portfolio_backtest_220m_dax.py` | Solo DAX |
| `scripts/portfolio_backtest_220m_final.py` | Versione finale multi-asset |

### 5. Segnali / Test

| File | Timeframe | Asset | Descrizione |
|------|-----------|-------|-------------|
| `scripts/test_1h_diretti.py` | 1h | BTP | Test segnali ST su 1h diretto |
| `scripts/test_segnali_1h.py` | 1h | BTP | Simulazione segnali 1h |
| `scripts/test_segnali_3h.py` | 3h | BTP | Simulazione segnali 3h |
| `scripts/btp3h_barre_segnali.py` | 3h | BTP | Barre 3h + segnali ST |

### 6. Diagnostica

| File | Descrizione |
|------|-------------|
| `scripts/diagnose_dax_trade.py` | Analisi dettagliata trade DAX specifico |
| `scripts/diagnose_sept2023.py` | Diagnosi trades BTP settembre 2023 |
| `scripts/verify_dax_trade.py` | Verifica trade DAX vs segnali ST |

### 7. Report / Grafici

| File | Descrizione |
|------|-------------|
| `scripts/generate_report_3h.py` | Report HTML da CSV ottimizzazione 3h |
| `scripts/generate_trades_excel.py` | Esporta trades in Excel |
| `scripts/grafico_candele.py` | Viewer candlestick interattivo |
| `scripts/test_grafico.py` | Test plotting base |
| `scripts/generatore_mensile.py` | Report mensile BTP |
| `scripts/volume_profile_mensile.py` | Volume profile mensile |

### 8. Utility

| File | Descrizione |
|------|-------------|
| `scripts/convert_bund.py` | Converte M1 BUND in OHLC standard |
| `scripts/duplicati_finder.py` | GUI per trovare file duplicati (tkinter) |

---

## Output Generati

### HTML Report (`outputhtml/`)

| File | Contenuto |
|------|-----------|
| `outputhtml/btp_220m_backtest.html` | Backtest BTP 220m |
| `outputhtml/btp_220m_stable_backtest.html` | Backtest BTP 220m stable |
| `outputhtml/btp_220m_trades_report.html` | Report trades BTP 220m |
| `outputhtml/btp_220m_optimization_results.html` | Ottimizzazione BTP 220m |
| `outputhtml/btp_ma_optimization_results.html` | Ottimizzazione ST+MA BTP |
| `outputhtml/btp3h_optimization_results.html` | Ottimizzazione BTP 3h |
| `outputhtml/btp3h_barre_segnali.html` | Barre 3h + segnali |
| `outputhtml/btp_footprint_test.html` | Footprint test |
| `outputhtml/bund_220m_optimization_report.html` | Ottimizzazione BUND 220m |
| `outputhtml/bund_220m_optimized_backtest.html` | Backtest BUND ottimizzato |
| `outputhtml/bund_220m_stable_backtest.html` | Backtest BUND stable |
| `outputhtml/dax_220m_optimization_report.html` | Ottimizzazione DAX 220m |
| `outputhtml/minidax_220m_optimization_report.html` | Ottimizzazione MiniDAX 220m |
| `outputhtml/stoxx_220m_optimization_report.html` | Ottimizzazione STOXX 220m |
| `outputhtml/portfolio_combined_backtest.html` | Portfolio combinato |
| `outputhtml/portfolio_combined_backtest_dax.html` | Portfolio combinato DAX |
| `outputhtml/portfolio_combined_4asset.html` | Portfolio 4 asset |

### CSV Risultati (`outputxls/`)

| File | Contenuto |
|------|-----------|
| `outputxls/btp_220m_optimization_results.csv` | BTP 220m |
| `outputxls/btp3h_optimization_results.csv` | BTP 3h |
| `outputxls/bund_220m_optimization_results.csv` | BUND 220m |
| `outputxls/dax_220m_optimization_results.csv` | DAX 220m |
| `outputxls/minidax_220m_optimization_results.csv` | MiniDAX 220m |
| `outputxls/stoxx_220m_optimization_results.csv` | STOXX 220m |
| `outputxls/supertrend_optimization_results.csv` | BTP daily |
| `outputxls/supertrend_ma_optimization_results.csv` | BTP daily + MA |

### Altro (`outputxls/`)

| File | Tipo |
|------|------|
| `outputxls/btp_trades_report.xlsx` | Excel trades |
| `Euro BTP Future.png` | Screenshot grafico |
| `outputxls/geminilavoro.xlsm` | Excel macro |
| `outputxls/geminilavoro_ordinato_dde.xlsm` | Excel macro DDE |

---

## Codici ProRealTime 10.3

| File | Descrizione |
|------|-------------|
| `prorealtime_supertrend_220m.md` | Due indicatori separati: Supertrend220m_Prezzo (su grafico) + Supertrend220m_Segnali (finestra sotto, istogramma) |
| `prorealtime_supertrend_3h.prt` | Indicatore 3h (bin: 8-11, 11-14, 14-17), ST(14,3.0) + SMA21 opzionale |

---

## Migliori Configurazioni Trovate

### BTP 220m — Top Result
- **ST(20, 3.0) TP=1.0** → 92.7% win, 55 trades, €17.662, ratio 7.65

### BTP 3h — Top Results
| Config | Win% | Trades | Profit | Ratio |
|--------|------|--------|--------|-------|
| ST(20,2.5) TP=2.0 | 67.6% | 68 | €21.348 | — |
| ST(20,2.5) TP=1.5 | 75.0% | 68 | €17.065 | 5.56 |
| ST(14,3.0) TP=1.0 | 90.0% | 60 | €15.015 | 6.13 |

### BTP Daily — Top Result
- ST(10, 3.0) TP=1.0 — miglior ratio

---

## Note Generali

- Dati tick BTP unificati: `dati/btp 2023-25.txt` (6.23M righe, ~190 MB)
- Costruzione barre intraday: ricostruzione da tick con bin orari fissi (no MAX/MIN nativi PRT)
- Supertrend implementato manualmente (ATR Wilder ricorsivo, bande finali con logica di persistenza)
- Filtro SMA 21 opzionale incluso (non cambia risultati su ST(14,3.0))
- ATR medio ~0.29 su 1h
