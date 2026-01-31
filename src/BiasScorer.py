"""
Backward-compatible re-export: BiasScorer = BiasScorerV1.
Existing imports (from src.BiasScorer import BiasScorer) continue to work and resolve to v1.
Use BIAS_SCORER_VERSION=v2 in analyze_service to switch to v2.
"""

from src.scoring.v1 import BiasScorerV1 as BiasScorer

__all__ = ["BiasScorer"]
