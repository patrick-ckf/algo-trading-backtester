"""
Simple Moving Average (SMA) Crossover Strategy.
Generates BUY signal when fast SMA crosses above slow SMA.
Generates SELL signal when fast SMA crosses below slow SMA.
"""

import pandas as pd
from backtester.strategy import Strategy, Signal


class SMACrossover(Strategy):
    """
    SMA Crossover strategy.
    
    Args:
        fast_period: Fast SMA period (default: 50)
        slow_period: Slow SMA period (default: 200)
    """
    
    def __init__(self, fast_period: int = 50, slow_period: int = 200):
        super().__init__(name=f"SMA_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.fast_sma = None
        self.slow_sma = None
        self.position = False
    
    def setup(self, data: pd.DataFrame) -> None:
        """Calculate SMAs once at the start."""
        super().setup(data)
        self.fast_sma = data["Close"].rolling(window=self.fast_period).mean()
        self.slow_sma = data["Close"].rolling(window=self.slow_period).mean()
        self.position = False
    
    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """Generate trading signal based on SMA crossover."""
        if index < self.slow_period:
            return "HOLD"
        
        fast_now = self.fast_sma.iloc[index]
        slow_now = self.slow_sma.iloc[index]
        
        if pd.isna(fast_now) or pd.isna(slow_now):
            return "HOLD"
        
        if index > 0:
            fast_prev = self.fast_sma.iloc[index - 1]
            slow_prev = self.slow_sma.iloc[index - 1]
            
            if not pd.isna(fast_prev) and not pd.isna(slow_prev):
                if fast_prev <= slow_prev and fast_now > slow_now and not self.position:
                    self.position = True
                    return "BUY"
                
                elif fast_prev >= slow_prev and fast_now < slow_now and self.position:
                    self.position = False
                    return "SELL"
        
        return "HOLD"
