"""
Command-line interface for running backtests.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from backtester.data import DataLoader
from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics
from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Algorithmic Trading Backtesting System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--strategy",
        type=str,
        default="sma",
        choices=["sma", "rsi"],
        help="Strategy to run (sma or rsi)",
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="SPY",
        help="Stock symbol to backtest",
    )
    
    parser.add_argument(
        "--start",
        type=str,
        default="2020-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD), defaults to latest",
    )
    
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to CSV file instead of fetching from Yahoo Finance",
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital",
    )
    
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Commission rate (0.001 = 0.1%%)",
    )
    
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0005,
        help="Slippage rate (0.0005 = 0.05%%)",
    )
    
    parser.add_argument(
        "--position-size",
        type=float,
        default=0.95,
        help="Position size (fraction of equity for fixed_fraction mode)",
    )
    
    parser.add_argument(
        "--fast-period",
        type=int,
        default=50,
        help="Fast SMA period (for SMA strategy)",
    )
    
    parser.add_argument(
        "--slow-period",
        type=int,
        default=200,
        help="Slow SMA period (for SMA strategy)",
    )
    
    parser.add_argument(
        "--rsi-period",
        type=int,
        default=14,
        help="RSI period (for RSI strategy)",
    )
    
    parser.add_argument(
        "--rsi-oversold",
        type=float,
        default=30,
        help="RSI oversold threshold (for RSI strategy)",
    )
    
    parser.add_argument(
        "--rsi-overbought",
        type=float,
        default=70,
        help="RSI overbought threshold (for RSI strategy)",
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Directory for output files",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ALGORITHMIC TRADING BACKTESTING SYSTEM")
    print("=" * 60)
    print(f"Strategy: {args.strategy.upper()}")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.start} to {args.end or 'latest'}")
    print(f"Initial Capital: ${args.capital:,.2f}")
    print("=" * 60 + "\n")
    
    try:
        loader = DataLoader()
        
        if args.csv:
            print(f"Loading data from CSV: {args.csv}")
            data = loader.load_csv(args.csv)
        else:
            data = loader.fetch_yahoo(args.symbol, args.start, args.end)
        
        print(f"Loaded {len(data)} bars from {data.index[0].date()} to {data.index[-1].date()}\n")
        
        if args.strategy == "sma":
            strategy = SMACrossover(
                fast_period=args.fast_period,
                slow_period=args.slow_period,
            )
            print(f"Running SMA Crossover (Fast={args.fast_period}, Slow={args.slow_period})...")
        else:
            strategy = RSIMeanReversion(
                period=args.rsi_period,
                oversold=args.rsi_oversold,
                overbought=args.rsi_overbought,
            )
            print(f"Running RSI Mean Reversion (Period={args.rsi_period}, Oversold={args.rsi_oversold}, Overbought={args.rsi_overbought})...")
        
        engine = BacktestEngine(
            initial_capital=args.capital,
            commission=args.commission,
            slippage=args.slippage,
            position_size_type="fixed_fraction",
            position_size_value=args.position_size,
        )
        
        equity_curve = engine.run(strategy, data)
        
        metrics = PerformanceMetrics(
            equity_curve=equity_curve,
            trades=engine.trades,
            initial_capital=args.capital,
        )
        metrics.print_summary()
        
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        equity_file = output_dir / f"equity_curve_{args.symbol}_{args.strategy}_{timestamp}.csv"
        trades_file = output_dir / f"trades_{args.symbol}_{args.strategy}_{timestamp}.csv"
        
        equity_curve.to_csv(equity_file)
        print(f"Equity curve saved to: {equity_file}")
        
        trades_df = engine.get_trades_df()
        if not trades_df.empty:
            trades_df.to_csv(trades_file, index=False)
            print(f"Trades saved to: {trades_file}")
            print(f"\nTotal trades executed: {len(trades_df)}")
        else:
            print("\nNo trades were executed during the backtest period.")
        
        print("\nBacktest complete!")
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
