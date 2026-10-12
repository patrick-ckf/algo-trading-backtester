#!/usr/bin/env python3
"""
Standalone demo of multi-asset portfolio backtest.

Run this to see the portfolio backtest in action without the Streamlit UI.
"""

from backtester.portfolio import PortfolioBacktester, calculate_benchmark
import pandas as pd


def main():
    print("=" * 70)
    print("Multi-Asset Portfolio Backtest Demo")
    print("=" * 70)
    print()
    
    # Configure portfolio
    tickers = ["SPY", "QQQ", "IWM"]  # Large cap, tech, small cap
    start_date = "2022-01-01"
    end_date = "2023-12-31"
    initial_capital = 100000.0
    commission = 0.001  # 0.1%
    
    print(f"Portfolio Configuration:")
    print(f"  Tickers: {', '.join(tickers)}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Initial Capital: ${initial_capital:,.0f}")
    print(f"  Commission: {commission*100:.2f}%")
    print(f"  Strategy: Equal-weight, monthly rebalance")
    print()
    
    # Create and run portfolio backtest
    print("Loading data...")
    portfolio = PortfolioBacktester(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission=commission,
    )
    
    portfolio.load_data()
    print()
    
    print("Running backtest...")
    equity_curve = portfolio.run()
    print()
    
    # Calculate metrics
    print("Calculating metrics...")
    metrics = portfolio.calculate_metrics()
    print()
    
    # Calculate SPY benchmark
    print("Loading benchmark (SPY)...")
    benchmark = calculate_benchmark(
        ticker="SPY",
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        aligned_dates=equity_curve.index,
        commission=commission,
    )
    print()
    
    # Display results
    print("=" * 70)
    print("Portfolio Performance Metrics")
    print("=" * 70)
    print()
    
    print(f"Initial Capital:      ${metrics.initial_capital:,.2f}")
    print(f"Final Equity:         ${metrics.final_equity:,.2f}")
    print(f"Total Return:         {metrics.total_return_pct:+.2f}%")
    print(f"CAGR:                 {metrics.cagr_pct:+.2f}%")
    print(f"Sharpe Ratio:         {metrics.sharpe_ratio:.2f}")
    print(f"Max Drawdown:         {metrics.max_drawdown_pct:.2f}%")
    print(f"Volatility (annual):  {metrics.volatility_pct:.2f}%")
    print()
    
    # Benchmark comparison
    if not benchmark.empty:
        benchmark_final = benchmark["BenchmarkEquity"].iloc[-1]
        benchmark_return = ((benchmark_final / initial_capital) - 1) * 100
        
        print("SPY Benchmark:")
        print(f"  Final Value:        ${benchmark_final:,.2f}")
        print(f"  Total Return:       {benchmark_return:+.2f}%")
        print(f"  Outperformance:     {metrics.total_return_pct - benchmark_return:+.2f}%")
        print()
    
    # Asset contributions
    print("=" * 70)
    print("Asset Contributions (% of final equity)")
    print("=" * 70)
    print()
    
    for ticker in tickers:
        contribution = metrics.asset_contributions.get(ticker, 0.0)
        final_value = equity_curve[ticker].iloc[-1]
        print(f"  {ticker:8s}  {contribution:5.1f}%  (${final_value:,.2f})")
    print()
    
    # Correlation matrix
    print("=" * 70)
    print("Correlation Matrix")
    print("=" * 70)
    print()
    print(metrics.correlation_matrix.to_string())
    print()
    
    print("Interpretation:")
    print("  1.0  = Perfect positive correlation")
    print("  0.0  = No correlation")
    print("  -1.0 = Perfect negative correlation")
    print()
    
    # Sample of equity curve
    print("=" * 70)
    print("Sample Equity Curve (first 5 and last 5 days)")
    print("=" * 70)
    print()
    
    # Show first 5 rows
    print("First 5 days:")
    print(equity_curve[["Equity"] + tickers].head().to_string())
    print()
    
    # Show last 5 rows
    print("Last 5 days:")
    print(equity_curve[["Equity"] + tickers].tail().to_string())
    print()
    
    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("For full interactive visualization, use:")
    print("  streamlit run streamlit_app.py")
    print("  (then select 'Multi-Asset Portfolio' mode)")
    print()


if __name__ == "__main__":
    main()
