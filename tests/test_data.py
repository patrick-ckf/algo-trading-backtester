"""
Unit tests for data loading and management.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from pathlib import Path

from backtester.data import DataLoader


def test_data_loader_initialization():
    """Test DataLoader initializes with correct cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DataLoader(cache_dir=tmpdir)
        assert loader.cache_dir == Path(tmpdir)
        assert loader.cache_dir.exists()


def test_load_csv_valid():
    """Test loading valid CSV file."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    assert not data.empty
    assert "Open" in data.columns
    assert "High" in data.columns
    assert "Low" in data.columns
    assert "Close" in data.columns
    assert "Volume" in data.columns
    assert isinstance(data.index, pd.DatetimeIndex)


def test_load_csv_sorted_by_date():
    """Test that loaded CSV is sorted by date."""
    loader = DataLoader()
    data = loader.load_csv("data/sample/SPY_sample.csv")
    
    # Check dates are ascending
    assert (data.index[1:] >= data.index[:-1]).all()


def test_load_csv_missing_columns():
    """Test error handling for CSV with missing required columns."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Open,High,Low\n")
        f.write("2020-01-01,100,101,99\n")
        temp_file = f.name
    
    try:
        loader = DataLoader()
        with pytest.raises(ValueError, match="Missing required columns"):
            loader.load_csv(temp_file)
    finally:
        os.unlink(temp_file)


def test_load_csv_wrong_column_names():
    """Test error for CSV with wrong column names."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Price,HighPrice,LowPrice,ClosePrice,Vol\n")
        f.write("2020-01-01,100,101,99,100,1000\n")
        temp_file = f.name
    
    try:
        loader = DataLoader()
        with pytest.raises(ValueError, match="Missing required columns"):
            loader.load_csv(temp_file)
    finally:
        os.unlink(temp_file)


def test_fetch_yahoo_returns_dataframe():
    """Test Yahoo Finance fetch returns valid DataFrame structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DataLoader(cache_dir=tmpdir)
        
        try:
            # Try to fetch real data (may fail if offline)
            data = loader.fetch_yahoo("SPY", "2023-01-01", "2023-01-31", use_cache=False)
            
            assert isinstance(data, pd.DataFrame)
            assert "Open" in data.columns
            assert "High" in data.columns
            assert "Low" in data.columns
            assert "Close" in data.columns
            assert "Volume" in data.columns
            assert isinstance(data.index, pd.DatetimeIndex)
            assert len(data) > 0
            
        except Exception as e:
            # If offline or API fails, skip test
            pytest.skip(f"Yahoo Finance unavailable: {e}")


def test_fetch_yahoo_caching():
    """Test that Yahoo Finance data is cached correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DataLoader(cache_dir=tmpdir)
        
        try:
            # First fetch (should download)
            data1 = loader.fetch_yahoo("SPY", "2023-01-01", "2023-01-31", use_cache=True)
            
            # Check cache file was created
            cache_files = list(Path(tmpdir).glob("*.csv"))
            assert len(cache_files) > 0
            
            # Second fetch (should use cache)
            data2 = loader.fetch_yahoo("SPY", "2023-01-01", "2023-01-31", use_cache=True)
            
            # Data should be identical
            pd.testing.assert_frame_equal(data1, data2)
            
        except Exception:
            pytest.skip("Yahoo Finance unavailable")


def test_fetch_yahoo_invalid_symbol():
    """Test error handling for invalid symbol."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = DataLoader(cache_dir=tmpdir)
        
        try:
            with pytest.raises(ValueError, match="No data returned"):
                loader.fetch_yahoo("INVALID_SYMBOL_XYZ123", "2023-01-01", "2023-01-31")
        except Exception:
            pytest.skip("Yahoo Finance unavailable")


def test_load_csv_file_not_found():
    """Test error handling for non-existent file."""
    loader = DataLoader()
    
    with pytest.raises(FileNotFoundError):
        loader.load_csv("nonexistent_file.csv")


def test_load_csv_with_custom_data():
    """Test loading CSV with custom test data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        f.write("2020-01-01,100.0,101.0,99.0,100.5,1000000\n")
        f.write("2020-01-02,100.5,102.0,100.0,101.5,1100000\n")
        f.write("2020-01-03,101.5,103.0,101.0,102.0,1200000\n")
        temp_file = f.name
    
    try:
        loader = DataLoader()
        data = loader.load_csv(temp_file)
        
        assert len(data) == 3
        assert data.iloc[0]["Close"] == 100.5
        assert data.iloc[1]["Close"] == 101.5
        assert data.iloc[2]["Close"] == 102.0
        assert data.iloc[0]["Volume"] == 1000000
        
    finally:
        os.unlink(temp_file)


def test_data_loader_cache_directory_creation():
    """Test that cache directory is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = os.path.join(tmpdir, "nested", "cache", "dir")
        loader = DataLoader(cache_dir=cache_path)
        
        assert os.path.exists(cache_path)
        assert os.path.isdir(cache_path)


def test_load_csv_empty_file():
    """Test handling of empty CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        temp_file = f.name
    
    try:
        loader = DataLoader()
        data = loader.load_csv(temp_file)
        assert len(data) == 0
    finally:
        os.unlink(temp_file)


def test_load_csv_with_nan_close_dropped():
    """
    Regression test: CSV with NaN Close values should be cleaned.
    This simulates Yahoo Finance returning NaN Close on recent dates.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        f.write("2020-01-01,100.0,101.0,99.0,100.5,1000000\n")
        f.write("2020-01-02,100.5,102.0,100.0,101.5,1100000\n")
        f.write("2020-01-03,101.5,103.0,101.0,nan,1200000\n")  # NaN Close
        temp_file = f.name
    
    try:
        loader = DataLoader()
        data = loader.load_csv(temp_file)
        
        # Should drop the row with NaN Close
        assert len(data) == 2
        assert data.iloc[0]["Close"] == 100.5
        assert data.iloc[1]["Close"] == 101.5
        # Should not contain any NaN Close values
        assert not data["Close"].isna().any()
        
    finally:
        os.unlink(temp_file)


def test_load_csv_with_multiple_nan_columns():
    """Test cleaning when multiple OHLCV columns have NaN."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Date,Open,High,Low,Close,Volume\n")
        f.write("2020-01-01,100.0,101.0,99.0,100.5,1000000\n")
        f.write("2020-01-02,nan,102.0,100.0,101.5,1100000\n")  # NaN Open
        f.write("2020-01-03,101.5,103.0,101.0,102.0,nan\n")   # NaN Volume
        f.write("2020-01-04,102.0,103.5,101.5,102.5,1300000\n")
        temp_file = f.name
    
    try:
        loader = DataLoader()
        data = loader.load_csv(temp_file)
        
        # Should drop rows with any NaN in OHLCV
        assert len(data) == 2
        assert data.iloc[0]["Close"] == 100.5
        assert data.iloc[1]["Close"] == 102.5
        
        # Verify no NaN in any OHLCV column
        assert not data["Open"].isna().any()
        assert not data["High"].isna().any()
        assert not data["Low"].isna().any()
        assert not data["Close"].isna().any()
        assert not data["Volume"].isna().any()
        
    finally:
        os.unlink(temp_file)


def test_clean_ohlcv_trailing_nan():
    """Test the _clean_ohlcv method directly with trailing NaN."""
    loader = DataLoader()
    
    # Create DataFrame with trailing NaN (simulates Yahoo Finance bug)
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "Open": [100.0, 101.0, 102.0, 103.0, np.nan],
        "High": [101.0, 102.0, 103.0, 104.0, np.nan],
        "Low": [99.0, 100.0, 101.0, 102.0, np.nan],
        "Close": [100.5, 101.5, 102.5, 103.5, np.nan],
        "Volume": [1000000, 1100000, 1200000, 1300000, np.nan],
    }, index=dates)
    df.index.name = "Date"
    
    cleaned = loader._clean_ohlcv(df)
    
    # Should drop the last row with NaN
    assert len(cleaned) == 4
    assert cleaned.iloc[-1]["Close"] == 103.5
    assert not cleaned["Close"].isna().any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
