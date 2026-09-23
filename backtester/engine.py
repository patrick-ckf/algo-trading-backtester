"""
Backtest engine for executing strategies on historical data.
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import numpy as np

from backtester.strategy import Strategy, Signal


@dataclass
class Trade:
    """Represents a completed trade."""
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float


class BacktestEngine:
    """
    Backtest engine with position tracking and performance metrics.
    Currently supports long-only or long/flat strategies.
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        position_size_type: str = "fixed_fraction",
        position_size_value: float = 0.95,
    ):
        """
        Args:
            initial_capital: Starting cash amount
            commission: Commission rate as decimal (0.001 = 0.1%)
            slippage: Slippage rate as decimal (0.0005 = 0.05%)
            position_size_type: "fixed_fraction" or "fixed_shares"
            position_size_value: Fraction of equity (0-1) or number of shares
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size_type = position_size_type
        self.position_size_value = position_size_value
        
        self.cash = initial_capital
        self.shares = 0
        self.equity_curve: List[float] = []
        self.trades: List[Trade] = []
        self.entry_price: Optional[float] = None
        self.entry_date: Optional[pd.Timestamp] = None
    
    def run(self, strategy: Strategy, data: pd.DataFrame) -> pd.DataFrame:
        """
        Execute the backtest.
        
        Args:
            strategy: Strategy instance to test
            data: OHLCV DataFrame with DatetimeIndex
        
        Returns:
            DataFrame with equity curve and metrics
        """
        strategy.setup(data)
        self.equity_curve = []
        self.trades = []
        
        for i, (date, row) in enumerate(data.iterrows()):
            signal = strategy.on_bar(i, row)
            close_price = row["Close"]
            
            if signal == "BUY" and self.shares == 0:
                self._execute_buy(date, close_price)
            elif signal == "SELL" and self.shares > 0:
                self._execute_sell(date, close_price)
            
            equity = self.cash + self.shares * close_price
            self.equity_curve.append(equity)
        
        strategy.teardown()
        
        equity_df = pd.DataFrame({
            "Date": data.index,
            "Equity": self.equity_curve,
            "Cash": [self.cash] * len(data),
            "Position": [self.shares] * len(data),
        })
        equity_df.set_index("Date", inplace=True)
        
        return equity_df
    
    def _execute_buy(self, date: pd.Timestamp, price: float) -> None:
        """Execute a buy order."""
        effective_price = price * (1 + self.slippage)
        
        if self.position_size_type == "fixed_fraction":
            position_value = self.cash * self.position_size_value
            shares = int(position_value / effective_price)
        else:
            shares = int(self.position_size_value)
        
        if shares <= 0:
            return
        
        cost = shares * effective_price
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost
        
        if total_cost > self.cash:
            shares = int(self.cash / (effective_price * (1 + self.commission)))
            if shares <= 0:
                return
            cost = shares * effective_price
            commission_cost = cost * self.commission
            total_cost = cost + commission_cost
        
        self.cash -= total_cost
        self.shares = shares
        self.entry_price = effective_price
        self.entry_date = date
    
    def _execute_sell(self, date: pd.Timestamp, price: float) -> None:
        """Execute a sell order."""
        if self.shares <= 0 or self.entry_price is None:
            return
        
        effective_price = price * (1 - self.slippage)
        revenue = self.shares * effective_price
        commission_cost = revenue * self.commission
        net_revenue = revenue - commission_cost
        
        pnl = net_revenue - (self.shares * self.entry_price * (1 + self.commission))
        return_pct = (effective_price / self.entry_price - 1) * 100
        
        trade = Trade(
            entry_date=self.entry_date,
            exit_date=date,
            entry_price=self.entry_price,
            exit_price=effective_price,
            shares=self.shares,
            pnl=pnl,
            return_pct=return_pct,
        )
        self.trades.append(trade)
        
        self.cash += net_revenue
        self.shares = 0
        self.entry_price = None
        self.entry_date = None
    
    def get_trades_df(self) -> pd.DataFrame:
        """Return trades as a DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        
        return pd.DataFrame([
            {
                "Entry Date": t.entry_date,
                "Exit Date": t.exit_date,
                "Entry Price": t.entry_price,
                "Exit Price": t.exit_price,
                "Shares": t.shares,
                "PnL": t.pnl,
                "Return %": t.return_pct,
            }
            for t in self.trades
        ])
