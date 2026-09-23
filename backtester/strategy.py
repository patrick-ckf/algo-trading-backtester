"""
Base Strategy class for defining trading strategies.
"""

from abc import ABC, abstractmethod
from typing import Literal
import pandas as pd


Signal = Literal["BUY", "SELL", "HOLD"]


class Strategy(ABC):
    """
    Base class for trading strategies.
    
    Subclasses must implement:
    - on_bar: Called for each bar to generate trading signals
    """
    
    def __init__(self, name: str = "Strategy"):
        self.name = name
        self.data: pd.DataFrame = None
    
    def setup(self, data: pd.DataFrame) -> None:
        """
        Called once before backtesting starts.
        Use this to prepare indicators or state.
        """
        self.data = data.copy()
    
    @abstractmethod
    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """
        Called for each bar in the backtest.
        
        Args:
            index: Current bar index in self.data
            row: Current bar data (OHLCV)
        
        Returns:
            Signal: "BUY", "SELL", or "HOLD"
        """
        pass
    
    def teardown(self) -> None:
        """Called after backtesting completes."""
        pass
