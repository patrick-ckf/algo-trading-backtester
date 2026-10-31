"""
Example trading strategies.
"""

from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion
from backtester.strategies.donchian_breakout import DonchianBreakout
from backtester.strategies.macd_crossover import MACDCrossover
from backtester.strategies.bollinger_mean_reversion import BollingerMeanReversion

__all__ = [
    "SMACrossover",
    "RSIMeanReversion",
    "DonchianBreakout",
    "MACDCrossover",
    "BollingerMeanReversion",
]
