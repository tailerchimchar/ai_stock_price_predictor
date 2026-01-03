import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.BiasScorer import BiasScorer


class TestBiasScorer:
  """Unit tests for BiasScorer using synthetic signal dicts."""
  
  def test_strongly_bullish_signal(self):
    """Test a clearly bullish scenario."""
    signals = {
      'rsi': 25.0,  # Oversold
      'price_change': 15.5,  # Large positive
      'ma_5': 660.0,
      'ma_20': 658.0,  # ma_5 > ma_20
      'last_close': 665.0,  # Above SMA20
      'adx': 35.0  # Strong uptrend
    }
    scorer = BiasScorer(signals)
    label, score, evidence = scorer.full_bias_assessment()
    
    assert label == 'bullish'
    assert score >= 0.7
    assert 'RSI 25.0 oversold' in evidence['rsi']
    assert 'strong uptrend' in evidence['adx']
  
  def test_strongly_bearish_signal(self):
    """Test a clearly bearish scenario."""
    signals = {
      'rsi': 75.0,  # Overbought
      'price_change': -12.3,  # Negative
      'ma_5': 655.0,
      'ma_20': 660.0,  # ma_5 < ma_20
      'last_close': 650.0,  # Below SMA20
      'adx': 28.0  # Strong downtrend
    }
    scorer = BiasScorer(signals)
    label, score, evidence = scorer.full_bias_assessment()
    
    assert label == 'bearish'
    assert score <= 0.3
    assert 'RSI 75.0 overbought' in evidence['rsi']
    assert 'strong downtrend' in evidence['adx']
  
  def test_neutral_signal_mixed_indicators(self):
    """Test a neutral scenario with mixed signals."""
    signals = {
      'rsi': 50.0,  # Neutral RSI
      'price_change': 0.0,  # Flat price change keeps score near base
      'ma_5': 658.0,
      'ma_20': 658.5,  # Slight downward cross
      'last_close': 659.0,  # Above SMA20
      'adx': None  # Weak/no trend
    }
    scorer = BiasScorer(signals)
    label, score, evidence = scorer.full_bias_assessment()
    
    assert label == 'neutral'
    assert 0.3 < score < 0.7
    assert 'ADX not available' in evidence['adx']

  def test_short_window_outputs_no_nan(self):
    """Short window/empty indicators should surface availability messages, no NaN."""
    signals = {
      'rsi': None,
      'percent_price_change': None,
      'ma_5': None,
      'ma_20': None,
      'ma_100': None,
      'ma_200': None,
      'last_close': None,
      'adx': None,
      'window': 1,
    }
    scorer = BiasScorer(signals)
    label, score, evidence = scorer.full_bias_assessment()

    assert label == 'neutral'
    for v in evidence.values():
      assert 'nan' not in str(v).lower()
    assert evidence['rsi'].startswith('RSI unavailable')
    assert evidence['percent_price_change'].startswith('5 day return unavailable')
    assert evidence['ma_short_term'] == 'MA5/MA20 unavailable'
    assert evidence['ma_long_term'] == 'MA100/MA200 unavailable'
    assert evidence['close_vs_sma20'] == 'Close/SMA20 unavailable'
    assert 'ADX not available' in evidence['adx']

  def test_decimal_formatting_and_no_nan(self):
    """Check evidence formatting rounds to one decimal and stays clean."""
    signals = {
      'rsi': 50.04,
      'percent_price_change': 0.021,  # 2.1%
      'ma_5': 10.126,
      'ma_20': 10.0,
      'ma_100': 9.8,
      'ma_200': 9.7,
      'last_close': 10.2,
      'adx': 30.0,
      'window': 30,
    }
    scorer = BiasScorer(signals)
    label, score, evidence = scorer.full_bias_assessment()

    assert label == 'bullish'
    assert 'RSI 50.0 neutral' == evidence['rsi']
    assert evidence['percent_price_change'].startswith('5 day return: 2.10')
    assert 'Ma5 10.1 above Ma20 10.0' in evidence['ma_short_term']
    assert 'Ma100 9.8 above Ma200 9.7' in evidence['ma_long_term']
    assert 'Close 10.2 above SMA20 10.0' in evidence['close_vs_sma20']
    assert 'strong uptrend' in evidence['adx']
    for v in evidence.values():
      assert 'nan' not in str(v).lower()
