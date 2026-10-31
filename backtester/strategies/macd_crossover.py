"""
MACD Crossover Strategy.
BUY when MACD line crosses above signal line; SELL when it crosses below (long-only).
"""

import pandas as pd
from backtester.strategy import Strategy, Signal


class MACDCrossover(Strategy):
    """
    Classic MACD crossover strategy using EMA-based MACD and signal lines.

    Args:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal EMA period (default: 9)
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        super().__init__(name=f"MACD_{fast_period}_{slow_period}_{signal_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.macd_line = None
        self.signal_line = None
        self.position = False

    def setup(self, data: pd.DataFrame) -> None:
        """Calculate MACD and signal lines once at the start."""
        super().setup(data)
        close = data["Close"]
        fast_ema = close.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close.ewm(span=self.slow_period, adjust=False).mean()
        self.macd_line = fast_ema - slow_ema
        self.signal_line = self.macd_line.ewm(span=self.signal_period, adjust=False).mean()
        self.position = False

    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """Generate trading signal on MACD / signal crossovers."""
        warmup = max(self.slow_period, self.signal_period) + self.signal_period
        if index < warmup:
            return "HOLD"

        macd_now = self.macd_line.iloc[index]
        signal_now = self.signal_line.iloc[index]

        if pd.isna(macd_now) or pd.isna(signal_now):
            return "HOLD"

        if index > 0:
            macd_prev = self.macd_line.iloc[index - 1]
            signal_prev = self.signal_line.iloc[index - 1]

            if not pd.isna(macd_prev) and not pd.isna(signal_prev):
                if (
                    macd_prev <= signal_prev
                    and macd_now > signal_now
                    and not self.position
                ):
                    self.position = True
                    return "BUY"

                if (
                    macd_prev >= signal_prev
                    and macd_now < signal_now
                    and self.position
                ):
                    self.position = False
                    return "SELL"

        return "HOLD"
