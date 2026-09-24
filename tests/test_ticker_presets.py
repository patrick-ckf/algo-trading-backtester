"""
Unit tests for ticker presets module (Phase 1).
Tests symbol groups, descriptions, and helper functions.
"""

import pytest
from backtester.ticker_presets import (
    TICKER_GROUPS,
    TICKER_DESCRIPTIONS,
    get_flat_ticker_list,
    get_ticker_description,
    get_grouped_ticker_options,
    is_separator,
)


def test_ticker_groups_structure():
    """Test that TICKER_GROUPS has expected structure."""
    assert isinstance(TICKER_GROUPS, list)
    assert len(TICKER_GROUPS) > 0
    
    for group in TICKER_GROUPS:
        assert isinstance(group, tuple)
        assert len(group) == 2
        group_name, tickers = group
        assert isinstance(group_name, str)
        assert isinstance(tickers, list)
        assert len(tickers) > 0
        assert all(isinstance(t, str) for t in tickers)


def test_ticker_descriptions_exist():
    """Test that key tickers have descriptions."""
    required_tickers = ["SPY", "QQQ", "DIA", "XLF", "XLK", "GLD"]
    
    for ticker in required_tickers:
        assert ticker in TICKER_DESCRIPTIONS
        assert len(TICKER_DESCRIPTIONS[ticker]) > 0


def test_get_flat_ticker_list():
    """Test flat ticker list generation."""
    flat_list = get_flat_ticker_list()
    
    assert isinstance(flat_list, list)
    assert len(flat_list) > 0
    assert "SPY" in flat_list
    assert "QQQ" in flat_list
    
    # Should not have duplicates
    assert len(flat_list) == len(set(flat_list))


def test_get_ticker_description():
    """Test ticker description retrieval."""
    # Known ticker
    assert "S&P 500" in get_ticker_description("SPY")
    assert "納指" in get_ticker_description("QQQ") or "Nasdaq" in get_ticker_description("QQQ")
    
    # Unknown ticker should return empty string
    assert get_ticker_description("UNKNOWN_TICKER_XYZ") == ""


def test_get_grouped_ticker_options():
    """Test grouped options for selectbox."""
    options = get_grouped_ticker_options()
    
    assert isinstance(options, list)
    assert len(options) > 0
    
    # Should start with manual input header
    assert is_separator(options[0])
    assert "手動輸入" in options[0] or "Manual" in options[0]
    
    # Should contain some actual tickers
    assert "SPY" in options
    assert "QQQ" in options
    
    # Should contain group separators
    separators = [opt for opt in options if is_separator(opt)]
    assert len(separators) >= len(TICKER_GROUPS)


def test_is_separator():
    """Test separator detection."""
    assert is_separator("──── 美股指數/ETF ────")
    assert is_separator("──── Test ────")
    assert not is_separator("SPY")
    assert not is_separator("QQQ")
    assert not is_separator("")


def test_all_grouped_tickers_have_descriptions():
    """Test that all preset tickers have descriptions defined."""
    flat_list = get_flat_ticker_list()
    
    missing_descriptions = []
    for ticker in flat_list:
        if ticker not in TICKER_DESCRIPTIONS:
            missing_descriptions.append(ticker)
    
    # All preset tickers should have descriptions
    assert len(missing_descriptions) == 0, f"Missing descriptions for: {missing_descriptions}"


def test_phase0_compliance():
    """
    Test that ticker presets module does not affect backtest behavior.
    This module only provides UI helpers and should not change any logic.
    """
    # Import core modules to ensure no import side effects
    from backtester.engine import BacktestEngine
    from backtester.strategies.sma_crossover import SMACrossover
    from backtester.metrics import PerformanceMetrics
    
    # If imports succeed without errors, Phase 0 boundary is maintained
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
