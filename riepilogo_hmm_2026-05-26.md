# Riepilogo Sessione 26 Maggio 2026 — Analisi HMM e Markov sul BTP Future

## Contesto
Abbiamo reimpostato da zero l'analisi quantitativa del BTP Future utilizzando le **10 Istruzioni Operative** (Definizione Adattiva, Etichettatura, Proprietà di Markov, Matrice di Transizione, Stickiness, Matrix Squaring, Distribuzione Stazionaria, Signal Generation, Walk Forward Backtesting, Conferma HMM).

L'analisi è stata eseguita su **due timeframe**: dati orari (1h) e dati giornalieri (Daily).

---

## 1. Script Creati in Questa Sessione

| Script | Descrizione |
|--------|-------------|
| `scripts/btp_hmm_1h_analysis.py` | Analisi completa 10 step su barre orarie (resample da tick a 1h) |
| `scripts/btp_hmm_daily_analysis.py` | Analisi completa 10 step su barre giornaliere (esclude automaticamente il giorno corrente se incompleto) |
| `scripts/btp_predict_today.py` | Script di previsione: esclude l'ultimo giorno per simulare la previsione "al buio" |

---

## 2. Risultati Chiave — Dati Orari (1h)

- **Barre totali**: 7.641 (sessione 08:00-19:00, dati tick 2023-2025)
- **Distribuzione regimi**: Sideways 73.4%, Bear 13.1%, Bull 12.9%
- **Stickiness Sideways**: 74.16%
- **Decadimento predittivo**: Collasso sulla distribuzione stazionaria in 2 ore
- **Walk Forward Hit Rate**: 47.75% (peggio di un lancio di moneta)
- **Semaforo HMM**: ROSSO (ultima barra)

### Conclusione 1h
A livello orario la matrice di transizione è quasi uniforme: qualunque stato tu sia, hai circa il 73% di probabilità di tornare Sideways. Il segnale direzionale è inesistente.

---

## 3. Risultati Chiave — Dati Giornalieri (Daily, aggiornati al 25/05/2026)

- **Barre totali**: 2.405 (dal 2017 ad oggi, esclusa barra incompleta del 26/05)
- **Distribuzione regimi**: Sideways 69.4%, Bull 15.6%, Bear 14.2%
- **Stickiness**: Sideways 71.04%, Bear 16.96%, Bull 13.90%
- **Decadimento predittivo**: Convergenza alla distribuzione stazionaria in 3 giorni
- **Walk Forward Hit Rate**: 50.62% (come un lancio di moneta)
- **Distribuzione Stazionaria**: Bear 14.35%, Sideways 69.92%, Bull 15.73%

### Matrice di Transizione Giornaliera (al 25/05/2026)
```
To          Bear  Sideways    Bull
From                              
Bear      0.1696    0.6754  0.1550
Sideways  0.1277    0.7104  0.1619
Bull      0.1898    0.6711  0.1390
```

### Insight dalla Matrice
- **Da Bull**: Solo il 13.90% di persistenza. Il 67.11% rientra in Sideways, il 18.98% inverte in Bear.
- **Da Bear**: 16.96% di persistenza. Il 67.54% rientra in Sideways, il 15.50% inverte in Bull.
- **Da Sideways**: 71.04% resta laterale. Lievissima asimmetria rialzista (16.19% Bull vs 12.77% Bear).

---

## 4. Previsione per Oggi (26/05/2026) — Generata al Buio da Dati fino al 25/05

- **Ultimo Prezzo Noto**: 118.83 (chiusura 25/05/2026)
- **Stato Deterministico al 25/05**: **Bull** (forte rialzo settimanale, +2.6 punti)
- **Stato HMM al 25/05**: **Sideways**
- **Semaforo HMM**: **ROSSO** (discordanza)
- **Segnale per il 26/05**: **SHORT**, Forza 5.08%
  - Probabilità Bear: 18.98%
  - Probabilità Sideways: 67.11%
  - Probabilità Bull: 13.90%
- **Interpretazione**: Dopo una giornata Bull, il BTP nel 67% dei casi rientra in laterale e nel 19% inverte al ribasso. Solo nel 14% continua a salire.

---

## 5. Conclusioni Generali dello Studio

### A. Il BTP è strutturalmente laterale
Il mercato si trova in regime Sideways per circa il 70% del tempo su base giornaliera. Le fasi di trend (Bull/Bear) sono eccezioni che durano tipicamente 1-2 giorni prima di essere riassorbite.

### B. Forte Mean Reversion
Sia dallo stato Bull che dallo stato Bear, la probabilità dominante è il rientro in Sideways il giorno successivo (67-68%). La persistenza dei trend è bassissima (14-17%).

### C. L'informazione predittiva scade in 3 giorni
Dopo 3 giorni le probabilità convergono sulla distribuzione stazionaria. Conoscere lo stato di oggi non dà alcun vantaggio per previsioni oltre i 3 giorni.

### D. Il trading direzionale puro su Markov non funziona
Hit Rate del backtest walk-forward: ~50% (casuale). Tentare scommesse Long/Short basandosi sulle sole probabilità di transizione non genera edge.

### E. L'edge reale è la vendita di volatilità
L'inerzia laterale del BTP è ideale per strategie di vendita di premi (Short Strangle / Iron Condor) con scadenze a ~20 giorni, posizionando gli strike sulle code empiriche (90-95° percentile).

### F. Il Semaforo HMM è un indicatore di regime-shift
Quando il Semaforo è VERDE (concordanza), il mercato è in una fase stabile e classificabile. Quando è ROSSO (discordanza), il mercato sta vivendo una transizione o un cambio di personalità. In quel caso: cautela e nessuna nuova posizione aggressiva.

---

## 6. Estensione Settimanale (26/05/2026) — Analisi su base W-FRI

Abbiamo esteso l'analisi a barre **settimanali** (W-FRI, min 3 giorni per barra completa), dato che la daily mostrava hit rate casuale (50.62%).

### Script Creati
| Script | Descrizione |
|--------|-------------|
| `scripts/btp_hmm_weekly_analysis.py` | Analisi completa 10 step su barre settimanali |
| `scripts/btp_predict_week.py` | Previsione settimanale corrente |
| `scripts/btp_highconf_options.py` | Ricerca filtri ottimali + backtest opzioni filtrato vs sempre aperto |
| `scripts/btp_weekly_stats.py` | Walk-forward 1-settimana su 465 settimane (2017-2026) |
| `scripts/btp_weekly_excursion.py` | Distribuzione escursione di prezzo reale condizionata ai filtri |

### Matrice di Transizione Settimanale
```
To          Bear  Sideways    Bull
From
Bear      0.2877    0.4932  0.2192
Sideways  0.1327    0.7407  0.1265
Bull      0.1159    0.7101  0.1739
```

### Stickiness Settimanale
- Bear: **28.77%** (vs 16.96% daily — orso più persistente su weekly)
- Sideways: 74.07%
- Bull: 17.39% (debole come daily)

### Hit Rate Walk-Forward (465 settimane)
- **Predizione stato Markov**: 69.03% (ma predice sempre Sideways, lo stato dominante)
- **Direzionale Long/Short**: 48.39% (conferma: inutilizzabile)

### Filtri per Vendita Opzioni ad Alta Confidenza

L'analisi chiave: non predire lo stato, ma l'**escursione massima di prezzo condizionata ai filtri**.

| Filtro | N | Max95 | Max99 | Range90 |
|--------|:-:|:----:|:-----:|:-------:|
| **SW+Consec3+Vol<25%** | 43 | ±1.31% | **±1.56%** | 2.45% |
| **SW+Consec3+Vol<15%** | 34 | ±1.24% | **±1.49%** | 2.29% |
| SW+Vol<15% | 68 | ±1.61% | ±3.86% | 2.67% |
| Solo Sideways | 324 | ±3.45% | ±4.32% | 5.01% |

**Con `SW+Consec3+Vol<25%`**:
- 95%: max movimento settimanale < ±1.31%
- 99%: max movimento settimanale < ±1.56%
- Short Strangle a ±2.0%: >99.5% confidenza
- Attivazione: ~9% del tempo (1 trade ogni ~3 mesi)

### Backtest Opzioni: Sempre Aperto vs Filtrato (SW+HMM+Consec3)
| Metrica | Sempre Aperto | Filtrato | Delta |
|---------|:------------:|:--------:|:-----:|
| Win Rate | 78.00% | **92.77%** | +14.78% |
| Call Breach | 12.22% | 3.61% | -8.61% |
| Put Breach | 10.27% | 3.61% | -6.65% |
| Trades | 409 | 83 | -326 |

### Segnale Corrente (Settimana 26-30 Maggio 2026)
- **Stato**: Sideways (Markov) + Sideways (HMM) = **Semaforo VERDE**
- **Consecutive SW**: 1 (serve 3+)
- **Vol percentile**: 63.2% (serve <25%)
- **Verdetto**: NO TRADE (1/4 filtri, confidenza troppo bassa per vendere opzioni)

---

## 7. Conclusioni Finali dello Studio

### A. Il BTP è strutturalmente laterale su ogni timeframe
70% Sideways su daily, weekly, e convergenza stazionaria identica (~70%).

### B. La persistenza Bear migliora su weekly (28.77% vs 16.96%)
Trend ribassisti settimanali sono più "reali" di quelli giornalieri. I rialzi restano fugaci anche su weekly (17.39%).

### C. Predizione direzionale impossibile
Hit rate 48-51% su ogni timeframe. Nessun edge long/short.

### D. Vendita opzioni: l'unica strategia sensata
Con filtri stringenti (SW+Consec3+Vol<25%) si raggiunge >99.5% confidenza che il prezzo resti entro ±2% nella settimana successiva. Il trade-off è la frequenza: ~1 segnale ogni 3 mesi.

### E. Regime-shift = pericolo
Semaforo HMM ROSSO indica transizione: in quei periodi non vendere opzioni.

---

## 8. Prossimi Passi (da riprendere)

- [ ] Verificare cosa ha fatto il BTP il 26/05 e confrontare con la previsione Short al 5.08%
- [x] Integrare il calcolatore strike opzioni con segnale HMM/Markov (fatto: `btp_highconf_options.py`)
- [ ] Automatizzare controllo settimanale (cron job ogni venerdì)
- [ ] Testare su BUND, DAX, STOXX (dati già disponibili)
- [ ] Provare volatilità a 10/30/50 settimane invece di 20
- [ ] Aggiungere feature HMM: volatilità + rendimenti invece di soli rendimenti
