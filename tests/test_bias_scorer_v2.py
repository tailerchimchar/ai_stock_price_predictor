"""Unit tests for BiasScorer v2: strength-sensitive RSI/ADX, NA weight reduction, label boundaries."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.scoring.v2 import BiasScorerV2


class TestBiasScorerV2StrengthRSI:
    """Strength-sensitive RSI: deeply oversold/overbought have larger impact."""

    def test_deeply_oversold_larger_impact_than_oversold(self):
        # RSI 15 (deeply oversold) -> +0.25; RSI 25 (oversold) -> +0.22
        signals_low = {
            "rsi": 15.0,
            "percent_price_change": 0.0,
            "ma_5": 100.0,
            "ma_20": 99.0,
            "ma_100": 98.0,
            "ma_200": 97.0,
            "last_close": 100.0,
            "adx": 18.0,
        }
        signals_mid = {**signals_low, "rsi": 25.0}
        scorer_low = BiasScorerV2(signals_low)
        scorer_mid = BiasScorerV2(signals_mid)
        _, score_low, ev_low = scorer_low.full_bias_assessment()
        _, score_mid, ev_mid = scorer_mid.full_bias_assessment()
        assert score_low > score_mid
        assert "deeply oversold" in ev_low["rsi"].message or ev_low["rsi"].impact >= 0.22
        assert ev_low["rsi"].impact >= ev_mid["rsi"].impact

    def test_deeply_overbought_larger_impact_than_overbought(self):
        signals_high = {
            "rsi": 85.0,
            "percent_price_change": 0.0,
            "ma_5": 100.0,
            "ma_20": 101.0,
            "ma_100": 102.0,
            "ma_200": 103.0,
            "last_close": 99.0,
            "adx": 18.0,
        }
        signals_mid = {**signals_high, "rsi": 75.0}
        scorer_high = BiasScorerV2(signals_high)
        scorer_mid = BiasScorerV2(signals_mid)
        _, score_high, ev_high = scorer_high.full_bias_assessment()
        _, score_mid, ev_mid = scorer_mid.full_bias_assessment()
        assert score_high < score_mid
        assert ev_high["rsi"].impact <= ev_mid["rsi"].impact


class TestBiasScorerV2LabelBoundaries:
    """Same label thresholds as v1: 0.7, 0.55, 0.45, 0.25."""

    def test_label_from_score_bullish(self):
        scorer = BiasScorerV2({})
        assert scorer.label_from_score(0.70) == "bullish"
        assert scorer.label_from_score(0.85) == "bullish"

    def test_label_from_score_slightly_bullish(self):
        scorer = BiasScorerV2({})
        assert scorer.label_from_score(0.55) == "slightly bullish"
        assert scorer.label_from_score(0.69) == "slightly bullish"

    def test_label_from_score_neutral(self):
        scorer = BiasScorerV2({})
        assert scorer.label_from_score(0.45) == "neutral"
        assert scorer.label_from_score(0.54) == "neutral"
        assert scorer.label_from_score(0.50) == "neutral"

    def test_label_from_score_slightly_bearish(self):
        scorer = BiasScorerV2({})
        assert scorer.label_from_score(0.25) == "slightly bearish"
        assert scorer.label_from_score(0.44) == "slightly bearish"

    def test_label_from_score_bearish(self):
        scorer = BiasScorerV2({})
        assert scorer.label_from_score(0.24) == "bearish"
        assert scorer.label_from_score(0.0) == "bearish"


class TestBiasScorerV2NAWeightReduction:
    """Many indicators NA -> score pulled toward 0.5."""

    def test_few_signals_pulls_toward_neutral(self):
        # Full bullish signals
        full = {
            "rsi": 25.0,
            "percent_price_change": 0.05,
            "ma_5": 100.0,
            "ma_20": 99.0,
            "ma_100": 98.0,
            "ma_200": 97.0,
            "last_close": 100.0,
            "adx": 30.0,
        }
        # Only RSI and price change (no MAs, no ADX)
        sparse = {
            "rsi": 25.0,
            "percent_price_change": 0.05,
            "ma_5": None,
            "ma_20": None,
            "ma_100": None,
            "ma_200": None,
            "last_close": None,
            "adx": None,
        }
        scorer_full = BiasScorerV2(full)
        scorer_sparse = BiasScorerV2(sparse)
        _, score_full, _ = scorer_full.full_bias_assessment()
        _, score_sparse, _ = scorer_sparse.full_bias_assessment()
        assert score_sparse < score_full
        assert 0.4 <= score_sparse <= 0.7  # Damped toward 0.5


class TestBiasScorerV2ADXScaling:
    """Stronger ADX (when > 25) gives slightly larger impact."""

    def test_strong_adx_larger_impact_than_moderate(self):
        # Use a neutral-ish base so scores stay below 1 and ADX scaling is visible
        base = {
            "rsi": 50.0,
            "percent_price_change": 0.01,
            "ma_5": 100.0,
            "ma_20": 100.0,
            "ma_100": 99.0,
            "ma_200": 98.0,
            "last_close": 100.0,
        }
        strong = {**base, "adx": 45.0}
        moderate = {**base, "adx": 28.0}
        scorer_strong = BiasScorerV2(strong)
        scorer_moderate = BiasScorerV2(moderate)
        _, score_strong, ev_strong = scorer_strong.full_bias_assessment()
        _, score_moderate, ev_moderate = scorer_moderate.full_bias_assessment()
        assert score_strong > score_moderate
        assert abs(ev_strong["adx"].impact) >= abs(ev_moderate["adx"].impact)
