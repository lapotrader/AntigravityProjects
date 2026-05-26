import pandas as pd
import numpy as np

def load_and_filter_data(filepath, start_date=None, end_date=None):
    df = pd.read_csv(filepath, sep='\t')
    df.columns = [c.strip().lower() for c in df.columns]
    try:
        df['data'] = pd.to_datetime(df['data'])
    except Exception:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    for col in ['high', 'low', 'open', 'close', 'volume']:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            else:
                df[col] = df[col].astype(float)
    if start_date:
        df = df[df['data'] >= start_date]
    if end_date:
        df = df[df['data'] <= end_date]
    return df.sort_values('data').reset_index(drop=True)

def calculate_supertrend(df, period, multiplier):
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    df['hl2'] = (high + low) / 2
    df['basic_ub'] = df['hl2'] + multiplier * df['atr']
    df['basic_lb'] = df['hl2'] - multiplier * df['atr']
    final_ub = [0.0] * len(df)
    final_lb = [0.0] * len(df)
    supertrend = [0.0] * len(df)
    direction = [1] * len(df)
    for i in range(len(df)):
        if i == 0:
            final_ub[i] = df['basic_ub'].iloc[i]
            final_lb[i] = df['basic_lb'].iloc[i]
            supertrend[i] = final_ub[i]
            direction[i] = -1
            continue
        prev_close = df['close'].iloc[i-1]
        prev_final_ub = final_ub[i-1]
        prev_final_lb = final_lb[i-1]
        if df['basic_ub'].iloc[i] < prev_final_ub or prev_close > prev_final_ub:
            final_ub[i] = df['basic_ub'].iloc[i]
        else:
            final_ub[i] = prev_final_ub
        if df['basic_lb'].iloc[i] > prev_final_lb or prev_close < prev_final_lb:
            final_lb[i] = df['basic_lb'].iloc[i]
        else:
            final_lb[i] = prev_final_lb
        prev_super = supertrend[i-1]
        if prev_super == prev_final_ub:
            if df['close'].iloc[i] > final_ub[i]:
                supertrend[i] = final_lb[i]
                direction[i] = 1
            else:
                supertrend[i] = final_ub[i]
                direction[i] = -1
        else:
            if df['close'].iloc[i] < final_lb[i]:
                supertrend[i] = final_ub[i]
                direction[i] = -1
            else:
                supertrend[i] = final_lb[i]
                direction[i] = 1
    df['supertrend'] = supertrend
    df['direction'] = direction
    return df

def main():
    # Load all DAX data and apply full supertrend on the whole series (important for continuity)
    dax_full = load_and_filter_data('dax_220m.txt')
    dax_full = calculate_supertrend(dax_full, period=10, multiplier=4.0)
    
    # SMA 100
    dax_full['sma100'] = dax_full['close'].rolling(window=100).mean()

    # Find the trade window: entry 2023-08-31, exit 2023-09-08
    entry_date = pd.Timestamp('2023-08-31')
    exit_date  = pd.Timestamp('2023-09-08')

    # Show bars from a few days before entry to a few after exit
    window_start = pd.Timestamp('2023-08-25')
    window_end   = pd.Timestamp('2023-09-12')
    window = dax_full[(dax_full['data'] >= window_start) & (dax_full['data'] <= window_end)].copy()

    entry_price = None

    print("="*110)
    print(f"DAX – Dettaglio barre 220 min intorno al trade LONG (entrata ~31 ago, uscita ~8 set 2023)")
    print(f"Configurazione: SuperTrend period=10, multiplier=4.0, SMA100, TP=0.5xATR")
    print("="*110)
    print(f"{'Data/Ora':<22} {'Open':>9} {'High':>9} {'Low':>9} {'Close':>9} {'SuperTrend':>12} {'Dir':>4} {'SMA100':>9} {'Distanza ST':>12}  Note")
    print("-"*110)

    for _, row in window.iterrows():
        note = ''
        dt = row['data']
        dist = row['close'] - row['supertrend']  # positivo = close sopra ST (zona long sicura)

        if dt.date() == entry_date.date() and entry_price is None:
            entry_price = row['open']
            note = f'<-- ENTRATA LONG @ {entry_price:.2f}'
        
        if entry_price is not None and dt.date() > entry_date.date():
            pnl = (row['close'] - entry_price) * 25.0
            note = f'PnL aperto: {pnl:+,.0f} EUR  (close-ST gap: {dist:+.1f})'

        if row['close'] < row['supertrend'] and entry_price is not None and 'STOP' not in note:
            note += '  *** STOP ATTIVATO ***'

        dir_str = 'UP' if row['direction'] == 1 else 'DN'
        print(f"  {str(dt):<20} {row['open']:>9.1f} {row['high']:>9.1f} {row['low']:>9.1f} {row['close']:>9.1f} "
              f"{row['supertrend']:>12.1f} {dir_str:>4} {row['sma100']:>9.1f} {dist:>+12.1f}  {note}")

    print()
    print("SPIEGAZIONE:")
    print("  Il SuperTrend con period=10, multiplier=4.0 e' molto AMPIO (usa 4x l'ATR).")
    print("  Questo lo rende resistente ai falsi segnali (alta % vincita) ma tollera")
    print("  correzioni MOLTO ampie prima di scattare lo stop.")
    print("  Il DAX e' sceso da ~16.000 a ~15.600 (-400 punti) senza mai chiudere sotto ST.")
    print()
    if entry_price:
        print(f"  Prezzo di entrata: {entry_price:.2f}")
        exit_row = dax_full[dax_full['data'].dt.date == exit_date.date()]
        if not exit_row.empty:
            exit_close = exit_row.iloc[-1]['close']
            exit_st = exit_row.iloc[-1]['supertrend']
            loss = (exit_close - entry_price) * 25.0 - 6.0
            print(f"  Prezzo di uscita (close): {exit_close:.2f}")
            print(f"  SuperTrend all'uscita: {exit_st:.2f}")
            print(f"  Perdita: {loss:+,.2f} EUR")
            print(f"  Distanza entry->stop: {abs(exit_close - entry_price):.1f} punti = {abs(exit_close - entry_price)*25:.0f} EUR lordi")

if __name__ == '__main__':
    main()
