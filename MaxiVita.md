# Strategia DAX SuperTrend - Documento di Lavoro

> **Stato**: analisi preliminare completata. Strategia promettente ma con rischi strutturali.
> **Data ultimo aggiornamento**: 04/06/2026

---

## 1. Logica della strategia

- **Indicatore**: SuperTrend(10, 3.0)
  - Periodo ATR: 10 barre da 3 minuti
  - Moltiplicatore bande: 3.0
  - Calcolato su dati continui 24h (incluso overnight futures)
- **Time filter**: solo ingressi nelle finestre 9:00-11:00 e 15:30-17:30
- **Reversal logic**:
  - Al close della barra: se close > ST → LONG; se close < ST → SHORT
  - Esecuzione all'open della barra successiva (i+1)
  - In fascia oraria: reversal = chiudi posizione + apri opposta
  - Fuori fascia: reversal = chiudi posizione, niente nuova apertura
- **Exit**: solo su reversal SuperTrend (no stop loss, no take profit nella versione baseline)
- **Costi**: 3 EUR/giro (verificato con broker)
- **Punto valore DAX**: 25 EUR

---

## 2. Dati utilizzati

- **File principale**: `dati/dax_m1.txt` (1.128.996 barre 1min, Gen 2023 → Mag 2026)
- **File correttivo**: `dati/3 minuti da rettificare.txt` (3.863 barre 3min, Mag 20 → Giu 03 2026, 24h)
- **Resample**: 1min → 3min via OHLCV aggregation
- **Dataset finale**: 387.942 barre 3min, continuo 24h, 02/01/2023 → 03/06/2026

**Nota**: il file "3 minuti da rettificare" contiene barre per le ore non coperte dal file 1min (essenziale per calcolare l'ATR su tutto l'arco temporale).

---

## 3. Bug risolti durante lo sviluppo

| # | Bug | Impatto | Fix |
|---|-----|---------|-----|
| 1 | ST reversal condition sbagliata: `c[i]<=fub[i]` invece di `c[i]<=fl[i]` (e viceversa) | Generava 80 trade/giorno (reversal ogni barra) | Corretta condizione reversal su banda corretta |
| 2 | Time check sul bar sbagliato: usava `in_fascia(bar i)` invece di `in_fascia(bar i+1)` | Apriva posizioni al bordo delle finestre | Time check spostato sul bar di esecuzione |
| 3 | Exit/entry sullo stesso bar (look-ahead bias) | PF gonfiato a 2.06 | Exit e entry entrambi su open del bar i+1 |
| 4 | File "3 minuti da rettificare" interpretato come sospetto | Dubbi su integrità dati | Verificato: serve per copertura 24h |

---

## 4. Risultati baseline (no filtri)

| Metrica | Valore |
|---------|-------:|
| Periodo | 02/01/2023 → 02/06/2026 (3.4 anni) |
| Trade totali | 2.198 |
| Win rate | 40.2% |
| P&L totale | **+88.828 EUR** |
| P&L medio/anno | +26.018 EUR |
| Profit Factor | 1.073 |
| Avg trade | +1.6 pt |
| Avg winner | +58.8 pt |
| Avg loser | -36.9 pt |
| Payoff ratio | 1.60 |
| Max win singolo | +857 pt |
| Max loss singolo | -305 pt |
| Max consecutive wins | 8 |
| Max consecutive losses | 15 |
| **Max drawdown** | **-48.633 EUR** |
| Max DD duration | 611 giorni |
| Recovery factor | 1.83 |
| Sharpe ratio (ann.) | 0.58 |
| Sortino ratio (ann.) | 1.38 |
| Calmar ratio | 0.53 |
| LONG / SHORT WR | 43% / 37% |
| Avg holding | 40 barre (2 ore) |
| Time in market | 23.2% |
| Commissioni totali | 6.594 EUR |

---

## 5. Analisi avvocato del diavolo (sintesi)

### 5.1 Punti accettati come limiti noti
- Slippage non modellato
- No OOS / walk-forward
- No filtri su news/eventi
- Tenuta weekend/gap overnight
- ATR include gap overnight (rumore)
- Niente selezione robusta dei parametri (10/3.0 tondo)

### 5.2 Conclusioni
- PF 1.073 è buono ma nella coda della distribuzione pubblicata
- Max DD -48K EUR è **insostenibile** per un conto reale (2 anni di profitti medi in un singolo DD)
- Strategia media pochi trade/giorno ma con elevata varianza

---

## 6. Analisi dei losing trades

Su 1.314 losing trades (59.8% del totale):
- **97.3% sono passati in territorio positivo** durante la loro vita
- MFE mediano: +19 pt
- MFE medio: +24.9 pt
- MAE mediano: -29.5 pt
- MAE medio: -34 pt

**Breakpoint chiave**: l'80% dei losing ha MFE ≤ 38.6 pt, MAE ≥ 48 pt.

**Significato**: la strategia entra nella direzione giusta ma esce troppo tardi — vede il movimento ma non lo cavalca fino in fondo.

---

## 7. Test mitigazioni

### 7.1 Stop Loss / Take Profit — INSUFFICIENTE

| TP/SL migliore | PnL | Max DD | Calmar |
|---|---:|---:|---:|
| Baseline | +88.828 | -48.633 | 0.54 |
| TP+50 / SL-75 | +56.954 | -42.744 | 0.39 |
| TP+40 / SL-75 | +55.559 | -52.233 | 0.31 |

**Conclusione**: nessuna combinazione TP/SL batte il baseline. Lo SL hard interrompe trade che il reversal ST avrebbe recuperato.

### 7.2 Filtro Media Mobile — RISULTATI POSITIVI

Filtro: LONG solo se close > MA, SHORT solo se close < MA (skip contro-trend).

| Periodo MA | N | PnL EUR | PF | Max DD EUR | Calmar | Note |
|-----------:|--:|--------:|----|-----------:|-------:|------|
| Baseline | 2.198 | +88.828 | 1.073 | -48.633 | 0.54 | — |
| MA 20 | 2.166 | +92.534 | 1.078 | -47.054 | 0.58 | Modesto miglioramento |
| **MA 50** | 1.718 | **+103.194** | **1.109** | -51.454 | 0.59 | +16% PnL |
| **MA 100** | **1.346** | **+110.222** | **1.151** | -43.157 | **0.75** | **Best risk-adjusted** |
| **MA 200** | 1.216 | +88.480 | 1.136 | **-34.351** | **0.76** | **DD minimo** |
| MA 300 | 1.195 | +71.833 | 1.111 | -42.929 | 0.49 | Troppo pochi trade |

**Configurazione consigliata**:
- **MA 100** se si vuole massimizzare il PnL (+24% vs baseline) mantenendo DD simile
- **MA 200** se si vuole il minimo rischio assoluto (DD -34K vs -48K) con PnL invariato

### 7.3 Filtro MA slope — INUTILE
Lo slope su 5 barre (15 min) è troppo rumoroso. Nessun vantaggio.

### 7.4 Combinato MA + slope — TROPPO RESTRITTIVO
Genera 0-4 trade totali. Inutilizzabile.

---

## 8. Conclusioni

### 8.1 Cosa funziona
- La logica SuperTrend su DAX 3min con filtri orari ha un edge reale (PF > 1.05, Calmar > 0.5)
- Il **filtro MA 100-200** migliora significativamente il rapporto rischio/rendimento
- LONG performa meglio di SHORT (43% vs 37% WR)

### 8.2 Cosa non funziona
- Qualsiasi combinazione TP/SL hard peggiora la strategia
- Lo SL tradizionale è controproducente con la logica trend-following
- Il DD baseline (-48K EUR) è troppo alto per uso realistico

### 8.3 Prossimi passi da valutare
1. **Validazione out-of-sample** della configurazione MA 100/200 su dati 2010-2022
2. **Walk-forward analysis** per stabilità dei parametri
3. **Test su altre asset class** (NASDAQ, EUR/USD, oro) per generalizzabilità
4. **Backtest intraday con dati tick** per misurare slippage reale
5. **Position sizing dinamico** (ridurre size dopo N loss consecutivi)

---

## 9. File del progetto

| File | Scopo |
|------|-------|
| `listati/backtest_completo.py` | Backtest base su 24h, 3 moltiplicatori |
| `listati/report_metrics.py` | Calcolo tutte le metriche professionali |
| `listati/build_report.py` | Genera report HTML |
| `listati/test_tp_sl.py` | Test combinazioni TP/SL |
| `listati/test_ma_filter.py` | Test filtro media mobile |
| `listati/analisi_losers.py` | MFE/MAE dei losing trades |
| `listati/grafico_10_giorni.py` | Grafico ultimi 10 giorni |
| `reports/resoconto_supertrend.html` | Report HTML professionale |
| `reports/grafico_10_giorni.html` | Grafico candles+ST+volume |

---

## 10. Decisioni aperte

1. La strategia in questa forma è utilizzabile per live trading? **NO** — DD inaccettabile senza OOS
2. Ha senso investire tempo in walk-forward? **SÌ** — se MA 100/200 conferma, è un candidato serio
3. Il filtro MA è robusto o overfittato su questo periodo? **DA VERIFICARE** con OOS
4. Il backtest è affidabile o c'è ancora qualche bias nascosto? **PROBABILE** (slippage, news, gap)

**Prossima azione consigliata**: out-of-sample test su dati 2018-2022 della configurazione MA 100.
