import pandas as pd
import numpy as np
import os

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

PER_POINT = {'dax': 25.0, 'btp': 1000.0, 'bund': 1000.0, 'stoxx': 10.0}
COMMISSION = 6.0

def run_strategy_with_trade_details(df, period, multiplier, tp_multiplier, ma_period, instrument='bund'):
    df = df.copy()
    df = calculate_supertrend(df, period, multiplier)
    ma_col = None
    if ma_period and str(ma_period) != 'None':
        ma_col = f'sma{ma_period}'
        df[ma_col] = df['close'].rolling(window=int(ma_period)).mean()
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    tp_level = 0.0
    entry_date = None
    pnl_per_bar = [0.0] * len(df)
    for i in range(len(df)):
        min_idx = max(21, int(ma_period) if ma_col else 0)
        if i < min_idx:
            continue
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        cur_open = df['open'].iloc[i]
        cur_high = df['high'].iloc[i]
        cur_low = df['low'].iloc[i]
        cur_close = df['close'].iloc[i]
        cur_super = df['supertrend'].iloc[i]
        cur_date = df['data'].iloc[i]
        if in_position:
            pnl = 0.0
            closed = False
            exit_reason = ''
            if pos_type == 'long':
                if cur_high >= tp_level and tp_multiplier != 999.0:
                    pnl = ((tp_level - entry_price) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                    exit_reason = 'TP'
                elif cur_close < cur_super:
                    pnl = ((cur_close - entry_price) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                    exit_reason = 'ST_STOP'
            else:
                if cur_low <= tp_level and tp_multiplier != 999.0:
                    pnl = ((entry_price - tp_level) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                    exit_reason = 'TP'
                elif cur_close > cur_super:
                    pnl = ((entry_price - cur_close) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                    exit_reason = 'ST_STOP'
            if closed:
                pnl_per_bar[i] = pnl
                trades.append({
                    'instrument': instrument.upper(),
                    'type': pos_type.upper(),
                    'entry_date': entry_date,
                    'exit_date': cur_date,
                    'entry_price': entry_price,
                    'exit_reason': exit_reason,
                    'pnl_eur': round(pnl, 2)
                })
                in_position = False
                pos_type = None
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_prev = df[ma_col].iloc[i-1] if ma_col else None
            allow_long = True
            allow_short = True
            if ma_prev is not None and not np.isnan(ma_prev):
                allow_long = close_prev > ma_prev
                allow_short = close_prev < ma_prev
            if prev_dir == 1 and prev_prev_dir == -1 and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = cur_open
                entry_date = cur_date
                atr = df['atr'].iloc[i-1]
                tp_level = entry_price + tp_multiplier * atr
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = cur_open
                entry_date = cur_date
                atr = df['atr'].iloc[i-1]
                tp_level = entry_price - tp_multiplier * atr
    df['bar_pnl_eur'] = pnl_per_bar
    return df, trades

def main():
    print("Loading data...")
    btp = load_and_filter_data('btp_220m.txt')
    bund = load_and_filter_data('bund_220m.txt')
    dax = load_and_filter_data('dax_220m.txt')
    stoxx = load_and_filter_data('stoxx_220m.txt')
    start = max(btp['data'].min(), bund['data'].min(), dax['data'].min(), stoxx['data'].min())
    end = min(btp['data'].max(), bund['data'].max(), dax['data'].max(), stoxx['data'].max())
    btp = load_and_filter_data('btp_220m.txt', start, end)
    bund = load_and_filter_data('bund_220m.txt', start, end)
    dax = load_and_filter_data('dax_220m.txt', start, end)
    stoxx = load_and_filter_data('stoxx_220m.txt', start, end)

    print("Running strategies...")
    _, trades_btp = run_strategy_with_trade_details(btp, 20, 3.0, 1.0, 21, 'btp')
    _, trades_bund = run_strategy_with_trade_details(bund, 20, 1.5, 999.0, 50, 'bund')
    _, trades_dax = run_strategy_with_trade_details(dax, 10, 4.0, 0.5, 100, 'dax')
    _, trades_stoxx = run_strategy_with_trade_details(stoxx, 10, 4.0, 1.0, 21, 'stoxx')

    all_trades = trades_btp + trades_bund + trades_dax + trades_stoxx
    df_trades = pd.DataFrame(all_trades)

    # Focus on Aug-Sep 2023
    print("\n" + "="*80)
    print("TRADES AGOSTO - SETTEMBRE 2023 (tutte le strategie)")
    print("="*80)
    mask = (df_trades['exit_date'] >= '2023-08-01') & (df_trades['exit_date'] <= '2023-09-30')
    period_trades = df_trades[mask].sort_values('exit_date')
    
    for _, t in period_trades.iterrows():
        emoji = "+" if t['pnl_eur'] > 0 else "!!!"
        print(f"  {t['instrument']:6s} | {t['type']:5s} | Entry: {t['entry_date'].strftime('%Y-%m-%d')} | "
              f"Exit: {t['exit_date'].strftime('%Y-%m-%d')} | Price: {t['entry_price']:.2f} | "
              f"Reason: {t['exit_reason']:7s} | PnL: {t['pnl_eur']:>+10.2f} EUR  {emoji}")

    total_period = period_trades['pnl_eur'].sum()
    losses = period_trades[period_trades['pnl_eur'] < 0]
    wins = period_trades[period_trades['pnl_eur'] > 0]
    print(f"\n  Totale trade nel periodo: {len(period_trades)}")
    print(f"  Vincenti: {len(wins)}  |  Perdenti: {len(losses)}")
    print(f"  PnL totale ago-set 2023: {total_period:+,.2f} EUR")
    print(f"  Perdita totale trade negativi: {losses['pnl_eur'].sum():+,.2f} EUR")

    # Per-instrument breakdown
    print("\n  --- Breakdown per strumento ---")
    for instr in ['BTP', 'BUND', 'DAX', 'STOXX']:
        sub = period_trades[period_trades['instrument'] == instr]
        if len(sub) > 0:
            print(f"  {instr}: {len(sub)} trade, PnL = {sub['pnl_eur'].sum():+,.2f} EUR")
        else:
            print(f"  {instr}: nessun trade nel periodo")

if __name__ == '__main__':
    main()
