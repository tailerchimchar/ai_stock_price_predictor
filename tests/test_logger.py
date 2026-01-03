"""Unit tests for logger module."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger


class TestLogger:
    """Test logger module."""
    
    def test_logger_exists(self):
        """Logger should be created without error."""
        logger = get_logger(__name__)
        assert logger is not None
    
    def test_logger_has_handlers(self):
        """Logger should have at least one handler."""
        logger = get_logger(__name__)
        assert len(logger.handlers) > 0
    
    def test_logger_returns_same_instance(self):
        """Calling get_logger twice should return same logger."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2
    
    def test_logger_has_correct_level(self):
        """Logger should be set to INFO level."""
        logger = get_logger("test_level")
        assert logger.level <= 20  # INFO is 20, DEBUG is 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
