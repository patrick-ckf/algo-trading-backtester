"""
Backtester - A clean Python algorithmic-trading backtesting system
"""

__version__ = "0.1.0"

from backtester.strategy import Strategy
from backtester.engine import BacktestEngine
from backtester.data import DataLoader

__all__ = ["Strategy", "BacktestEngine", "DataLoader"]
