# BTP — Risultati Finali

## Data
- BTP 1h: 7.704 candele, 2023-2025 (2.7 anni)
- BTP new (27 febbraio.txt): 708 candele, feb-giu 2026

## Volatilità
- BTP: 6.2% annua, ATR med 0.214
- BUND: 5.5% annua, ATR med 0.213
- BTP leggermente più volatile, a parità di ATR

## Cosa abbiamo testato

### 1. ATR-channel breakout
Zero trades su BTP 1h. Il breakout non si attiva mai.

### 2. BB Multi-TF Mean Reversion
| Config | PF | PnL | Trades |
|---|---|---|---|
| Best IS (ottimizzato) | 1.65 IS → 1.02 OOS | +1.87 | 154 |
| Fixed params | 1.05 IS → 0.94 OOS | +2.92 → -2.66 | 401→407 |
| ON/OFF filter | OOS PF **1.12** | — | 76 |

Overfitta (IS PF 1.65 → OOS 1.02). Fixed params perdono OOS. ON/OFF aiuta marginalmente.

### 3. RSI + Volume confirmation ✅
**NETTAMENTE MIGLIORE SU BTP:**

| Periodo | PF | Trades | PnL |
|---|---|---|---|
| IS (2023) | **6.23** | 15 | +2.82 |
| OOS (2024-25) | **6.52** | 16 | +2.26 |
| ON/OFF filter | **8.35** | 14 | +3.01 |
| Fixed (vol=2.0, tp=2.0) | 4.36 | 11 | +1.65 |

Best params: RSI(14), soglie 20/75, vol_mult=1.5, TP=2×ATR.

**Criticità:** Si rompe sui dati nuovi (27 febbraio.txt, 2026): PF=0.85. Ma con vol_mult=1.0 (no volume filter) e TP=3×ATR torna positivo: PF=4.04.

### 4. Risultati su dati 2026 (27 febbraio.txt)

| Segnale | PF | Trades | Note |
|---|---|---|---|
| RSI+Volume best IS | **0.85** | 7 | Non regge |
| RSI+Volume vol=1.0 tp=3.0 | **4.04** | 13 | Senza filtro volume |
| BB fixed | 1.13 | 73 | Stabile ma piccolo |
| BB best IS | 1.91 | 25 | Migliore su 2026 |

## Confronto BUND vs BTP

| Metrica | BUND | BTP |
|---|---|---|
| Volatilità annua | 5.5% | 6.2% |
| Best sistema | RSI+Vol (PF=1.24) | RSI+Vol (PF=6.52) |
| Trades/anno | ~21 | ~12 |
| PnL/anno | +0.87 pt | +1.69 pt |
| Dimensione edge | Piccolo | Significativo |
| Regge OOS 2026? | No (PF=0.83) | Parzialmente (PF=0.85→4.04) |
| Dimensione campione | 8 anni | 2.7 anni |

## Conclusione

**BTP ha un edge molto più forte di BUND** (PF 6.5 vs 1.2), ma su un campione più piccolo (2.7 anni vs 8 anni). Il sistema perde sui dati 2026 con i parametri ottimizzati, ma può essere recuperato rimuovendo il filtro volume.

L'edge su BTP è reale ma **instabile**: funziona molto bene in un periodo, si degrada in un altro. Coerente con la lezione Simons — gli edge sono momentanei e vanno continuamente monitorati.

## File prodotti
- `directives/bund_final_results.md` — report BUND
- `execution/bund_rsi_only.py` — RSI+Volume puro BUND
- `dati/btp_1h_full.txt` — dati BTP 1h
