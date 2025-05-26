"""
DEPRECATED: Tests for the old MultiServerAIClient.

These tests are deprecated because MultiServerAIClient has been replaced
by the new ConversationClient architecture.

New tests for the ConversationClient should be added in test_conversation_client.py
"""

import pytest


@pytest.mark.skip(reason="MultiServerAIClient has been deprecated and removed")
class TestDeprecatedAIClient:
    """Deprecated test class - all tests skipped."""

    def test_deprecated_notice(self):
        """This test class is deprecated."""
        pytest.skip("MultiServerAIClient has been deprecated and removed")
