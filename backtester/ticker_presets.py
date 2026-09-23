"""
Ticker presets for quick symbol selection in the dashboard.
This module provides categorized symbol groups and descriptions.
"""

from typing import Dict, List, Tuple


# Categorized ticker presets with Traditional Chinese labels
TICKER_GROUPS: List[Tuple[str, List[str]]] = [
    ("美股指數/ETF", ["SPY", "QQQ", "DIA", "IWM", "VOO", "IVV"]),
    ("板塊 ETF", ["XLF", "XLK", "XLE", "XLV", "XLI"]),
    ("港股/亞洲", ["2800.HK", "2828.HK", "EWJ", "FXI", "EEM", "VGK"]),
    ("債券/商品/波動", ["TLT", "IEF", "GLD", "USO", "VXX"]),
]


# Symbol descriptions (English / Traditional Chinese)
TICKER_DESCRIPTIONS: Dict[str, str] = {
    # US Indices / ETFs
    "SPY": "S&P 500 ETF / 標普 500 指數",
    "QQQ": "Nasdaq-100 ETF / 納指 100 ETF",
    "DIA": "Dow Jones ETF / 道瓊指數 ETF",
    "IWM": "Russell 2000 ETF / 羅素 2000 小型股",
    "VOO": "Vanguard S&P 500 ETF",
    "IVV": "iShares S&P 500 ETF",
    
    # Sector ETFs
    "XLF": "Financial Sector ETF / 金融板塊",
    "XLK": "Technology Sector ETF / 科技板塊",
    "XLE": "Energy Sector ETF / 能源板塊",
    "XLV": "Healthcare Sector ETF / 醫療保健板塊",
    "XLI": "Industrial Sector ETF / 工業板塊",
    
    # Hong Kong / Asia
    "2800.HK": "Tracker Fund of Hong Kong / 盈富基金（港股恆指）",
    "2828.HK": "Hang Seng H-Share Index ETF / 恆生 H 股 ETF",
    "EWJ": "Japan ETF / 日本 ETF",
    "FXI": "China Large-Cap ETF / 中國大型股 ETF",
    "EEM": "Emerging Markets ETF / 新興市場 ETF",
    "VGK": "Europe ETF / 歐洲 ETF",
    
    # Bonds / Commodities / Volatility
    "TLT": "20+ Year Treasury ETF / 長期美債 ETF",
    "IEF": "7-10 Year Treasury ETF / 中期美債 ETF",
    "GLD": "Gold ETF / 黃金 ETF",
    "USO": "US Oil Fund / 原油 ETF",
    "VXX": "Volatility Index ETF / 波動率 ETF (注意：可能不穩定)",
}


def get_flat_ticker_list() -> List[str]:
    """Return a flat list of all preset tickers."""
    tickers = []
    for _, group_tickers in TICKER_GROUPS:
        tickers.extend(group_tickers)
    return tickers


def get_ticker_description(symbol: str) -> str:
    """Get description for a ticker symbol."""
    return TICKER_DESCRIPTIONS.get(symbol, "")


def get_grouped_ticker_options() -> List[str]:
    """
    Return a flat list of ticker options with group separators.
    Format suitable for Streamlit selectbox with disabled separator options.
    """
    options = ["──── 手動輸入 / Manual Input ────"]
    
    for group_name, tickers in TICKER_GROUPS:
        options.append(f"──── {group_name} ────")
        options.extend(tickers)
    
    return options


def is_separator(option: str) -> bool:
    """Check if an option string is a separator."""
    return option.startswith("────")
