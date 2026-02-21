"""Minimal test so colcon test always gets a result file (avoids pytest.missing_result)."""


def test_placeholder() -> None:
    """Always passes; ensures pytest writes pytest.xml for colcon test-result."""
    pass
