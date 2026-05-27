# SOP: Generazione Segnali SuperTrend per BTP 1h

## 1. Caricamento Dati
- Leggere `dati/1oraprova.txt` con `pandas.read_csv(sep='\t', skiprows=2)`
- Rinominare colonne in: `data, high, low, open, close, volume`
- Convertire `data` in datetime con formato `%d/%m/%Y %H:%M:%S`
- Sostituire virgole con punti nei campi numerici e convertire a float
- Ordinare per data e resettare l'indice

## 2. Calcolo SuperTrend (14, 3.0)

### True Range (TR)
```
TR = max(high - low, |high - close_prev|, |low - close_prev|)
```

### ATR
```
ATR = TR.ewm(alpha=1/14, adjust=False).mean()
```

### Bande Base
```
hl2 = (high + low) / 2
basic_ub = hl2 + 3.0 * ATR
basic_lb = hl2 - 3.0 * ATR
```

### Bande Finali (iterativo)
- Alla prima candela: `final_ub = basic_ub`, `final_lb = basic_lb`
- Per ogni candela successiva:
  - `final_ub[i] = basic_ub[i]` se `basic_ub[i] < final_ub[i-1]` OPPURE `close[i-1] > final_ub[i-1]`, altrimenti `final_ub[i-1]`
  - `final_lb[i] = basic_lb[i]` se `basic_lb[i] > final_lb[i-1]` OPPURE `close[i-1] < final_lb[i-1]`, altrimenti `final_lb[i-1]`

### Direzione
- Se `supertrend[i-1] == final_ub[i-1]` (era in downtrend):
  - Se `close[i] > final_ub[i]` → flip a LONG (super=final_lb, dir=1)
  - Altrimenti → continua SHORT (super=final_ub, dir=-1)
- Se `supertrend[i-1] == final_lb[i-1]` (era in uptrend):
  - Se `close[i] < final_lb[i]` → flip a SHORT (super=final_ub, dir=-1)
  - Altrimenti → continua LONG (super=final_lb, dir=1)

## 3. Rilevamento Flip (Segnali)
- Iterare da indice 2 in poi
- **LONG**: quando `direction[i-1] == 1` e `direction[i-2] == -1`
- **SHORT**: quando `direction[i-1] == -1` e `direction[i-2] == 1`
- Entry al prezzo `open[i]` (apertura candela successiva al flip)
- Registrare data/ora entry, direzione, prezzo entry, ATR al momento

## 4. Salvataggio
- Salvare i segnali in `output/supertrend_signals_1h.json`
- Stampare riepilogo a console
