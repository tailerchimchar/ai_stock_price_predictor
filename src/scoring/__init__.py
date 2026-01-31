"""
Scoring package: BiasScorer v1 and v2.
Version switch via get_scorer(version="v1"|"v2").
"""

from src.scoring.v1 import BiasScorerV1
from src.scoring.v2 import BiasScorerV2


def get_scorer(version: str = "v1"):
    """Return scorer class for the given version. Default v1 for rollback safety."""
    if version == "v2":
        return BiasScorerV2
    return BiasScorerV1


__all__ = ["BiasScorerV1", "BiasScorerV2", "get_scorer"]
