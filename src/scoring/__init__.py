"""
Scoring package: BiasScorer v1, v2, and v3.
Version switch via get_scorer(version="v1"|"v2"|"v3").
"""

from src.scoring.v1 import BiasScorerV1
from src.scoring.v2 import BiasScorerV2
from src.scoring.v3 import BiasScorerV3


def get_scorer(version: str = "v1"):
    """Return scorer class for the given version. Default v1 for rollback safety."""
    if version == "v3":
        return BiasScorerV3
    if version == "v2":
        return BiasScorerV2
    return BiasScorerV1


__all__ = ["BiasScorerV1", "BiasScorerV2", "BiasScorerV3", "get_scorer"]
