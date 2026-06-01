# Devil's Advocate — 5 Demolizioni della Strategia BTP ST(30,1.5)+Pivot

---

## 1. Il Matematico Spietato — "Non hai statisticamente un cazzo di edge"

### Parameter overfitting
Hai fatto grid search su ST period×mult×TP strategy su 2.7 anni. Su 375 combinazioni, hai scelto la migliore. La probabilità che sia un artefatto è altissima. Il walk-forward l'hai passato? Sì. Ma il walk-forward non protegge dal data snooping quando la grid è abbastanza grande.

**Prova**: Prendi ST(28, 1.4) o ST(32, 1.6) e vedi se tengono. Spoiler: degradano. Sei finito in un minimo locale.

### Il win rate 88% è un campanello d'allarme
Nessuna strategia sistematica su future mantiene 88% win rate su 559 trade senza avere loss enormi. È la signature di un sistema che vince micro-piccole vincite e perde raramente ma grosso. Il problema: **la distribuzione dei PnL non è normale**. Quando arriva la loss grossa (e arriverà), può cancellare 20 win di fila.

Backtest: avg win +541€, avg loss -626€. Il rapporto è quasi 1:1. Con 88% win rate, PF=3.78 è matematicamente sospetto. Calcoliamo: PF = (0.88 × 541) / (0.12 × 626) = 476 / 75 = 6.34. Ma il tuo PF è 3.78. **I conti non tornano** — significa che le win sono più piccole e le loss più grandi di quanto mostrato, oppure c'è un errore di arrotondamento.

### Sharpe 10.17
Uno Sharpe > 3 su strumenti finanziari reali è già bandiera rossa. > 5 è impossibile. > 10 è **pura spazzatura** o errore di calcolo. Lo Sharpe ratio usa la deviazione standard dei rendimenti periodici. Se calcolato su rendimenti giornalieri di una strategia che fa 1 trade ogni 2 giorni, il denominatore è piccolo e lo Sharpe esplode. Non è un indicatore valido qui.

### Sensitivity test mancante
Prova a spostare l'entry di 1 candle. Prova a slippare l'execution di 0.05 pt. Prova a ritardare il pivot di 1 barra. Se la strategia collassa per 0.05 pt di slippage, **non esiste in realta'**.

---

## 2. Il Trader Reale — "In live perdi il 50% del tuo PnL, e non lo sai"

### Slippage e spread
Hai usato costi fissi 6€/trade. Su un future BTP:
- Spread bid/ask medio: 0.02-0.05 pt
- Slippage su entry: facile 0.03 pt (30€)
- Slippage su exit: altri 0.03 pt (30€)
- Totale invisibile: **60-100€/trade**, non 6€

Il tuo PnL netto reale è 181k - 52k = **129k**, non 181k. PF reale scende a ~2.5.

### L'entry è all'open dopo il flip — ma a che prezzo?
La strategia dice: "flip rilevato alla chiusura, entry all'open successivo". Ma l'open di una candela 1h non è un prezzo eseguibile. Su BTP Future:
- L'open è un prezzo di riferimento, non necessariamente il primo eseguito
- Se c'è gap tra close e open (e c'è: il 28/05 high 118.89, open 118.63 = gap di -0.26 pt)
- **Hai slippato sistematicamente 0.1-0.2 pt a favore o contro?**

Il codice testa entry = open[i]. Non è realistico. Devi testare entry = close[i] + slippage, oppure usare il prezzo medio della candela.

### Le candele 1h sono discontinue
BTP Future non scambia 24h. La sessione apre 8:00 e chiude 19:00 (o 17:30?). Le candele 18:00 e 08:00 hanno un gap di **15 ore**. In quel gap il mercato può muoversi di 0.5 pt. Il backtest ignora completamente il rischio overnight/gap. Il tuo SL posizionato a 117.91 non vale nulla se il mercato apre a 117.50.

### Ordini limite vs mercato
Il backtest assume che SL e TP vengano eseguiti esattamente al prezzo target. In realtà:
- SL diventa un ordine market quando viene toccato
- In un mercato veloce, lo slippage sullo stop è sistematico
- Il TP è un ordine limite: potrebbe **non essere riempito** se il prezzo torna indietro

---

## 3. Lo Scettico degli Assunti — "Il tuo backtest mentisce, ed ecco come"

### Look-ahead bias #1: Il previous pivot non è confermato all'entry
Lo script calcola i pivot su tutto il dataset. Poi assegna ph_prev[i] = ultimo pivot alto TROVATO. Ma un pivot è definito come "high più alto delle 5 candele prima e delle 5 candele dopo".

**Il problema**: alla candle i, quando entri, le 5 candele successive NON ESISTONO ancora. Non sai se quel high è veramente un pivot fino a 5 ore dopo. Il backtest lo dà per noto.

**Impatto**: stai usando SL basati su livelli che in live non sai se sono validi. Alcuni SL sono più stretti di quanto dovrebbero, altri più larghi. In entrambi i casi, il backtest è più ottimistico della realtà.

### Look-ahead bias #2: Il next_pivot è pura fantascienza
Il TP è "prossimo pivot dopo l'entry". Ma un pivot future **non esiste** all'entry. Il TP nel backtest è determinato ex-post. È come sapere dove finirà il prezzo e posizionare il target lì.

Il trailing strutturale è una scusa elegante, ma nella simulazione il TP è già noto al momento dell'entry. In live, non lo sai e non puoi piazzare un ordine a un prezzo che non conosci ancora.

**Domanda**: come replichi esattamente il TP in live? Con un ordine OCO? A che prezzo? Non puoi mettere un ordine a un prezzo che non esiste ancora.

### Gli ordini OCO non sono modellati
Il backtest usa un semplice "se low <= SL → stop". Non simula:
- Se SL e TP sono nella stessa candela, quale viene eseguito per primo? (minute data needed)
- Lo slippage simultaneo su due livelli
- La cancellazione dell'ordine non eseguito

### Il pivot ha un confirmation lag di 5 barre
Anche supponendo di risolvere il look-ahead, il pivot è confermato solo 5 barre dopo che si è formato. Quindi:
- Il tuo SL basato su "ultimo pivot confermato" è in realtà basato su un pivot di 5-10 barre fa
- Non usi il massimo/minimo recente per SL
- Stai usando un livello vecchio di 5 ore, che potrebbe essere molto distante

### Test su 3 mesi non significa nulla
Il test su "27 febbraio" copre 3 mesi. Con 52 segnali. La deviazione standard del win rate su 52 trade è sqrt(0.88*0.12/52) = 4.5%. Quindi il vero win rate è 88% ± 9%. Potrebbe essere 79%. O 97%. **Non hai abbastanza campioni** per trarre conclusioni.

---

## 4. Il Risk Manager Paranoico — "Quando arriva la coda, perdi tutto"

### Regime change = morte della strategia
L'analisi HMM che hai fatto tu stesso mostra:
- 70% del tempo: Sideways
- Il BTP è strutturalmente laterale

La strategia funziona in laterale. Ma cosa succede quando arriva un regime di trend?

**Caso BCE taglia i tassi**: BTP vola, ST(30,1.5) è lentissimo a flipare, il pivot trailing perde la maggior parte del movimento. Perdi opportunità enormi. Ma peggio:

**Caso BTP crash**: Un gap down di 2 pt (succede, vedi COVID 2020). Il tuo SL a 117.91 viene bucato in apertura. Esegui a 116.50. Loss: 118.63 - 116.50 = **2.13 pt = 2.130€** su un singolo trade. Più di tutto il drawdown storico (2.036€). **Il tuo max drawdown storico viene cancellato in un trade**.

### Correlazione nascosta
Tutti i trade LONG e SHORT sono sullo stesso strumento, stesso timeframe. Non c'è diversificazione. La correlazione seriale tra trade è positiva: un drawdown di 3 loss consecutivi è probabile (0.12^3 = 0.17% → 1 volta ogni 600 trade, ma ne hai solo 559).

### Non c'è un piano per la coda
- Qual è la loss massima accettabile? 5.000€? 10.000€?
- Quando smetti di tradare? Dopo 3 loss consecutivi?
- Cosa fai se il PnL scende del 20%? 50%?
- Non c'è un kill switch, non c'è un circuit breaker

### Monte Carlo ti dà ragione, ma...
Hai fatto Monte Carlo. Ma:
- Il Monte Carlo assume che i trade siano indipendenti e identicamente distribuiti (i.i.d.)
- I trade BTP NON sono indipendenti (serial correlation, volatility clustering)
- Il Monte Carlo sottostima la probabilità di drawdown prolungati
- **Il vero VaR 99% è probabilmente il doppio** di quello calcolato

### 1 contratto su 50k è corretto?
Rischio medio per trade: ~400€. Su 50k = 0.8%. Ok. Ma con 88% win rate, la probabilità di 4 loss consecutivi (~1.6%) significa:
- Perdita: 4 × 626€ = 2.500€ (5% del capitale)
- Il recupero richiede 23 trade vincenti (2.500/541 × 0.88/0.12 correction)

Sei in un regime dove il recupero è molto più lento della perdita.

---

## 5. Il Cynic degli Exit — "La tua exit logic è un colabrodo, e il TP non esiste"

### "Trailing strutturale" = "Non so dove esco"
Il TP basato su "next pivot" è una variabile aleatoria:
- Può essere 0.01 pt sopra l'entry (trade #24: TP=117.80, entry=117.79)
- Può essere 2.57 pt sopra (trade #14: entry=115.18, TP=117.75)
- Non c'è consistenza. È un trailing che non traila — aspetta un pivot.

In pratica:
- Se il prezzo va nella tua direzione MA non forma un nuovo pivot (movimento lento), resti in trade per 20+ barre
- Se il prezzo forma un pivot rapidamente, esci subito con un micro-profitto
- **È esattamente l'opposto di ciò che vuoi**: tagli le win corte e lasci correre le win lunghe? No, è il contrario: win lunghe che danno molto PnL sono rare, win corte sono frequenti

### Lo SL è basato su un pivot che non si muove
Mentre il prezzo si muove, il tuo SL rimane fisso sull'ultimo pivot che è rimasto indietro. La maggior parte delle strategie di trend-following usa uno SL trailing (parabolico, ATR trailing, chandelier exit). Tu no.

Il risultato: trade #21/04 LONG 118.36 → SL 117.68 = −0.68 pt. Se lo SL fosse stato trailing, saresti uscito molto prima.

### Il fix TP è un hack pericoloso
```python
if dir_label == "LONG" and tp <= entry:
    tp = round(entry + abs(entry - sl), 2)
```

Quando non c'è un next_pivot (perché il prezzo sta scendendo), il TP viene fissato a entry ± risk. Ma è un 1:1 fisso. In 3 mesi hai avuto 52 segnali e la maggior parte ha TP = next_pivot reale. Ma quelli con TP "fake" potrebbero essere sistematicamente sbagliati.

### Il problema del gap overnight
Tra le 18:00 e le 08:00 passano 14 ore. In quel lasso:
- Il Bund si muove
- I future US si muovono
- Possono uscire notizie macro
- Il BTP può aprire 0.5-1 pt fuori dal tuo SL/TP

Il backtest tratta la candela 08:00 come se fosse normale, ma è una candela con gap. Il prezzo low/high non è continuo rispetto alla candela precedente. Stai sovrastimando la protezione dello SL.

### Non c'è gestione del tempo
Se un trade è aperto da 30 barre (30 ore = 4 sessioni di trading), non c'è una regola per chiuderlo. In un mercato laterale, il prezzo può oscillare senza mai toccare SL/TP per 50 barre. Il tuo capitale è bloccato, e l'opportunity cost non è modellato.

---

## Sintesi Finale — I 10 Punti Deboli Veri

| # | Punto Debole | Gravità | Impatto stimato su PnL reale |
|---|-------------|---------|------------------------------|
| 1 | **Look-ahead sui pivot**: SL e TP usano livelli NON noti all'entry | **CRITICO** | −30/50% del PnL |
| 2 | **TP = next_pivot è irreplicabile in live**: non sai dove mettere l'ordine | **CRITICO** | −50/70% del PnL senza trailing alternativo |
| 3 | **Slippage/spread non modellati**: costi reali 10× superiori a 6€ | **ALTO** | −25/40% del PnL |
| 4 | **Gap overnight ignorato**: 14h di buco con rischio gap | **ALTO** | −10/30% del PnL in regime volatile |
| 5 | **Parameter overfitting**: ST(30,1.5) su misura per questi dati | **ALTO** | degradazione su OOS vero |
| 6 | **No exit management**: trade aperti all'infinito, nessun time stop | **MEDIO** | −5/15% |
| 7 | **No regime filter**: strategia morta in trend forte | **MEDIO** | −50% del PnL in regime bear/bull prolungato |
| 8 | **Distribuzione PnL asimmetrica**: vince spesso, perde poco ma male | **MEDIO** | drawdown 2× lo storico atteso |
| 9 | **Campionamento insufficiente**: 52 trade in OOS non bastano | **MEDIO** | errore statistico ±9% sul win rate |
| 10 | **Nessun kill switch**: nessuna regola di stop trading | **BASSO** | perdita totale del capitale in scenario estremo |

### Verdetto finale

> **La strategia non è truffaldina, ma il backtest mente per eccesso del 30-50%.** I due problemi veri sono:
> 1. Il **look-ahead nei pivot** — risolvibile con SL trailing deterministico (es. ATR trailing, chandelier exit)
> 2. Il **TP next_pivot** — in live non sai dove piazzarlo. Serve un exit dinamico implementabile (trailing stop, parabolico, o time exit)
>
> Senza risolvere questi due, il sistema in live farà **30-50% meno PnL** del backtest. Ed è ottimistico.

---

## Configurazione Finale Salvata (Giugno 2026)

Dopo aver eliminato ogni look-ahead, la miglior config trovata è:

### Regime-Adaptive TP (raccomandata)
```
Entry:  ST(30, 1.5) flip -> open successivo
SL:     Ultimo pivot CONFERMATO (j <= i-5) +/- 0.5*ATR
TP:     entry +/- ATR * K, dove K dipende dal regime di volatilita:
        - ATR percentile < 30% (bassa vol):  K = 2.0
        - ATR percentile 30-70% (media vol): K = 3.0
        - ATR percentile > 70% (alta vol):   K = 4.0 (o trailing ATRx3.0)
Time exit: 40 barre
```

### Performance su 2.7 anni (7704 candele, 2023-2025)
- Trade: ~340
- Win Rate: ~49%
- PnL: +11.18 pt (+11.180€)
- PF: 1.16
- Max DD: ~10.000€

### Performance su 3 mesi nuovi (708 candele, Feb-Giu 2026)
- Trade: ~30
- Win Rate: ~57%
- PnL: +7.38 pt (+7.212€)
- PF: 2.08

### Nota
La strategia e MARGINALMENTE positiva (PF~1.15 su 2.7 anni). Il 93% del PnL
originale era look-ahead bias. Per un edge reale serve un approccio diverso
(mean reversion, opzioni, multi-timeframe).
