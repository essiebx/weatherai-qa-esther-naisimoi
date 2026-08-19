"""
conftest.py — Pytest configuration and shared fixtures
WeatherAI API Test Framework
"""

import os
import pytest
import requests

BASE_URL = "https://api.weather-ai.co"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "auth: Authentication tests")
    config.addinivalue_line("markers", "performance: Performance/latency tests")
    config.addinivalue_line("markers", "edge: Edge case and boundary tests")
    config.addinivalue_line("markers", "schema: Response schema validation tests")


@pytest.fixture(scope="session")
def api_key():
    """Return the API key from environment. Warn if using placeholder."""
    key = os.getenv("WAI_API_KEY", "wai_test_key_placeholder")
    if key == "wai_test_key_placeholder":
        pytest.warns(UserWarning, match="WAI_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def auth_headers(api_key):
    """Return valid Authorization headers for the session."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture(scope="session")
def session(auth_headers):
    """Return a requests.Session pre-loaded with auth headers."""
    s = requests.Session()
    s.headers.update(auth_headers)
    return s


@pytest.fixture
def nairobi_params():
    """Default Nairobi coordinates with AI disabled to preserve quota."""
    return {"lat": -1.2921, "lon": 36.8219, "ai": "false"}


@pytest.fixture
def london_params():
    """London coordinates with AI disabled."""
    return {"lat": 51.5074, "lon": -0.1278, "ai": "false"}


def pytest_html_report_title(report):
    """Set the HTML report title."""
    report.title = "WeatherAI API Test Report"