# Riepilogo e Ragionamento Strategia Quantitativa: BTP Future

Questo documento salva il percorso logico, le scoperte statistiche e la strategia in opzioni sviluppata per il BTP Future.

## 1. Il Punto di Partenza: Markov e HMM
Siamo partiti dall'applicare l'"Hedge Fund Method" al BTP, definendo 3 regimi di mercato (Bull, Bear, Sideways) usando una soglia adattiva a +/- 1 Deviazione Standard a 20 giorni.
* **Scoperta Fondamentale**: Il BTP ha uno "Stickiness Score" altissimo nella fase laterale (quasi il 70%).
* **Conferma Matematica**: Il modello *Hidden Markov Model (HMM)* ha confermato l'etichettatura deterministica.

## 2. Il Limite Predittivo e l'Evoluzione
Elevando a potenza la matrice di transizione, abbiamo scoperto che l'informazione predittiva decade rapidamente (l'Entropia prende il sopravvento in circa 3 giorni). A 20 giorni di distanza, la probabilità di trovarsi in un certo regime ricade sempre sulla distribuzione stazionaria (68% probabilità di essere Sideways). 
**L'Intuizione**: Più che cercare di prevedere la direzione, possiamo *sfruttare* l'immobilità del mercato vendendo **Call e Put (Short Strangle/Iron Condor)** per incassare il premio (Theta Decay) in base al trascorrere del tempo.

## 3. L'Approccio Empirico sulle Opzioni (No Black-Scholes)
Per calcolare gli Strike (livelli di sicurezza) a 20 giorni, abbiamo scartato la distribuzione Normale (troppo rischiosa per i venditori di premi) e abbracciato un calcolo empirico basato sulle **code grasse**:
* Abbiamo campionato i dati storici tick-by-tick trasformandoli in candele OHLC per non perderci neanche un picco (Spike) intraday.
* Abbiamo estratto l'escursione massima positiva (Run-Up) e negativa (Drawdown) per ogni finestra di 20 giorni futuri.

## 4. Il Backtest Walk-Forward (La Validazione)
L'errore più comune dei Quant alle prime armi è il *look-ahead bias* (fissare i livelli guardando a tutto il passato e tutto il futuro insieme). 
Abbiamo costruito un simulatore che agisce "al buio", ricalcolando i percentili di rischio usando SOLO i dati precedenti alla data di simulazione.
* **Target Statistico Ricercato**: 90.0% di Win Rate (Nessun tocco sugli strike).
* **Win Rate Reale Ottenuto**: **91.29%**. (Il modello ha dimostrato di funzionare perfettamente nella realtà).

## 5. Il Grande Insight: Asimmetria del Rischio (Skewness)
I 37 trade persi nel backtest ci hanno fornito la chiave per dominare il mercato. Le violazioni non sono simmetriche:
* **Call Sfondate (Mercato Esplode al Rialzo)**: solo lo **0.5%** dei casi.
* **Put Sfondate (Mercato Crolla al Ribasso)**: l'**8.2%** dei casi.

**Regola Operativa**: Il rischio vero sui titoli di stato italiani è il crollo (es. allargamento improvviso dello spread). Il lato Call è estremamente sicuro. Quando impostiamo i trade, la sorveglianza va mantenuta focalizzata sulla gamba Put, essendo pronti ad applicare tecniche di "Rolling" (spostare la put più in basso per guadagnare tempo) o di hedging meccanico (tagliare la perdita al raddoppio del premio).

## 6. L'Ecosistema degli Script Python (Toolkit)
Per automatizzare la strategia sono stati codificati 3 script:
1. `btp_hmm_analysis.py`: Valuta il regime di mercato (Bull/Bear/Sideways) odierno, estrae la matrice di Markov e conferma il segnale con l'HMM. Utile per avere la bussola direzionale.
2. `btp_options_calculator.py`: Il cuore operativo. Lo avvii ogni giorno per farti stampare a che livello matematico (es. al 90% di confidenza) devi vendere la tua Call e la tua Put. Include il modulo di allerta "Skew", che ti avvisa se il mercato sta curvando il suo rischio verso uno dei due lati.
3. `btp_options_backtest.py`: L'ambiente di collaudo. Lo usi per testare come le strategie si sarebbero comportate in passato con la logica walk-forward, in caso volessi variare parametri o confidenza.
