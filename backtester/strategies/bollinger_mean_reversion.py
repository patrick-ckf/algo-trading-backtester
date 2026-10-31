"""
Bollinger Bands Mean Reversion Strategy.
BUY when close crosses below the lower band; SELL when close crosses above the middle band.
"""

import pandas as pd
from backtester.strategy import Strategy, Signal


class BollingerMeanReversion(Strategy):
    """
    Long-only mean reversion using Bollinger Bands.

    Args:
        bb_period: Rolling window for SMA and standard deviation (default: 20)
        bb_std: Standard deviation multiplier for bands (default: 2.0)
    """

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0):
        super().__init__(name=f"BB_{bb_period}_{bb_std}")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.middle_band = None
        self.upper_band = None
        self.lower_band = None
        self.position = False

    def setup(self, data: pd.DataFrame) -> None:
        """Calculate Bollinger Bands once at the start."""
        super().setup(data)
        close = data["Close"]
        self.middle_band = close.rolling(window=self.bb_period).mean()
        rolling_std = close.rolling(window=self.bb_period).std()
        self.upper_band = self.middle_band + self.bb_std * rolling_std
        self.lower_band = self.middle_band - self.bb_std * rolling_std
        self.position = False

    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """Generate mean-reversion signals at band touches."""
        if index < self.bb_period:
            return "HOLD"

        middle = self.middle_band.iloc[index]
        lower = self.lower_band.iloc[index]
        close = row["Close"]

        if pd.isna(middle) or pd.isna(lower):
            return "HOLD"

        if index > 0:
            close_prev = self.data.iloc[index - 1]["Close"]
            lower_prev = self.lower_band.iloc[index - 1]
            middle_prev = self.middle_band.iloc[index - 1]

            if not pd.isna(lower_prev) and not pd.isna(middle_prev):
                if (
                    close_prev >= lower_prev
                    and close < lower
                    and not self.position
                ):
                    self.position = True
                    return "BUY"

                if (
                    close_prev <= middle_prev
                    and close > middle
                    and self.position
                ):
                    self.position = False
                    return "SELL"

        return "HOLD"
