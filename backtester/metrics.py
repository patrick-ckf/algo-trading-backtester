"""
Performance metrics calculation for backtesting results.
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from backtester.engine import Trade


def calculate_buy_and_hold(
    data: pd.DataFrame,
    initial_capital: float,
    commission: float = 0.0,
) -> pd.DataFrame:
    """
    Calculate buy-and-hold benchmark equity curve.
    
    Buys on first bar, holds until last bar, applies commission at entry.
    
    Args:
        data: OHLCV DataFrame with Close prices
        initial_capital: Starting capital
        commission: Commission rate (default 0 for fair comparison, or match strategy commission)
    
    Returns:
        DataFrame with Date index and BuyHoldEquity column
    """
    if data.empty or "Close" not in data.columns:
        return pd.DataFrame()
    
    first_close = data["Close"].iloc[0]
    shares = int((initial_capital * (1 - commission)) / first_close)
    
    if shares <= 0:
        return pd.DataFrame()
    
    equity_series = shares * data["Close"]
    
    return pd.DataFrame({
        "BuyHoldEquity": equity_series
    }, index=data.index)


class PerformanceMetrics:
    """Calculate and display performance metrics for backtest results."""
    
    def __init__(
        self,
        equity_curve: pd.DataFrame,
        trades: List[Trade],
        initial_capital: float,
        risk_free_rate: float = 0.0,
        buy_hold_curve: Optional[pd.DataFrame] = None,
    ):
        """
        Args:
            equity_curve: DataFrame with Date index and Equity column
            trades: List of completed trades
            initial_capital: Starting capital
            risk_free_rate: Annual risk-free rate for Sharpe calculation
            buy_hold_curve: Optional buy-and-hold equity curve for comparison
        """
        self.equity_curve = equity_curve
        self.trades = trades
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.buy_hold_curve = buy_hold_curve
    
    def calculate_all(self) -> Dict[str, float]:
        """Calculate all performance metrics."""
        metrics = {}
        
        if self.equity_curve.empty or "Equity" not in self.equity_curve.columns:
            return metrics
        
        equity = self.equity_curve["Equity"]
        
        # Use last finite equity value to avoid NaN propagation
        finite_equity = equity[equity.notna()]
        if finite_equity.empty:
            return metrics
        
        final_equity = finite_equity.iloc[-1]
        
        metrics["initial_capital"] = self.initial_capital
        metrics["final_equity"] = final_equity
        metrics["total_return_pct"] = ((final_equity / self.initial_capital) - 1) * 100
        
        years = len(finite_equity) / 252.0
        if years > 0:
            metrics["cagr_pct"] = (((final_equity / self.initial_capital) ** (1 / years)) - 1) * 100
        else:
            metrics["cagr_pct"] = 0.0
        
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100
        metrics["max_drawdown_pct"] = drawdown.min()
        
        daily_returns = equity.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() != 0:
            excess_return = daily_returns.mean() - (self.risk_free_rate / 252)
            metrics["sharpe_ratio"] = (excess_return / daily_returns.std()) * np.sqrt(252)
        else:
            metrics["sharpe_ratio"] = 0.0
        
        metrics["trade_count"] = len(self.trades)
        if self.trades:
            winning_trades = [t for t in self.trades if t.pnl > 0]
            metrics["win_rate_pct"] = (len(winning_trades) / len(self.trades)) * 100
            metrics["avg_trade_return_pct"] = np.mean([t.return_pct for t in self.trades])
        else:
            metrics["win_rate_pct"] = 0.0
            metrics["avg_trade_return_pct"] = 0.0
        
        # Buy-and-hold benchmark metrics
        if self.buy_hold_curve is not None and not self.buy_hold_curve.empty:
            buy_hold_equity = self.buy_hold_curve["BuyHoldEquity"]
            buy_hold_final = buy_hold_equity.iloc[-1]
            metrics["buy_hold_final"] = buy_hold_final
            metrics["buy_hold_return_pct"] = ((buy_hold_final / self.initial_capital) - 1) * 100
        else:
            metrics["buy_hold_final"] = 0.0
            metrics["buy_hold_return_pct"] = 0.0
        
        return metrics
    
    def print_summary(self) -> None:
        """Print formatted performance summary."""
        metrics = self.calculate_all()
        
        print("\n" + "=" * 60)
        print("BACKTEST PERFORMANCE SUMMARY")
        print("=" * 60)
        
        if not metrics:
            print("No metrics available.")
            return
        
        print(f"Initial Capital:        ${metrics['initial_capital']:,.2f}")
        print(f"Final Equity:           ${metrics['final_equity']:,.2f}")
        print(f"Total Return:           {metrics['total_return_pct']:.2f}%")
        print(f"CAGR:                   {metrics['cagr_pct']:.2f}%")
        print(f"Max Drawdown:           {metrics['max_drawdown_pct']:.2f}%")
        print(f"Sharpe Ratio (252):     {metrics['sharpe_ratio']:.2f}")
        print(f"\nTrade Count:            {metrics['trade_count']}")
        print(f"Win Rate:               {metrics['win_rate_pct']:.2f}%")
        print(f"Avg Trade Return:       {metrics['avg_trade_return_pct']:.2f}%")
        print("=" * 60 + "\n")
