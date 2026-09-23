"""
End-to-end tests for CLI and dashboard workflows.
Tests complete user paths without live network or browser.
"""

import pytest
import subprocess
import sys
import tempfile
import os
from pathlib import Path

from backtester.data import DataLoader
from backtester.engine import BacktestEngine
from backtester.metrics import PerformanceMetrics
from backtester.strategies.sma_crossover import SMACrossover
from backtester.strategies.rsi_mean_reversion import RSIMeanReversion


@pytest.mark.e2e
def test_cli_sma_sample_data():
    """Test CLI with SMA strategy on sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable, "-m", "backtester",
                "--strategy", "sma",
                "--csv", "data/sample/SPY_sample.csv",
                "--fast-period", "10",
                "--slow-period", "20",
                "--capital", "10000",
                "--output-dir", tmpdir,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "BACKTEST PERFORMANCE SUMMARY" in result.stdout
        assert "Total Return:" in result.stdout
        assert "CAGR:" in result.stdout
        assert "Sharpe Ratio" in result.stdout
        
        # Check output files were created
        output_files = list(Path(tmpdir).glob("equity_curve_*.csv"))
        assert len(output_files) > 0, "No equity curve file created"


@pytest.mark.e2e
def test_cli_rsi_sample_data():
    """Test CLI with RSI strategy on sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable, "-m", "backtester",
                "--strategy", "rsi",
                "--csv", "data/sample/SPY_sample.csv",
                "--rsi-period", "14",
                "--capital", "10000",
                "--output-dir", tmpdir,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "BACKTEST PERFORMANCE SUMMARY" in result.stdout
        assert "Trade Count:" in result.stdout
        assert "Win Rate:" in result.stdout
        
        # Check equity curve file exists
        output_files = list(Path(tmpdir).glob("equity_curve_*.csv"))
        assert len(output_files) > 0


@pytest.mark.e2e
def test_cli_help():
    """Test CLI help command."""
    result = subprocess.run(
        [sys.executable, "-m", "backtester", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    
    assert result.returncode == 0
    assert "Algorithmic Trading Backtesting System" in result.stdout
    assert "--strategy" in result.stdout
    assert "--symbol" in result.stdout


@pytest.mark.e2e
def test_cli_invalid_strategy():
    """Test CLI with invalid strategy."""
    result = subprocess.run(
        [
            sys.executable, "-m", "backtester",
            "--strategy", "invalid_strategy",
            "--csv", "data/sample/SPY_sample.csv",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    
    # Should fail with invalid choice
    assert result.returncode != 0


@pytest.mark.e2e
def test_cli_missing_csv_file():
    """Test CLI with non-existent CSV file."""
    result = subprocess.run(
        [
            sys.executable, "-m", "backtester",
            "--strategy", "sma",
            "--csv", "nonexistent_file.csv",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    
    # Should fail or at least report error
    assert result.returncode != 0 or "Error" in result.stderr or "Error" in result.stdout


@pytest.mark.e2e
def test_dashboard_workflow_sma():
    """Test complete dashboard workflow for SMA strategy."""
    # Simulate what the Streamlit dashboard does
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    assert not data.empty, "Sample data not loaded"
    
    strategy = SMACrossover(fast_period=10, slow_period=20)
    
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size_type="fixed_fraction",
        position_size_value=0.95,
    )
    
    equity_curve = engine.run(strategy, data)
    
    assert not equity_curve.empty, "Equity curve is empty"
    assert "Equity" in equity_curve.columns
    assert len(equity_curve) == len(data)
    
    metrics_calculator = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=engine.trades,
        initial_capital=10000.0,
    )
    metrics = metrics_calculator.calculate_all()
    
    assert "total_return_pct" in metrics
    assert "cagr_pct" in metrics
    assert "max_drawdown_pct" in metrics
    assert "sharpe_ratio" in metrics
    assert "trade_count" in metrics
    assert "win_rate_pct" in metrics
    
    # Verify trades DataFrame can be created
    trades_df = engine.get_trades_df()
    assert trades_df is not None


@pytest.mark.e2e
def test_dashboard_workflow_rsi():
    """Test complete dashboard workflow for RSI strategy."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    assert not data.empty
    
    strategy = RSIMeanReversion(period=14, oversold=30, overbought=70)
    
    engine = BacktestEngine(
        initial_capital=10000.0,
        commission=0.001,
        slippage=0.0005,
        position_size_type="fixed_fraction",
        position_size_value=0.95,
    )
    
    equity_curve = engine.run(strategy, data)
    
    assert not equity_curve.empty
    assert "Equity" in equity_curve.columns
    
    metrics_calculator = PerformanceMetrics(
        equity_curve=equity_curve,
        trades=engine.trades,
        initial_capital=10000.0,
    )
    metrics = metrics_calculator.calculate_all()
    
    # Verify all required metrics are present
    required_metrics = [
        "initial_capital",
        "final_equity",
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe_ratio",
        "trade_count",
        "win_rate_pct",
        "avg_trade_return_pct",
    ]
    
    for metric in required_metrics:
        assert metric in metrics, f"Missing metric: {metric}"


@pytest.mark.e2e
def test_dashboard_workflow_with_different_parameters():
    """Test dashboard workflow with various parameter combinations."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    # Test different capital amounts
    for capital in [5000, 50000, 100000]:
        engine = BacktestEngine(initial_capital=float(capital))
        strategy = SMACrossover(fast_period=10, slow_period=20)
        equity = engine.run(strategy, data)
        assert not equity.empty
        
    # Test different commission rates
    for commission in [0.0, 0.001, 0.01]:
        engine = BacktestEngine(initial_capital=10000.0, commission=commission)
        strategy = SMACrossover(fast_period=10, slow_period=20)
        equity = engine.run(strategy, data)
        assert not equity.empty
        
    # Test different strategy parameters
    for fast, slow in [(5, 10), (20, 50), (50, 100)]:
        if fast < slow:  # Valid combination
            strategy = SMACrossover(fast_period=fast, slow_period=slow)
            engine = BacktestEngine(initial_capital=10000.0)
            equity = engine.run(strategy, data)
            assert not equity.empty


@pytest.mark.e2e
def test_full_pipeline_produces_downloadable_results():
    """Test that full pipeline produces results suitable for download."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    strategy = SMACrossover(fast_period=10, slow_period=20)
    engine = BacktestEngine(initial_capital=10000.0)
    equity_curve = engine.run(strategy, data)
    
    # Test equity curve can be saved to CSV
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        equity_curve.to_csv(f.name)
        temp_file = f.name
    
    try:
        assert os.path.exists(temp_file)
        assert os.path.getsize(temp_file) > 0
    finally:
        os.unlink(temp_file)
    
    # Test trades can be saved to CSV
    trades_df = engine.get_trades_df()
    if not trades_df.empty:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            trades_df.to_csv(f.name, index=False)
            temp_file = f.name
        
        try:
            assert os.path.exists(temp_file)
            assert os.path.getsize(temp_file) > 0
        finally:
            os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
