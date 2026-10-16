"""
Donchian Channel Breakout Strategy.
BUY when close breaks above the prior N-day high; SELL when close breaks below the prior N-day low.
"""

import pandas as pd
from backtester.strategy import Strategy, Signal


class DonchianBreakout(Strategy):
    """
    Donchian-style breakout strategy (Turtle-style entry/exit channels).

    Args:
        channel_period: Lookback for highest high / lowest low (default: 20)
    """

    def __init__(self, channel_period: int = 20):
        super().__init__(name=f"Donchian_{channel_period}")
        self.channel_period = channel_period
        self.upper_channel = None
        self.lower_channel = None
        self.position = False

    def setup(self, data: pd.DataFrame) -> None:
        """Calculate Donchian channels (prior bar excludes current bar)."""
        super().setup(data)
        rolling_high = data["High"].rolling(window=self.channel_period).max()
        rolling_low = data["Low"].rolling(window=self.channel_period).min()
        self.upper_channel = rolling_high.shift(1)
        self.lower_channel = rolling_low.shift(1)
        self.position = False

    def on_bar(self, index: int, row: pd.Series) -> Signal:
        """Generate trading signal on channel breakouts."""
        if index < self.channel_period:
            return "HOLD"

        upper = self.upper_channel.iloc[index]
        lower = self.lower_channel.iloc[index]

        if pd.isna(upper) or pd.isna(lower):
            return "HOLD"

        close = row["Close"]

        if close > upper and not self.position:
            self.position = True
            return "BUY"

        if close < lower and self.position:
            self.position = False
            return "SELL"

        return "HOLD"
