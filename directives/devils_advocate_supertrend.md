# Devil's Advocate — SuperTrend DAX 3min

## Il sistema non funziona. Il backtest buggato mentiva.

### Il bug trovato: 1 barra di look-ahead nell'esecuzione

Nel codice originale, a barra `i`:
```python
t = df["trend"].iloc[i]        # trend[i] usa close[i] — noto a fine barra
if t != pos:
    xp = df["open"].iloc[i]    # esegue a open[i] — CHE E' PRIMA di close[i]!
```

Il segnale era calcolato al close[i] ma eseguito all'open[i] (che avviene 3 minuti prima). In un trend, questo regalava 3 minuti di vantaggio per ogni trade — sufficiente a far sembrare il sistema miracoloso.

### Confronto prima/dopo la correzione

| Metrica | PRIMA (bug) | DOPO (corretto) |
|---------|:----------:|:--------------:|
| Miglior sistema | ST(10,2.0) | Nessuno |
| PF totale | 1.45 (+623k) | 0.98 (-22k) |
| Min PF su 4 periodi | 1.23 (tutti >1!) | 0.63-0.78 (tutti <1!) |
| Sensibilità slippage | Bassa (PF 1.40 a 3t) | Non rilevante |

Dopo la correzione, **NESSUN sistema ST(period, multiplier) ha PF>1 su TUTTI i 4 periodi cronologici.** I migliori:
- ST(10,3.5): IS 1.40, OOS 1.25, FWD 0.78, Blind 0.80
- ST(14,3.5): IS 1.45, OOS 1.33, FWD 0.76, Blind 0.88

Tutti perdono su FWD 2025 e Blind 2026.

---

### Perché sembrava funzionare

1. **Il timing bug era enorme**: ogni trade guadagnava 3 minuti gratis. In una sessione di 8.5 ore = 170 barre 3min. Con ~400 trade/anno e trend rialzista DAX 14k->25.5k, quei 3 minuti di vantaggio cumulati facevano +623k fittizi.

2. **Il DAX in bull run puro**: da 13.979 a 25.508 = +82% in 3.3 anni. Un sistema trend-following sembra geniale in un mercato che sale senza fermarsi. Ma appena arriva un periodo laterale (2025, 2026), muore.

3. **Commissioni e slippage già realistici**: non era quello il problema. 3€/side e 1 tick sono già realistici. Il problema era il timing.

---

### Lezioni imparate

1. **Prima di guardare i risultati, cerca i bug**. Il mio primo output diceva "ST(10,2.0) PF=1.45". Sembrava fantastico. Era falso.
2. **Il timing di esecuzione è la fonte #1 di look-ahead**. Segnale a close[i] → esecuzione a open[i+1], sempre.
3. **Bull market nasconde tutto**. Anche con un bug, faceva soldi. Senza bug, è break-even.
4. **La sensitività allo slippage era l'unica cosa vera**: bassa, perché il sistema non aveva mai avuto un edge reale da cui scivolare via.

---

### Raccomandazione finale

**Non usare SuperTrend su DAX 3min.** Dopo costi reali e timing corretto, non ha edge.

Alternative da esplorare:
- SuperTrend su timeframe più alto (30min, 1h) per ridurre i falsi segnali
- Combinare ST con filtro di regime (volatility, trend strength)
- Usare ST solo per lo stop loss, non per l'entry (es. entry su rottura canale + ST come trailing)
- Provare su altri mercati (Bund, BTP) con timeframe più alto

---

### File aggiornati

- `supertrend_dax.py` — versione corretta (nessun look-ahead)
- `risultati_supertrend_dax.txt` — risultati definitivi
- `supertrend_dax_report.html` — **DA RIFARE** (i numeri erano basati sul bug)
