# Classic Pivots SL/TP per BTP 1h — SOP

## 1. Caricamento dati
- Leggere `dati/1oraprova.txt` (TSV, separatore tab)
- Saltare le prime 2 righe (intestazione strumento)
- Headers: `ora`, `high`, `low`, `open`, `close`, `volume`
- Pulire: sostituire `,` con `.` nei numeri; convertire `ora` in datetime (`DD/MM/YYYY HH:MM:SS`)

## 2. Identificazione pivot (lookback = N = 5)
### Pivot High
Una candela `i` è pivot high se:
```
high[i] > high[i-5] AND high[i] > high[i-4] AND ... AND high[i] > high[i+4] AND high[i] > high[i+5]
```
cioè il suo `high` è strettamente maggiore degli `high` delle 5 candele prima **e** 5 dopo.

### Pivot Low
Una candela `i` è pivot low se:
```
low[i] < low[i-5] AND low[i] < low[i-4] AND ... AND low[i] < low[i+4] AND low[i] < low[i+5]
```
cioè il suo `low` è strettamente minore dei `low` delle 5 candele prima **e** 5 dopo.

**Nota:** Le prime 5 e ultime 5 candele non possono avere pivot.

## 3. Carry-forward dei pivot più vicini
Per ogni candela (dopo la prima occorrenza):
- `nearest_pivot_high` = ultimo pivot high incontrato (None se nessuno ancora)
- `nearest_pivot_low` = ultimo pivot low incontrato (None se nessuno ancora)

## 4. Calcolo ATR (14 periodi)
```
TR = max(high - low, |high - prev_close|, |low - prev_close|)
ATR = media mobile esponenziale (o semplice) dei TR su 14 periodi
```
Usare SMA per semplicità.

## 5. Calcolo SL/TP da segnali (se presenti)
Leggere `output/supertrend_signals_1h.json`. Formato atteso:
```json
[
  {"timestamp": "2026-02-23 10:00:00", "signal": "LONG", "price": 122.26},
  ...
]
```

### LONG
- SL = `nearest_pivot_low - 0.5 * ATR`
- TP = `nearest_pivot_high`

### SHORT
- SL = `nearest_pivot_high + 0.5 * ATR`
- TP = `nearest_pivot_low`

## 6. Output
- `output/pivot_levels_1h.json` — lista di tutti i pivot (timestamp, tipo, prezzo)
- `output/trade_setup_1h.json` — lista setup (timestamp segnale, direzione, entry, SL, TP, pivot_low_usato, pivot_high_usato, ATR_usato)
