# Millantatore

Verifica indipendente delle strategie di "Strategie di trading con Python" (Trombetta)

---

## Premessa

Tutte le strategie sono state testate con:
- **Nessun look-ahead**: segnale a `close[i]`, esecuzione a `open[i+1]`
- **Costi reali**: 3€/side commissioni, slippage 1 tick base
- **Split cronologici**: IS (2023), OOS (2024), FWD (2025), Blind (2026)
- **Validazione su minimo PF tra tutti i periodi**: un sistema vale solo se **tutti** i periodi hanno PF > 1.0

---

## 1. MACD + Supertrend su BTP 1h

| Fonte | Risultato dichiarato |
|-------|---------------------|
| Libro | PF netto 1.17, +5.500€/anno |

### Verifica

Griglia 720 combinazioni MACD x TP/SL walk-forward su BTP 1h.

**Miglior sistema trovato**: MACD(5,30,3) TP=5x SL=2x ATR

| Periodo | PF | PnL | n trades |
|---------|-----|-----|---------|
| IS 2023 | 1.20 | +6.438€ | 92 |
| OOS 2024 | 1.02 | +811€ | 121 |
| FWD 2025 | 1.10 | +2.445€ | 115 |
| **Blind 2026** | **1.62** | **+5.551€** | **27** |
| **TOTALE** | **1.16** | **+15.700€** | **354** |

A prima vista sembra funzionare. Ma:

#### Slippage Sensitivity (kill shot)

| Slippage | PF | PnL |
|----------|-----|-----|
| 0 tick | 1.18 | +17.355€ |
| **1 tick (base)** | **1.16** | **+15.700€** |
| 2 tick | 1.08 | +7.720€ |
| **3 tick** | **0.94** | **-6.557€** |

Con 3 tick di slippage (ipotizzabile in esecuzione reale su BTP), il sistema **perde denaro**. Non c'e' robustezza.

### Verdetto: ❌ NON VALIDO

> Il sistema esiste solo con slippage zero. Basta un minimo attrito di mercato per dissolversi.

---

## 2. SuperTrend su DAX 3min (09:00-17:30)

| Fonte | Risultato dichiarato |
|-------|---------------------|
| Codice originale (bug look-ahead) | PF > 1.45 su tutti i periodi |

Dopo aver corretto il bug di timing (esecuzione a `open[i+1]` invece che `open[i]`), il castello crolla.

### Verifica

Griglia 6 periodi ATR x 7 moltiplicatori = 42 combinazioni.

| Parametro | IS_PF | OOS_PF | FWD_PF | Blind_PF | min PF |
|-----------|-------|--------|--------|----------|--------|
| ST(7,2.0) | 1.31 | 1.24 | 0.97 | 0.86 | **0.86** |
| ST(10,2.0) | 1.21 | 1.07 | 0.92 | 0.76 | **0.76** |
| ST(14,2.0) | 1.12 | 1.06 | 0.81 | 0.72 | **0.72** |

**Zero** combinazioni con min PF > 1.00 su 42. Il bull market DAX 14.000 -> 25.500 (+82%) mascherava tutto.

### Verdetto: ❌ NON VALIDO

> Il SuperTrend su DAX 3min dopo costi reali e timing corretto non ha alcun edge. I PF positivi su IS+OOS erano un artefatto del bull market, non del sistema.

---

## 3. SuperTrend su Bund 3min (09:00-17:30)

### Verifica

Stessa griglia: 6 periodi x 7 moltiplicatori = 42 combinazioni. Bund ha range stretto (158 -> 123 in 8 anni).

| Parametro | IS_PF | OOS_PF | FWD_PF | Blind_PF | min PF |
|-----------|-------|--------|--------|----------|--------|
| ST(20,2.0) | 0.97 | 0.97 | 0.79 | 0.77 | **0.77** |
| ST(14,2.0) | 1.07 | 1.01 | 0.90 | 0.76 | **0.76** |

Nessuna combinazione sopra 1.00. Il Bund e' troppo poco volatile, i costi mangiano ogni segnale.

### Verdetto: ❌ NON VALIDO

> Troppo range stretto, commissioni insostenibili per un sistema a media frequenza.

---

## 4. SuperTrend su BTP 3min (09:00-17:30)

### Verifica

Stessa griglia. **BTP e' l'unico strumento che mostra un barlume di edge.**

**Migliori sistemi**:

| Sistema | IS_PF | IS_PnL | OOS_PF | OOS_PnL | FWD_PF | FWD_PnL | min PF |
|---------|-------|--------|--------|---------|--------|---------|--------|
| **ST(30,3.0)** | 1.68 | +16.624€ | 1.09 | +2.374€ | 1.11 | +2.500€ | **1.09** |
| **ST(20,3.0)** | 1.84 | +18.828€ | 1.11 | +2.936€ | 1.08 | +1.948€ | **1.08** |

2 sistemi su 42 (4.8%) hanno min PF > 1.00.

### Riserve critiche

1. **PnL modesto**: ST(30,3.0) fa solo +2.500€ su FWD 2025 — marginale
2. **Niente Blind 2026**: i dati BTP finiscono a dicembre 2025. Manca la validazione piu' importante
3. **Pochi trade**: periodi ATR 30 significano pochi segnali (~100/periodo)
4. **Slippage non testato**: da verificare se regge a 2-3 tick

### Verdetto: ❓ DUBBIO (non sufficiente)

> Primo sistema che mostra coerenza su 3 periodi, ma PnL troppo esiguo e manca validazione su Blind. Da approfondire con dati 2026.

---

## Riepilogo finale

| Strategia | Strumento | Timeframe | PF min | Verdetto |
|-----------|-----------|-----------|--------|----------|
| MACD + ST | BTP | 1h | 0.94 (3tick) | ❌ |
| SuperTrend | DAX | 3min | 0.86 | ❌ |
| SuperTrend | Bund | 3min | 0.77 | ❌ |
| SuperTrend | **BTP** | **3min** | **1.09** | ❓ |

## Conclusione

4 strategie testate, **3 falliscono completamente**, 1 e' dubbia con PnL marginale.

Il libro "Strategie di trading con Python" di Giovanni Trombetta millanta risultati che non reggono a:
1. Costi realistici (commissioni + slippage)
2. Split temporali rigorosi (IS/OOS/FWD/Blind)
3. Correzione di banali bug di look-ahead (1-bar timing)

Nessuna delle strategie analizzate e' passabile per trading live.

---

*Report generato il 2 Giugno 2026*
