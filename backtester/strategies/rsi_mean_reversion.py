"""
RSI Mean Reversion Strategy.
Generates BUY signal when RSI crosses below oversold threshold.
Generates SELL signal when RSI crosses above overbought threshold.
"""

import pandas as pd
import numpy as np
from backtester.strategy import Strategy, Signal


class RSIMeanReversion(Strategy):
    """
    RSI Mean Reversion strategy.
    
    Args:
        period: RSI calculation period (default: 14)
        oversold: Oversold threshold (default: 30)
        overbought: Overbought threshold (default: 70)
    """
    
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__(name=f"RSI_{period}")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.rsi = None
        self.position = False
    
    def setup(self, data: pd.DataFrame) -> None:
        """Calculate RSI once at the start."""
        super().setup(data)
        self.rsi = self._calculate_rsi(data["Close"], self.period)
        self.position = False
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """Generate trading signal based on RSI levels."""
        if index < self.period:
            return "HOLD"
        
        rsi_now = self.rsi.iloc[index]
        
        if pd.isna(rsi_now):
            return "HOLD"
        
        if index > 0:
            rsi_prev = self.rsi.iloc[index - 1]
            
            if not pd.isna(rsi_prev):
                if rsi_prev >= self.oversold and rsi_now < self.oversold and not self.position:
                    self.position = True
                    return "BUY"
                
                elif rsi_prev <= self.overbought and rsi_now > self.overbought and self.position:
                    self.position = False
                    return "SELL"
        
        return "HOLD"
