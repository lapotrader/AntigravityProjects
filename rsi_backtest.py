import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')
np.seterr(all='ignore')

# -- DATA --------------------------------------------------------
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns = ["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]:
    cont[c] = cont[c].astype(float)

print(f"Bars: {len(cont)}  |  {cont.index[0]}  ->  {cont.index[-1]}")
print()

# -- INDICATORS --------------------------------------------------
def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_g = gain.rolling(period, min_periods=period).mean()
    avg_l = loss.rolling(period, min_periods=period).mean()
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))

def compute_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()

# -- BACKTEST ENGINE ---------------------------------------------
def backtest(df, params, strategy='rsi_extreme', verbose=False):
    rsi_period = int(params.get('rsi_period', 14))
    rsi_lower  = params.get('rsi_lower', 30)
    rsi_upper  = params.get('rsi_upper', 70)
    tp_atr     = params.get('tp_atr', 3)
    sl_atr     = params.get('sl_atr', 2)
    vol_mult   = params.get('vol_mult', 1.0)
    div_window = int(params.get('div_window', 14))

    df = df.copy()
    df['rsi'] = compute_rsi(df['close'], rsi_period)
    df['atr'] = compute_atr(df['high'], df['low'], df['close'], 14)
    df['vol_sma20'] = df['volume'].rolling(20, min_periods=20).mean()
    df['swing_low5']  = df['low'].rolling(5, min_periods=5).min()
    df['swing_high5'] = df['high'].rolling(5, min_periods=5).max()

    trades = []
    pos = 0       # 1 long, -1 short, 0 flat
    entry_p = 0.0
    entry_i = 0
    sl_p = 0.0
    tp_p = 0.0

    start = max(rsi_period, 20, 14) + 5

    for i in range(start, len(df)):
        bar = df.iloc[i]
        prev = df.iloc[i-1]

        # -- manage open position --
        if pos != 0:
            bars_in = i - entry_i
            exited = False

            if pos == 1:
                hit_sl = bar['low'] <= sl_p
                hit_tp = bar['high'] >= tp_p
                if hit_sl or hit_tp:
                    if hit_sl and hit_tp:
                        exit_p = sl_p if (sl_p - entry_p) < (tp_p - entry_p) else tp_p
                    elif hit_sl:
                        exit_p = sl_p
                    else:
                        exit_p = tp_p
                    exit_p = np.clip(exit_p, bar['low'], bar['high'])
                    pnl = exit_p - entry_p
                    trades.append(dict(entry_time=df.index[entry_i], exit_time=df.index[i],
                        entry_price=entry_p, exit_price=exit_p, direction=1, pnl=pnl,
                        bars=bars_in, exit_reason='sl' if hit_sl else 'tp'))
                    pos = 0; exited = True
            else:
                hit_sl = bar['high'] >= sl_p
                hit_tp = bar['low'] <= tp_p
                if hit_sl or hit_tp:
                    if hit_sl and hit_tp:
                        exit_p = sl_p if (sl_p - entry_p) < (tp_p - entry_p) else tp_p
                    elif hit_sl:
                        exit_p = sl_p
                    else:
                        exit_p = tp_p
                    exit_p = np.clip(exit_p, bar['low'], bar['high'])
                    pnl = entry_p - exit_p
                    trades.append(dict(entry_time=df.index[entry_i], exit_time=df.index[i],
                        entry_price=entry_p, exit_price=exit_p, direction=-1, pnl=pnl,
                        bars=bars_in, exit_reason='sl' if hit_sl else 'tp'))
                    pos = 0; exited = True

            if not exited and bars_in >= 30:
                exit_p = bar['open']
                pnl = (exit_p - entry_p) if pos == 1 else (entry_p - exit_p)
                trades.append(dict(entry_time=df.index[entry_i], exit_time=df.index[i],
                    entry_price=entry_p, exit_price=exit_p, direction=pos, pnl=pnl,
                    bars=bars_in, exit_reason='timeout'))
                pos = 0; exited = True

        # -- entry signals --
        if pos == 0 and 'rsi' in df.columns and not pd.isna(prev['rsi']):
            sig_long = sig_short = False

            if strategy in ('rsi_extreme', 'volume_confirmation'):
                vol_ok = True
                if strategy == 'volume_confirmation':
                    vol_ok = (not pd.isna(prev['vol_sma20']) and
                              prev['volume'] > prev['vol_sma20'] * vol_mult)
                sig_long  = prev['rsi'] < rsi_lower and vol_ok
                sig_short = prev['rsi'] > rsi_upper and vol_ok

            elif strategy == 'divergence':
                wstart = max(start, i - 1 - div_window)
                window = df.iloc[wstart:i-1]
                if len(window) >= div_window // 2:
                    # bullish divergence: price lower low, RSI higher low
                    min_idx = window['close'].idxmin()
                    if prev['close'] < window['close'].min() and prev['rsi'] > df.loc[min_idx, 'rsi']:
                        sig_long = True
                    # bearish divergence: price higher high, RSI lower high
                    max_idx = window['close'].idxmax()
                    if prev['close'] > window['close'].max() and prev['rsi'] < df.loc[max_idx, 'rsi']:
                        sig_short = True

            if sig_long:
                pos = 1; entry_p = bar['open']; entry_i = i
                sl_swing = prev['swing_low5']
                sl_a = entry_p - sl_atr * prev['atr']
                sl_p = max(sl_swing, sl_a) if not pd.isna(sl_swing) else sl_a
                tp_p = entry_p + tp_atr * prev['atr']
            elif sig_short:
                pos = -1; entry_p = bar['open']; entry_i = i
                sl_swing = prev['swing_high5']
                sl_a = entry_p + sl_atr * prev['atr']
                sl_p = min(sl_swing, sl_a) if not pd.isna(sl_swing) else sl_a
                tp_p = entry_p - tp_atr * prev['atr']

    return pd.DataFrame(trades)

# -- METRICS -----------------------------------------------------
def compute_metrics(trades, prefix=''):
    if len(trades) == 0:
        return {f'{prefix}trades': 0}
    tot = trades['pnl'].sum()
    wins = trades[trades['pnl'] > 0]
    losses = trades[trades['pnl'] < 0]
    n_wins = len(wins)
    n_losses = len(losses)
    avg_win = wins['pnl'].mean() if n_wins > 0 else 0
    avg_loss = losses['pnl'].mean() if n_losses > 0 else 0
    pf = abs(avg_win * n_wins / (avg_loss * n_losses)) if n_losses > 0 and avg_loss != 0 else 0
    win_rate = n_wins / len(trades) * 100 if len(trades) > 0 else 0
    return {
        f'{prefix}trades': len(trades),
        f'{prefix}pnl': tot,
        f'{prefix}win_rate': win_rate,
        f'{prefix}avg_win': avg_win,
        f'{prefix}avg_loss': avg_loss,
        f'{prefix}pf': pf,
        f'{prefix}n_wins': n_wins,
        f'{prefix}n_losses': n_losses,
    }

# -- SPLIT -------------------------------------------------------
is_mask  = cont.index < "2020-01-01"
val_mask = (cont.index >= "2020-01-01") & (cont.index < "2023-01-01")
oos_mask = cont.index >= "2023-01-01"

df_is   = cont[is_mask].copy()
df_val  = cont[val_mask].copy()
df_oos  = cont[oos_mask].copy()

print(f"IS  bars: {len(df_is)}   ({df_is.index[0]} -> {df_is.index[-1]})")
print(f"VAL bars: {len(df_val)}  ({df_val.index[0]} -> {df_val.index[-1]})")
print(f"OOS bars: {len(df_oos)}  ({df_oos.index[0]} -> {df_oos.index[-1]})")
print("="*80)

# -- GRID SEARCH -------------------------------------------------
def run_grid_search(df_train, df_val, df_oos, param_grid, strategy, name):
    print(f"\n{'='*80}")
    print(f"STRATEGY: {name}")
    print(f"{'='*80}")
    
    keys = list(param_grid.keys())
    results = []

    for vals in product(*param_grid.values()):
        params = dict(zip(keys, vals))
        trades = backtest(df_train, params, strategy)
        m = compute_metrics(trades)
        results.append({**params, **m})

    res = pd.DataFrame(results)
    res = res[res['trades'] >= 10].copy()
    res = res[res['n_losses'] > 0].copy()
    if len(res) == 0:
        print("  No param combo meets minimum criteria (>=10 trades, not all wins)")
        return None, None

    res = res.sort_values('pf', ascending=False)

    print(f"\n  Top 10 by PF (IS):")
    print(f"  {'Params':<55s} {'Trades':>6s} {'PF':>7s} {'Win%':>6s} {'PnL':>9s}")
    print(f"  {'-'*55} {'-'*6} {'-'*7} {'-'*6} {'-'*9}")
    for _, r in res.head(10).iterrows():
        pstr = ", ".join(f"{k}={v}" for k,v in r.items() if k in keys)
        print(f"  {pstr:<55s} {r['trades']:>6.0f} {r['pf']:>7.3f} {r['win_rate']:>5.1f}% {r['pnl']:>9.2f}")

    best = res.iloc[0].to_dict()
    print(f"\n  BEST params: {', '.join(f'{k}={v}' for k,v in best.items() if k in keys)}")
    print(f"  IS:  trades={best['trades']:.0f}  PF={best['pf']:.3f}  WinRate={best['win_rate']:.1f}%  PnL={best['pnl']:.2f}")

    params_best = {k: best[k] for k in keys}
    t_val = backtest(df_val, params_best, strategy)
    m_val = compute_metrics(t_val)
    print(f"  VAL: trades={m_val['trades']:.0f}  PF={m_val['pf']:.3f}  WinRate={m_val['win_rate']:.1f}%  PnL={m_val['pnl']:.2f}")

    t_oos = backtest(df_oos, params_best, strategy)
    m_oos = compute_metrics(t_oos)
    print(f"  OOS: trades={m_oos['trades']:.0f}  PF={m_oos['pf']:.3f}  WinRate={m_oos['win_rate']:.1f}%  PnL={m_oos['pnl']:.2f}")

    # Fixed params
    print(f"\n  FIXED PARAMS (rsi_period=14, lower=30, upper=70, tp_atr=3):")
    fixed = {'rsi_period': 14, 'rsi_lower': 30, 'rsi_upper': 70, 'tp_atr': 3, 'sl_atr': 2}
    if 'vol_mult' in keys:
        fixed['vol_mult'] = 1.5
    if 'div_window' in keys:
        fixed['div_window'] = 14

    for dset, label in [(df_train, 'IS'), (df_val, 'VAL'), (df_oos, 'OOS')]:
        t = backtest(dset, fixed, strategy)
        m = compute_metrics(t)
        print(f"    {label}: trades={m['trades']:.0f}  PF={m['pf']:.3f}  WinRate={m['win_rate']:.1f}%  PnL={m['pnl']:.2f}")

    return best, params_best

# ===================================================================
# STRATEGY 1: RSI EXTREMES
# ===================================================================
param_grid_1 = {
    'rsi_period': [7, 14, 21],
    'rsi_lower':  [20, 25, 30],
    'rsi_upper':  [80, 75, 70],
    'tp_atr':     [2, 3, 4],
}
best1, pbest1 = run_grid_search(df_is, df_val, df_oos, param_grid_1, 'rsi_extreme', '1: RSI Extremes')
trades1_best = backtest(df_is, pbest1, 'rsi_extreme') if pbest1 else pd.DataFrame()

# ===================================================================
# STRATEGY 2: VOLUME CONFIRMATION
# ===================================================================
param_grid_2 = {
    'rsi_period': [7, 14, 21],
    'rsi_lower':  [20, 25, 30],
    'rsi_upper':  [80, 75, 70],
    'tp_atr':     [2, 3, 4],
    'vol_mult':   [1.0, 1.5, 2.0],
}
best2, pbest2 = run_grid_search(df_is, df_val, df_oos, param_grid_2, 'volume_confirmation', '2: Volume Confirmation')

# ===================================================================
# STRATEGY 3: RSI DIVERGENCE
# ===================================================================
param_grid_3 = {
    'div_window': [10, 14, 21],
    'tp_atr':     [2, 3, 4],
}
best3, pbest3 = run_grid_search(df_is, df_val, df_oos, param_grid_3, 'divergence', '3: RSI Divergence')

# ===================================================================
# DETERMINE OVERALL BEST
# ===================================================================
systems = []
if best1:
    best1['system'] = 'RSI Extremes'
    best1['best_params'] = str(pbest1)
    systems.append(best1)
if best2:
    best2['system'] = 'Volume Confirmation'
    best2['best_params'] = str(pbest2)
    systems.append(best2)
if best3:
    best3['system'] = 'RSI Divergence'
    best3['best_params'] = str(pbest3)
    systems.append(best3)

if systems:
    best_sys = max(systems, key=lambda x: x['pf'])
    print(f"\n{'='*80}")
    print(f"OVERALL BEST: {best_sys['system']} with PF={best_sys['pf']:.3f}")
    print(f"  Params: {best_sys['best_params']}")
    print(f"  IS: trades={best_sys['trades']:.0f}  PF={best_sys['pf']:.3f}  WinRate={best_sys['win_rate']:.1f}%  PnL={best_sys['pnl']:.2f}")

    # -- MONTHLY PNL ------------------------------------------
    strat_name = best_sys['system']
    overall_params = pbest1 if strat_name == 'RSI Extremes' else (pbest2 if strat_name == 'Volume Confirmation' else pbest3)
    overall_strat = 'rsi_extreme' if strat_name == 'RSI Extremes' else ('volume_confirmation' if strat_name == 'Volume Confirmation' else 'divergence')

    t_all = backtest(cont, overall_params, overall_strat)
    if len(t_all) > 0:
        t_all['month'] = t_all['entry_time'].dt.to_period('M')
        monthly = t_all.groupby('month').agg(
            trades=('pnl', 'count'), pnl=('pnl', 'sum'), avg_pnl=('pnl', 'mean')
        )
        monthly['cum'] = monthly['pnl'].cumsum()

        print(f"\n  MONTHLY PnL BREAKDOWN ({strat_name}):")
        print(f"  {'Month':<10s} {'Trades':>6s} {'PnL':>9s} {'Avg':>9s} {'Cum':>9s}")
        print(f"  {'-'*10} {'-'*6} {'-'*9} {'-'*9} {'-'*9}")
        for idx, r in monthly.iterrows():
            print(f"  {str(idx):<10s} {r['trades']:>6.0f} {r['pnl']:>9.2f} {r['avg_pnl']:>9.2f} {r['cum']:>9.2f}")

        # -- ON/OFF FILTER ------------------------------------
        print(f"\n  ON/OFF FILTER ANALYSIS ({strat_name}):")
        for dset, label in [(df_is, 'IS'), (df_val, 'VAL'), (df_oos, 'OOS')]:
            trades_p = backtest(dset, overall_params, overall_strat)
            if len(trades_p) == 0:
                print(f"    {label}: no trades")
                continue

            trades_p = trades_p.sort_values('entry_time').reset_index(drop=True)
            trades_p['entry_time'] = pd.to_datetime(trades_p['entry_time'])

            # Rolling 3M PnL sum before each trade
            roll_pnl = []
            for j in range(len(trades_p)):
                t0 = trades_p.loc[j, 'entry_time']
                prior = trades_p[(trades_p['entry_time'] >= t0 - pd.DateOffset(months=3)) &
                                 (trades_p['entry_time'] < t0)]
                roll_pnl.append(prior['pnl'].sum())
            trades_p['roll_3m_pnl'] = roll_pnl

            # No filter
            m_all = compute_metrics(trades_p)

            # Filtered (only trades with roll_3m_pnl > 0)
            trades_f = trades_p[trades_p['roll_3m_pnl'] > 0].copy()
            m_fil = compute_metrics(trades_f)

            print(f"    {label}:")
            print(f"      No filter:  trades={m_all['trades']:.0f}  PF={m_all['pf']:.3f}  WinRate={m_all['win_rate']:.1f}%  PnL={m_all['pnl']:.2f}")
            print(f"      Filtered:   trades={m_fil['trades']:.0f}  PF={m_fil['pf']:.3f}  WinRate={m_fil['win_rate']:.1f}%  PnL={m_fil['pnl']:.2f}")

    # -- ALSO: full param grid display --------------------------
    print(f"\n{'='*80}")
    print("FULL PARAM GRID RESULTS")
    print("="*80)

    for name, grid, strat_key, best_rec in [
        ('1: RSI Extremes', param_grid_1, 'rsi_extreme', best1),
        ('2: Volume Confirmation', param_grid_2, 'volume_confirmation', best2),
        ('3: RSI Divergence', param_grid_3, 'divergence', best3),
    ]:
        print(f"\n  {name}:")
        keys = list(grid.keys())
        results = []
        for vals in product(*grid.values()):
            params = dict(zip(keys, vals))
            t = backtest(df_is, params, strat_key)
            m = compute_metrics(t)
            if m['trades'] >= 10 and m['n_losses'] > 0:
                results.append({**params, **m})
        if results:
            rdf = pd.DataFrame(results).sort_values('pf', ascending=False)
            print(f"  {'Params':<50s} {'Trades':>6s} {'PF':>7s} {'Win%':>6s} {'PnL':>9s}")
            print(f"  {'-'*50} {'-'*6} {'-'*7} {'-'*6} {'-'*9}")
            for _, r in rdf.iterrows():
                pstr = ", ".join(f"{k}={v}" for k,v in r.items() if k in keys)
                print(f"  {pstr:<50s} {r['trades']:>6.0f} {r['pf']:>7.3f} {r['win_rate']:>5.1f}% {r['pnl']:>9.2f}")
else:
    print("No viable system found.")
