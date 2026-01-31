"""
BiasScorer v1: original additive scoring logic.
Preserved for rollback; same behavior as legacy BiasScorer.
"""

import json
from app.stock_response_model import EvidenceItemModel

IMPACT_RSI = 0.2
IMPACT_PRICE_CHANGE = 0.2
IMPACT_MA_SHORT_TERM = 0.1
IMPACT_MA_LONG_TERM = 0.1
IMPACT_CLOSE_VS_SMA20 = 0.1
IMPACT_ADX = 0.15


class BiasScorerV1:
    def __init__(self, signals):
        self.signals = signals
        self.evidence = {}

    def _fmt(self, value: float) -> str:
        return f"{value:.1f}"

    def _has(self, value) -> bool:
        return value is not None and value == value  # filters None and NaN

    def score_from_signals(self) -> tuple[float, dict]:
        bullish_bias_score = 0.5
        evidence = {}

        rsi = self.signals.get("rsi")
        if not self._has(rsi):
            evidence["rsi"] = EvidenceItemModel(
                key="rsi", message="RSI unavailable, time period is too short", impact=0.0, direction=None
            )
        else:
            if rsi < 30:
                bullish_bias_score += IMPACT_RSI
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} oversold", value=rsi, impact=IMPACT_RSI, direction="bullish"
                )
            elif rsi > 70:
                bullish_bias_score -= IMPACT_RSI
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} overbought", value=rsi, impact=-IMPACT_RSI, direction="bearish"
                )
            else:
                evidence["rsi"] = EvidenceItemModel(
                    key="rsi", message=f"RSI {self._fmt(rsi)} neutral", value=rsi, impact=0.0, direction="neutral"
                )

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
            bullish_bias_score += IMPACT_PRICE_CHANGE
            evidence["percent_price_change_5_days"] = EvidenceItemModel(
                key="percent_price_change_5_days",
                message=f"Price change {pct*100:.2f}% positive",
                value=pct,
                impact=IMPACT_PRICE_CHANGE,
                direction="bullish",
            )
        elif pct < 0:
            bullish_bias_score -= IMPACT_PRICE_CHANGE
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

        ma5 = self.signals.get("ma_5")
        ma20 = self.signals.get("ma_20")
        if self._has(ma5) and self._has(ma20):
            if ma5 > ma20:
                bullish_bias_score += IMPACT_MA_SHORT_TERM
                evidence["ma_short_term"] = EvidenceItemModel(
                    key="ma_short_term",
                    message=f"Ma5 {self._fmt(ma5)} above Ma20 {self._fmt(ma20)}",
                    impact=IMPACT_MA_SHORT_TERM,
                    direction="bullish",
                )
            else:
                bullish_bias_score -= IMPACT_MA_SHORT_TERM
                evidence["ma_short_term"] = EvidenceItemModel(
                    key="ma_short_term",
                    message=f"Ma5 {self._fmt(ma5)} below Ma20 {self._fmt(ma20)}",
                    impact=-IMPACT_MA_SHORT_TERM,
                    direction="bearish",
                )
        else:
            evidence["ma_short_term"] = EvidenceItemModel(key="ma_short_term", message="MA5/MA20 unavailable")

        ma100 = self.signals.get("ma_100")
        ma200 = self.signals.get("ma_200")
        if self._has(ma100) and self._has(ma200):
            if ma100 > ma200:
                bullish_bias_score += IMPACT_MA_LONG_TERM
                evidence["ma_long_term"] = EvidenceItemModel(
                    key="ma_long_term",
                    message=f"Ma100 {self._fmt(ma100)} above Ma200 {self._fmt(ma200)}",
                    impact=IMPACT_MA_LONG_TERM,
                    direction="bullish",
                )
            else:
                bullish_bias_score -= IMPACT_MA_LONG_TERM
                evidence["ma_long_term"] = EvidenceItemModel(
                    key="ma_long_term",
                    message=f"Ma100 {self._fmt(ma100)} below Ma200 {self._fmt(ma200)}",
                    impact=-IMPACT_MA_LONG_TERM,
                    direction="bearish",
                )
        else:
            evidence["ma_long_term"] = EvidenceItemModel(key="ma_long_term", message="MA100/MA200 unavailable")

        last_close = self.signals.get("last_close")
        if self._has(last_close) and self._has(ma20):
            if last_close > ma20:
                bullish_bias_score += IMPACT_CLOSE_VS_SMA20
                evidence["close_vs_sma20"] = EvidenceItemModel(
                    key="close_vs_sma20",
                    message=f"Close {self._fmt(last_close)} above SMA20 {self._fmt(ma20)}",
                    impact=IMPACT_CLOSE_VS_SMA20,
                    direction="bullish",
                )
            else:
                bullish_bias_score -= IMPACT_CLOSE_VS_SMA20
                evidence["close_vs_sma20"] = EvidenceItemModel(
                    key="close_vs_sma20",
                    message=f"Close {self._fmt(last_close)} below SMA20 {self._fmt(ma20)}",
                    impact=-IMPACT_CLOSE_VS_SMA20,
                    direction="bearish",
                )
        else:
            evidence["close_vs_sma20"] = EvidenceItemModel(key="close_vs_sma20", message="Close/SMA20 unavailable")

        adx = self.signals.get("adx")
        if adx is None:
            evidence["adx"] = EvidenceItemModel(
                key="adx", message="ADX not available (adx needs >  28 trading days)"
            )
        else:
            if adx > 25:
                if self._has(pct) and pct > 0:
                    bullish_bias_score += IMPACT_ADX
                    evidence["adx"] = EvidenceItemModel(
                        key="adx", message=f"ADX {adx} strong uptrend", value=adx, impact=IMPACT_ADX, direction="bullish"
                    )
                elif self._has(pct) and pct < 0:
                    bullish_bias_score -= IMPACT_ADX
                    evidence["adx"] = EvidenceItemModel(
                        key="adx", message=f"ADX {adx} strong downtrend", value=adx, impact=-IMPACT_ADX, direction="bearish"
                    )
                else:
                    evidence["adx"] = EvidenceItemModel(key="adx", message=f"ADX {adx} strong trend (direction unclear)", value=adx)
            elif adx < 20:
                new_impact = (0.5 - bullish_bias_score) * 0.1
                bullish_bias_score += new_impact
                evidence["adx"] = EvidenceItemModel(
                    key="adx", message=f"ADX {adx} weak trend", value=adx, impact=new_impact, direction="neutral"
                )

        bullish_bias_score = max(0, min(1, bullish_bias_score))
        self.evidence = evidence
        return bullish_bias_score, evidence

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
