"""
BiasScorer v2: strength-sensitive RSI/ADX, NA weight reduction.
Same addition-based score and same label thresholds as v1.
"""

import json
from app.stock_response_model import EvidenceItemModel

# Base impacts (same as v1 for non-RSI/non-ADX)
IMPACT_PRICE_CHANGE = 0.2
IMPACT_MA_SHORT_TERM = 0.1
IMPACT_MA_LONG_TERM = 0.1
IMPACT_CLOSE_VS_SMA20 = 0.1
IMPACT_ADX_BASE = 0.15

# Strength-sensitive RSI: (upper_bound_exclusive, impact) for oversold (bullish) and overbought (bearish)
# More extreme = larger impact. Oversold: lower RSI = larger +impact. Overbought: higher RSI = larger -impact.
RSI_OVERSOLD_BUCKETS = [(20, 0.25), (25, 0.22), (30, 0.18)]   # rsi < 20 -> +0.25; [20,25) -> +0.22; [25,30) -> +0.18
RSI_OVERBOUGHT_BUCKETS = [(75, -0.18), (80, -0.22), (101, -0.25)]  # rsi in [70,75) -> -0.18; [75,80) -> -0.22; >=80 -> -0.25

# ADX strength scaling: factor = min(1.0, (adx - 20) / 30) when adx > 25
ADX_STRENGTH_DIVISOR = 30.0
ADX_WEAK_THRESHOLD = 20
ADX_STRONG_THRESHOLD = 25

# NA weight: score-contributing signal keys (must match what we count in score_from_signals)
SCORE_CONTRIBUTING_KEYS = ("rsi", "percent_price_change", "ma_short_term", "ma_long_term", "close_vs_sma20", "adx")


def _rsi_impact(rsi: float) -> tuple[float, str]:
    """Return (impact, message_suffix). impact is 0 if neutral."""
    if rsi < 30:
        for bound, impact in RSI_OVERSOLD_BUCKETS:
            if rsi < bound:
                suffix = "deeply oversold" if impact >= 0.24 else "oversold"
                return (impact, suffix)
        return (0.18, "oversold")
    elif rsi > 70:
        for bound, impact in RSI_OVERBOUGHT_BUCKETS:
            if rsi < bound:
                suffix = "deeply overbought" if impact <= -0.24 else "overbought"
                return (impact, suffix)
        return (-0.18, "overbought")
    return (0.0, "neutral")


def _adx_strength_factor(adx: float) -> float:
    """Scale factor for ADX impact when adx > 25; min 0, max 1."""
    if adx < ADX_STRONG_THRESHOLD:
        return 0.0
    return min(1.0, (adx - 20) / ADX_STRENGTH_DIVISOR)


class BiasScorerV2:
    def __init__(self, signals):
        self.signals = signals
        self.evidence = {}

    def _fmt(self, value: float) -> str:
        return f"{value:.1f}"

    def _has(self, value) -> bool:
        return value is not None and value == value

    def _count_available_signals(self, evidence_contributions: dict) -> int:
        """Count how many of SCORE_CONTRIBUTING_KEYS actually contributed (non-NA)."""
        # We consider: rsi, percent_price_change, ma_short_term, ma_long_term, close_vs_sma20, adx
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
        return count

    def score_from_signals(self) -> tuple[float, dict]:
        raw_score = 0.5
        evidence = {}

        # --- RSI (strength-sensitive) ---
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
        pct = self.signals.get("percent_price_change")
        if not self._has(pct):
            price_change = self.signals.get("price_change")
            if self._has(price_change):
                pct = price_change / 100
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
        ma20 = self.signals.get("ma_20")
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

        # --- ADX (strength-sensitive) ---
        adx = self.signals.get("adx")
        if adx is None:
            evidence["adx"] = EvidenceItemModel(
                key="adx", message="ADX not available (adx needs >  28 trading days)"
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
                        key="adx", message=f"ADX {adx} strong trend (direction unclear)", value=adx
                    )
            elif adx < ADX_WEAK_THRESHOLD:
                new_impact = (0.5 - raw_score) * 0.1
                raw_score += new_impact
                evidence["adx"] = EvidenceItemModel(
                    key="adx", message=f"ADX {adx} weak trend", value=adx, impact=new_impact, direction="neutral"
                )
            else:
                evidence["adx"] = EvidenceItemModel(
                    key="adx", message=f"ADX {adx} moderate trend", value=adx, impact=0.0, direction="neutral"
                )

        raw_score = max(0, min(1, raw_score))

        # --- NA weight reduction ---
        count_available = self._count_available_signals(evidence)
        count_total = len(SCORE_CONTRIBUTING_KEYS)
        if count_total > 0 and count_available < count_total:
            # adjusted = 0.5 + (raw - 0.5) * (available / total)
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
