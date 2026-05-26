import pandas as pd
import numpy as np
import os

def load_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Il file '{filepath}' non esiste.")
    df = pd.read_csv(filepath, sep='\t')
    df.columns = [col.strip().lower() for col in df.columns]
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').reset_index(drop=True)
    numeric_cols = ['high', 'low', 'open', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            else:
                df[col] = df[col].astype(float)
    return df

def calculate_supertrend(df, period, multiplier):
    high = df['high']
    low = df['low']
    close = df['close']
    
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
            
        prev_supertrend = supertrend[i-1]
        if prev_supertrend == prev_final_ub:
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

def run_backtest_ma(df, tp_multiplier, ma_series=None):
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0
    
    equity_curve = []
    current_equity = 0.0
    
    for i in range(len(df)):
        if i < 21:
            equity_curve.append(0.0)
            continue
            
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        
        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        
        if in_position:
            if pos_type == 'long':
                if current_high >= tp_level:
                    pnl = tp_level - entry_price
                    current_equity += pnl
                    trades.append({'type': 'Long', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
                elif current_close < current_supertrend:
                    pnl = current_close - entry_price
                    current_equity += pnl
                    trades.append({'type': 'Long', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
            elif pos_type == 'short':
                if current_low <= tp_level:
                    pnl = entry_price - tp_level
                    current_equity += pnl
                    trades.append({'type': 'Short', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
                elif current_close > current_supertrend:
                    pnl = entry_price - current_close
                    current_equity += pnl
                    trades.append({'type': 'Short', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
                    
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = ma_series.iloc[i-1] if ma_series is not None else None
            
            allow_long = True
            allow_short = True
            
            if ma_val_prev is not None and not np.isnan(ma_val_prev):
                allow_long = close_prev > ma_val_prev
                allow_short = close_prev < ma_val_prev
            
            if prev_dir == 1 and prev_prev_dir == -1 and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = current_open
                entry_idx = i
                tp_level = entry_price + tp_multiplier * df['atr'].iloc[i-1]
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                tp_level = entry_price - tp_multiplier * df['atr'].iloc[i-1]
                
        equity_curve.append(current_equity)
        
    equity_arr = np.array(equity_curve) * 1000
    cum_max = np.maximum.accumulate(equity_arr)
    drawdown = cum_max - equity_arr
    max_dd = drawdown.max()
    
    return trades, current_equity, max_dd

def main():
    df = load_data('btp3h.txt')
    
    ma_dict = {
        21: df['close'].rolling(window=21).mean(),
        50: df['close'].rolling(window=50).mean(),
        100: df['close'].rolling(window=100).mean(),
        200: df['close'].rolling(window=200).mean(),
        'None': None
    }
    
    results = []
    
    periods = [10, 14, 20, 30]
    multipliers = [1.5, 2.0, 2.5, 3.0]
    tps = [0.5, 1.0, 1.5, 2.0, 3.0, 999.0]
    ma_periods = ['None', 21, 50, 100, 200]
    
    print("Inizio ottimizzazione BTP 3h con filtri Media Mobile...")
    
    total_runs = len(periods) * len(multipliers) * len(tps) * len(ma_periods)
    current_run = 0
    
    for period in periods:
        for mult in multipliers:
            df_st = df.copy()
            df_st = calculate_supertrend(df_st, period, mult)
            
            for tp in tps:
                for ma_p in ma_periods:
                    current_run += 1
                    ma_series = ma_dict[ma_p]
                    
                    trades, final_profit, max_dd = run_backtest_ma(df_st, tp, ma_series)
                    
                    if len(trades) == 0:
                        continue
                        
                    pnl_series = [t['pnl'] * 1000 for t in trades]
                    wins = sum(1 for p in pnl_series if p > 0)
                    losses = sum(1 for p in pnl_series if p <= 0)
                    win_rate = (wins / len(trades)) * 100 if len(trades) > 0 else 0
                    
                    gross_profit = sum(p for p in pnl_series if p > 0)
                    gross_loss = abs(sum(p for p in pnl_series if p <= 0))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                    
                    results.append({
                        'ma_period': str(ma_p),
                        'st_period': period,
                        'st_multiplier': mult,
                        'tp_mult': tp if tp != 999.0 else 'No TP',
                        'trades': len(trades),
                        'win_rate': win_rate,
                        'profit_factor': profit_factor,
                        'net_profit_eur': final_profit * 1000,
                        'max_dd_eur': max_dd
                    })
                    
    res_df = pd.DataFrame(results)
    
    res_df = res_df.sort_values(by='net_profit_eur', ascending=False)
    
    res_df.to_csv('btp3h_optimization_results.csv', index=False)
    print(f"\nRun completate: {current_run}")
    print("\nTop 15 Combinazioni Ottimizzate per Profitto Netto:")
    print(res_df.head(15).to_string(index=False))
    
    res_df['profit_dd_ratio'] = res_df['net_profit_eur'] / res_df['max_dd_eur']
    res_df_ratio = res_df.sort_values(by='profit_dd_ratio', ascending=False)
    print("\nTop 15 Combinazioni Ottimizzate per Rapporto Profitto/Drawdown:")
    print(res_df_ratio.head(15).to_string(index=False))
    print("\nRisultati completi salvati in 'btp3h_optimization_results.csv'.")

if __name__ == '__main__':
    main()
