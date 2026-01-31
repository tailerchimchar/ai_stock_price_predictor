"""
BiasScorer v3: v2 logic + BBands and MACD impacts; same labels.
Consumes signals from feature_bars (features jsonb) or StockSignals.
"""

from app.stock_response_model import EvidenceItemModel

# Reuse v2 constants
from src.scoring.v2 import (
    ADX_STRONG_THRESHOLD,
    ADX_WEAK_THRESHOLD,
    IMPACT_ADX_BASE,
    IMPACT_CLOSE_VS_SMA20,
    IMPACT_MA_LONG_TERM,
    IMPACT_MA_SHORT_TERM,
    IMPACT_PRICE_CHANGE,
    SCORE_CONTRIBUTING_KEYS as V2_CONTRIBUTING_KEYS,
    _adx_strength_factor,
    _rsi_impact,
)

# v3 additional impacts
IMPACT_BBANDS = 0.05
IMPACT_MACD = 0.05

# v3: same as v2 plus bbands and macd for NA weight count
SCORE_CONTRIBUTING_KEYS_V3 = V2_CONTRIBUTING_KEYS + ("bbands", "macd")


class BiasScorerV3:
    """Same interface as v2; adds BBands and MACD evidence."""

    def __init__(self, signals):
        self.signals = signals
        self.evidence = {}

    def _fmt(self, value: float) -> str:
        return f"{value:.1f}"

    def _has(self, value) -> bool:
        return value is not None and value == value

    def _count_available_signals(self) -> int:
        """Count how many of v3 score-contributing signals are present."""
        count = 0
        if self._has(self.signals.get("rsi")):
            count += 1
        pct = self.signals.get("percent_price_change")
        if not self._has(pct) and self._has(self.signals.get("price_change")):
            pct = self.signals.get("price_change") / 100
        if self._has(pct):
            count += 1
        if self._has(self.signals.get("ma_5")) and self._has(self.signals.get("ma_20")):
            count += 1
        if self._has(self.signals.get("ma_100")) and self._has(self.signals.get("ma_200")):
            count += 1
        if self._has(self.signals.get("last_close")) and self._has(self.signals.get("ma_20")):
            count += 1
        if self._has(self.signals.get("adx")):
            count += 1
        if self._has(self.signals.get("bbands_upper")) and self._has(self.signals.get("bbands_lower")) and self._has(self.signals.get("last_close")):
            count += 1
        if self._has(self.signals.get("macd_12_26_9")):
            count += 1
        return count

    def score_from_signals(self) -> tuple[float, dict]:
        raw_score = 0.5
        evidence = {}
        pct = self.signals.get("percent_price_change")
        if not self._has(pct) and self._has(self.signals.get("price_change")):
            pct = self.signals.get("price_change") / 100
        ma20 = self.signals.get("ma_20")

        # --- RSI (strength-sensitive, same as v2) ---
        rsi = self.signals.get("rsi")
        if not self._has(rsi):
            evidence["rsi"] = EvidenceItemModel(
                key="rsi", message="RSI unavailable, time period is too short", impact=0.0, direction=None
            )
        else:
            impact, suffix = _rsi_impact(rsi)
            raw_score += impact
            if impact > 0:
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} {suffix}", value=rsi, impact=impact, direction="bullish"
                )
            elif impact < 0:
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} {suffix}", value=rsi, impact=impact, direction="bearish"
                )
            else:
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} neutral", value=rsi, impact=0.0, direction="neutral"
                )

        # --- Price change ---
        if not self._has(pct):
            evidence["percent_price_change_5_days"] = EvidenceItemModel(
                key="percent_price_change_5_days", message="Price change unavailable, time period is too short"
            )
        elif pct > 0:
            raw_score += IMPACT_PRICE_CHANGE
            evidence["percent_price_change_5_days"] = EvidenceItemModel(
                key="percent_price_change_5_days",
                message=f"Price change {pct*100:.2f}% positive",
                value=pct,
                impact=IMPACT_PRICE_CHANGE,
                direction="bullish",
            )
        elif pct < 0:
            raw_score -= IMPACT_PRICE_CHANGE
            evidence["percent_price_change_5_days"] = EvidenceItemModel(
                key="percent_price_change_5_days",
                message=f"Price change {pct*100:.2f}% negative",
                value=pct,
                impact=-IMPACT_PRICE_CHANGE,
                direction="bearish",
            )
        else:
            evidence["percent_price_change_5_days"] = EvidenceItemModel(
                key="percent_price_change_5_days", message="Price change neutral", value=pct, impact=0.0, direction="neutral"
            )

        # --- MA short ---
        ma5 = self.signals.get("ma_5")
        if self._has(ma5) and self._has(ma20):
            if ma5 > ma20:
                raw_score += IMPACT_MA_SHORT_TERM
                evidence["ma_short_term"] = EvidenceItemModel(
                    key="ma_short_term",
                    message=f"Ma5 {self._fmt(ma5)} above Ma20 {self._fmt(ma20)}",
                    impact=IMPACT_MA_SHORT_TERM,
                    direction="bullish",
                )
            else:
                raw_score -= IMPACT_MA_SHORT_TERM
                evidence["ma_short_term"] = EvidenceItemModel(
                    key="ma_short_term",
                    message=f"Ma5 {self._fmt(ma5)} below Ma20 {self._fmt(ma20)}",
                    impact=-IMPACT_MA_SHORT_TERM,
                    direction="bearish",
                )
        else:
            evidence["ma_short_term"] = EvidenceItemModel(key="ma_short_term", message="MA5/MA20 unavailable")

        # --- MA long ---
        ma100 = self.signals.get("ma_100")
        ma200 = self.signals.get("ma_200")
        if self._has(ma100) and self._has(ma200):
            if ma100 > ma200:
                raw_score += IMPACT_MA_LONG_TERM
                evidence["ma_long_term"] = EvidenceItemModel(
                    key="ma_long_term",
                    message=f"Ma100 {self._fmt(ma100)} above Ma200 {self._fmt(ma200)}",
                    impact=IMPACT_MA_LONG_TERM,
                    direction="bullish",
                )
            else:
                raw_score -= IMPACT_MA_LONG_TERM
                evidence["ma_long_term"] = EvidenceItemModel(
                    key="ma_long_term",
                    message=f"Ma100 {self._fmt(ma100)} below Ma200 {self._fmt(ma200)}",
                    impact=-IMPACT_MA_LONG_TERM,
                    direction="bearish",
                )
        else:
            evidence["ma_long_term"] = EvidenceItemModel(key="ma_long_term", message="MA100/MA200 unavailable")

        # --- Close vs SMA20 ---
        last_close = self.signals.get("last_close")
        if self._has(last_close) and self._has(ma20):
            if last_close > ma20:
                raw_score += IMPACT_CLOSE_VS_SMA20
                evidence["close_vs_sma20"] = EvidenceItemModel(
                    key="close_vs_sma20",
                    message=f"Close {self._fmt(last_close)} above SMA20 {self._fmt(ma20)}",
                    impact=IMPACT_CLOSE_VS_SMA20,
                    direction="bullish",
                )
            else:
                raw_score -= IMPACT_CLOSE_VS_SMA20
                evidence["close_vs_sma20"] = EvidenceItemModel(
                    key="close_vs_sma20",
                    message=f"Close {self._fmt(last_close)} below SMA20 {self._fmt(ma20)}",
                    impact=-IMPACT_CLOSE_VS_SMA20,
                    direction="bearish",
                )
        else:
            evidence["close_vs_sma20"] = EvidenceItemModel(key="close_vs_sma20", message="Close/SMA20 unavailable")

        # --- ADX (strength-sensitive, same as v2) ---
        adx = self.signals.get("adx")
        if adx is None:
            evidence["adx"] = EvidenceItemModel(
                key="adx", message="ADX not available (adx needs > 28 trading days)"
            )
        else:
            if adx > ADX_STRONG_THRESHOLD:
                factor = _adx_strength_factor(adx)
                scaled_impact = IMPACT_ADX_BASE * factor
                if self._has(pct) and pct > 0:
                    raw_score += scaled_impact
                    evidence["adx"] = EvidenceItemModel(
                        key="adx",
                        message=f"ADX {self._fmt(adx)} strong uptrend",
                        value=adx,
                        impact=scaled_impact,
                        direction="bullish",
                    )
                elif self._has(pct) and pct < 0:
                    raw_score -= scaled_impact
                    evidence["adx"] = EvidenceItemModel(
                        key="adx",
                        message=f"ADX {self._fmt(adx)} strong downtrend",
                        value=adx,
                        impact=-scaled_impact,
                        direction="bearish",
                    )
                else:
                    evidence["adx"] = EvidenceItemModel(
                        key="adx", message=f"ADX {self._fmt(adx)} strong trend (direction unclear)", value=adx
                    )
            elif adx < ADX_WEAK_THRESHOLD:
                new_impact = (0.5 - raw_score) * 0.1
                raw_score += new_impact
                evidence["adx"] = EvidenceItemModel(
                    key="adx", message=f"ADX {self._fmt(adx)} weak trend", value=adx, impact=new_impact, direction="neutral"
                )
            else:
                evidence["adx"] = EvidenceItemModel(
                    key="adx", message=f"ADX {self._fmt(adx)} moderate trend", value=adx, impact=0.0, direction="neutral"
                )

        # --- BBands: close < lower -> bullish, close > upper -> bearish ---
        bb_upper = self.signals.get("bbands_upper")
        bb_lower = self.signals.get("bbands_lower")
        if self._has(last_close) and self._has(bb_upper) and self._has(bb_lower):
            if last_close < bb_lower:
                raw_score += IMPACT_BBANDS
                evidence["bbands"] = EvidenceItemModel(
                    key="bbands",
                    message=f"Close {self._fmt(last_close)} below lower band (oversold)",
                    impact=IMPACT_BBANDS,
                    direction="bullish",
                )
            elif last_close > bb_upper:
                raw_score -= IMPACT_BBANDS
                evidence["bbands"] = EvidenceItemModel(
                    key="bbands",
                    message=f"Close {self._fmt(last_close)} above upper band (overbought)",
                    impact=-IMPACT_BBANDS,
                    direction="bearish",
                )
            else:
                evidence["bbands"] = EvidenceItemModel(
                    key="bbands", message="Close within Bollinger Bands", impact=0.0, direction="neutral"
                )
        else:
            evidence["bbands"] = EvidenceItemModel(key="bbands", message="BBands unavailable")

        # --- MACD: line > 0 -> bullish, < 0 -> bearish ---
        macd = self.signals.get("macd_12_26_9")
        if self._has(macd):
            if macd > 0:
                raw_score += IMPACT_MACD
                evidence["macd"] = EvidenceItemModel(
                    key="macd",
                    message=f"MACD {self._fmt(macd)} positive",
                    value=macd,
                    impact=IMPACT_MACD,
                    direction="bullish",
                )
            elif macd < 0:
                raw_score -= IMPACT_MACD
                evidence["macd"] = EvidenceItemModel(
                    key="macd",
                    message=f"MACD {self._fmt(macd)} negative",
                    value=macd,
                    impact=-IMPACT_MACD,
                    direction="bearish",
                )
            else:
                evidence["macd"] = EvidenceItemModel(
                    key="macd", message="MACD neutral", value=macd, impact=0.0, direction="neutral"
                )
        else:
            evidence["macd"] = EvidenceItemModel(key="macd", message="MACD unavailable")

        raw_score = max(0, min(1, raw_score))

        # --- NA weight reduction (v3: 8 contributors) ---
        count_available = self._count_available_signals()
        count_total = len(SCORE_CONTRIBUTING_KEYS_V3)
        if count_total > 0 and count_available < count_total:
            raw_score = 0.5 + (raw_score - 0.5) * (count_available / count_total)
            raw_score = max(0, min(1, raw_score))

        self.evidence = evidence
        return raw_score, evidence

    def label_from_score(self, score: float) -> str:
        if score >= 0.7:
            return "bullish"
        elif score < 0.7 and score >= 0.55:
            return "slightly bullish"
        elif score < 0.55 and score >= 0.45:
            return "neutral"
        elif score < 0.45 and score >= 0.25:
            return "slightly bearish"
        else:
            return "bearish"

    def full_bias_assessment(self) -> tuple[str, float, dict]:
        raw_score, evidence = self.score_from_signals()
        score = round(raw_score, 2)
        label = self.label_from_score(score)
        return (label, score, evidence)

    def get_bias_assessment(self) -> str:
        import json
        raw_score, _ = self.score_from_signals()
        score = round(raw_score, 2)
        label = self.label_from_score(score)
        evidence_serialized = {
            key: value.model_dump() if hasattr(value, "model_dump") else value
            for key, value in self.evidence.items()
        }
        return json.dumps({"label": label, "score": score, "evidence": evidence_serialized})

    def get_price_summary(self) -> dict:
        first_close = self.signals.get("first_close", 0)
        last_close = self.signals.get("last_close", 0)
        period_high = self.signals.get("period_high", 0)
        period_low = self.signals.get("period_low", 0)
        total_return = ((last_close / first_close) - 1) * 100 if first_close else 0
        return {
            "first_close": first_close,
            "last_close": last_close,
            "period_high": period_high,
            "period_low": period_low,
            "total_return_pct": round(total_return, 2),
        }
