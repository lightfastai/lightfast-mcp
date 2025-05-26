"""
DEPRECATED: Tests for the old AI CLI.

These tests are deprecated because the old AI CLI has been replaced
by the new conversation client CLI.
"""

import pytest


@pytest.mark.skip(reason="Old AI CLI has been deprecated and removed")
class TestDeprecatedClientsCliTests:
    """Deprecated test class - all tests skipped."""

    def test_deprecated_notice(self):
        """This test class is deprecated."""
        pytest.skip("Old AI CLI has been deprecated and removed")
