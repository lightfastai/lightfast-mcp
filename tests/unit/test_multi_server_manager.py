"""
DEPRECATED: Tests for the old MultiServerManager.

These tests are deprecated because MultiServerManager has been replaced
by the new ServerOrchestrator architecture.
"""

import pytest


@pytest.mark.skip(reason="MultiServerManager has been deprecated and removed")
class TestDeprecatedMultiServerManager:
    """Deprecated test class - all tests skipped."""

    def test_deprecated_notice(self):
        """This test class is deprecated."""
        pytest.skip("MultiServerManager has been deprecated and removed")
