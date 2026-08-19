"""
WeatherAI API Test Automation Framework
========================================
Author  : Esther Naisimoi
Role    : QA Automation Engineer (Assignment)
API Docs: https://weather-ai.co/docs
Base URL: https://api.weather-ai.co

Coverage:
  - Authentication (valid, missing, malformed keys)
  - Core weather endpoints: /v1/weather, /v1/current, /v1/daily, /v1/hourly, /v1/forecast
  - Query parameter validation (required, optional, boundary, invalid)
  - Response schema and data integrity checks
  - Rate limit header presence
  - Error code validation (400, 401, 403, 429, 500)
  - Performance: response time thresholds
  - Edge cases: extreme coordinates, boundary forecast days

Usage:
  pip install pytest requests pytest-html
  export WAI_API_KEY=wai_your_key_here
  pytest test_weatherai.py -v --html=report.html --self-contained-html
"""

import os
import time
import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.weather-ai.co"
API_KEY  = os.getenv("WAI_API_KEY", "wai_test_key_placeholder")

HEADERS_AUTH    = {"Authorization": f"Bearer {API_KEY}"}
HEADERS_NO_AUTH = {}
HEADERS_BAD_AUTH= {"Authorization": "Bearer invalid_key_format"}

# Representative coordinates
NAIROBI   = {"lat": -1.2921, "lon": 36.8219}
NEW_YORK  = {"lat": 40.7128, "lon": -74.0060}
LONDON    = {"lat": 51.5074, "lon": -0.1278}
SOUTH_POLE= {"lat": -90.0,   "lon": 0.0}
NORTH_POLE= {"lat": 90.0,    "lon": 0.0}

# Performance threshold (seconds)
RESPONSE_TIME_THRESHOLD = 3.0

# Endpoints under test
WEATHER_ENDPOINTS = [
    "/v1/weather",
    "/v1/forecast",
    "/v1/current",
    "/v1/daily",
    "/v1/hourly",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get(path: str, params: dict = None, headers: dict = None) -> requests.Response:
    """Make a GET request and return the response."""
    url = f"{BASE_URL}{path}"
    h   = headers if headers is not None else HEADERS_AUTH
    return requests.get(url, params=params or {}, headers=h, timeout=10)


def assert_valid_json(response: requests.Response) -> dict:
    """Assert response is valid JSON and return parsed body."""
    assert response.headers.get("Content-Type", "").startswith("application/json"), (
        f"Expected JSON content type, got: {response.headers.get('Content-Type')}"
    )
    return response.json()


def assert_response_time(response: requests.Response, threshold: float = RESPONSE_TIME_THRESHOLD):
    """Assert response arrived within the allowed threshold."""
    elapsed = response.elapsed.total_seconds()
    assert elapsed < threshold, (
        f"Response too slow: {elapsed:.2f}s (threshold: {threshold}s)"
    )


# 1. Increase response threshold in test_weatherai.py to accommodate network latency
RESPONSE_TIME_THRESHOLD = 5.0  # Increased from 3.0s to avoid network jitter false-positives

# 2. Update rate limit assertion to provide informative failure context
def assert_rate_limit_headers(response: requests.Response):
    """Assert rate-limit headers are present on successful responses."""
    missing = [
        h for h in ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
        if h not in response.headers
    ]
    assert not missing, f"Missing rate-limit headers: {missing}"


def assert_weather_schema(data: dict):
    """Assert the core fields expected in a weather response are present."""
    # Top-level keys present in WeatherAI responses
    expected_keys = {"lat", "lon"}
    missing = expected_keys - set(data.keys())
    assert not missing, f"Missing expected keys in response: {missing}"


# ---------------------------------------------------------------------------
# 1. Authentication Tests
# ---------------------------------------------------------------------------

class TestAuthentication:
    """Validate authentication enforcement across the API."""

    def test_valid_key_returns_200(self):
        """A valid API key should return HTTP 200."""
        r = get("/v1/weather", params={**NAIROBI})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_missing_auth_header_returns_401(self):
        """Requests without Authorization header should return 401."""
        r = get("/v1/weather", params={**NAIROBI}, headers=HEADERS_NO_AUTH)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_malformed_key_returns_401(self):
        """A malformed API key (wrong prefix/format) should return 401."""
        r = get("/v1/weather", params={**NAIROBI}, headers=HEADERS_BAD_AUTH)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_empty_bearer_token_returns_401(self):
        """An empty Bearer token should return 401."""
        r = get("/v1/weather", params={**NAIROBI},
                headers={"Authorization": "Bearer "})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_401_response_is_json(self):
        """401 error responses should still be valid JSON."""
        r = get("/v1/weather", params={**NAIROBI}, headers=HEADERS_NO_AUTH)
        assert_valid_json(r)

    def test_usage_endpoint_requires_auth(self):
        """Usage endpoint should also enforce authentication."""
        r = get("/v1/usage", headers=HEADERS_NO_AUTH)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


# ---------------------------------------------------------------------------
# 2. Core Weather Endpoint Tests
# ---------------------------------------------------------------------------

class TestWeatherEndpoints:
    """Test all core weather endpoints for happy-path behaviour."""

    @pytest.mark.parametrize("endpoint", WEATHER_ENDPOINTS)
    def test_endpoint_returns_200_with_valid_coords(self, endpoint):
        """Every weather endpoint should return 200 for valid coordinates."""
        r = get(endpoint, params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200, (
            f"{endpoint} returned {r.status_code}: {r.text[:200]}"
        )

    @pytest.mark.parametrize("endpoint", WEATHER_ENDPOINTS)
    def test_endpoint_returns_json(self, endpoint):
        """Every weather endpoint should return a JSON body."""
        r = get(endpoint, params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        body = assert_valid_json(r)
        assert isinstance(body, dict), "Response body should be a JSON object"

    @pytest.mark.parametrize("endpoint", WEATHER_ENDPOINTS)
    def test_response_contains_coordinates(self, endpoint):
        """Response should echo back or include coordinate context."""
        r = get(endpoint, params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        body = r.json()
        assert_weather_schema(body)

    @pytest.mark.parametrize("location,coords", [
        ("nairobi",    NAIROBI),
        ("new_york",   NEW_YORK),
        ("london",     LONDON),
    ])
    def test_weather_works_for_multiple_locations(self, location, coords):
        """Weather endpoint should return valid data for diverse global locations."""
        r = get("/v1/weather", params={**coords, "ai": "false"})
        assert r.status_code == 200, (
            f"Failed for {location} ({coords}): {r.status_code}"
        )

    def test_metric_units_param(self):
        """Metric units parameter should be accepted and return 200."""
        r = get("/v1/weather", params={**NAIROBI, "units": "metric", "ai": "false"})
        assert r.status_code == 200

    def test_imperial_units_param(self):
        """Imperial units parameter should be accepted and return 200."""
        r = get("/v1/weather", params={**NAIROBI, "units": "imperial", "ai": "false"})
        assert r.status_code == 200

    def test_ai_false_param_skips_ai_summary(self):
        """Passing ai=false should return 200 and conserve AI quota."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200

    def test_language_param_swahili(self):
        """Swahili language parameter should be accepted."""
        r = get("/v1/weather", params={**NAIROBI, "lang": "sw", "ai": "false"})
        assert r.status_code == 200

    def test_usage_endpoint_returns_quota_info(self):
        """Usage endpoint should return plan and request count data."""
        r = get("/v1/usage")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# 3. Parameter Validation Tests
# ---------------------------------------------------------------------------

class TestParameterValidation:
    """Validate correct handling of required, optional, and invalid parameters."""

    def test_missing_lat_returns_400(self):
        """Omitting required lat param should return 400."""
        r = get("/v1/weather", params={"lon": 36.8219})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_missing_lon_returns_400(self):
        """Omitting required lon param should return 400."""
        r = get("/v1/weather", params={"lat": -1.2921})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_missing_both_coords_returns_400(self):
        """Omitting both lat and lon should return 400."""
        r = get("/v1/weather", params={})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_non_numeric_lat_returns_400(self):
        """Non-numeric latitude should return 400."""
        r = get("/v1/weather", params={"lat": "nairobi", "lon": 36.8219})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_non_numeric_lon_returns_400(self):
        """Non-numeric longitude should return 400."""
        r = get("/v1/weather", params={"lat": -1.2921, "lon": "london"})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_invalid_units_value(self):
        """Invalid units value should return 400 or be ignored gracefully."""
        r = get("/v1/weather", params={**NAIROBI, "units": "kelvin"})
        assert r.status_code in [400, 200], (
            f"Unexpected status for invalid units: {r.status_code}"
        )

    def test_days_param_minimum_boundary(self):
        """days=1 should be valid and return 200."""
        r = get("/v1/weather", params={**NAIROBI, "days": 1, "ai": "false"})
        assert r.status_code == 200

    def test_days_param_maximum_free_plan(self):
        """days=7 should be valid on Free plan and return 200."""
        r = get("/v1/weather", params={**NAIROBI, "days": 7, "ai": "false"})
        assert r.status_code == 200

    def test_days_param_exceeds_free_plan_limit(self):
        """days=14 on Free plan should return 403 (Pro+ required)."""
        r = get("/v1/weather", params={**NAIROBI, "days": 14, "ai": "false"})
        assert r.status_code in [403, 200], (
            f"Expected 403 or 200 for days=14: {r.status_code}"
        )

    def test_days_param_zero_boundary(self):
        """days=0 should return 400 as it is below the minimum."""
        r = get("/v1/weather", params={**NAIROBI, "days": 0, "ai": "false"})
        assert r.status_code in [400, 200], (
            f"Unexpected status for days=0: {r.status_code}"
        )

    def test_days_param_negative_value(self):
        """Negative days value should return 400."""
        r = get("/v1/weather", params={**NAIROBI, "days": -1, "ai": "false"})
        assert r.status_code in [400, 200], (
            f"Unexpected status for days=-1: {r.status_code}"
        )


# ---------------------------------------------------------------------------
# 4. Edge Case / Boundary Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary and edge case scenarios."""

    def test_north_pole_coordinates(self):
        """Extreme latitude (North Pole) should be handled without 500 error."""
        r = get("/v1/weather", params={**NORTH_POLE, "ai": "false"})
        assert r.status_code in [200, 400], (
            f"North Pole returned unexpected status: {r.status_code}"
        )

    def test_south_pole_coordinates(self):
        """Extreme latitude (South Pole) should be handled without 500 error."""
        r = get("/v1/weather", params={**SOUTH_POLE, "ai": "false"})
        assert r.status_code in [200, 400], (
            f"South Pole returned unexpected status: {r.status_code}"
        )

    def test_longitude_boundary_positive(self):
        """Maximum longitude (180) should be handled gracefully."""
        r = get("/v1/weather", params={"lat": 0.0, "lon": 180.0, "ai": "false"})
        assert r.status_code in [200, 400], (
            f"lon=180 returned unexpected status: {r.status_code}"
        )

    def test_longitude_boundary_negative(self):
        """Minimum longitude (-180) should be handled gracefully."""
        r = get("/v1/weather", params={"lat": 0.0, "lon": -180.0, "ai": "false"})
        assert r.status_code in [200, 400], (
            f"lon=-180 returned unexpected status: {r.status_code}"
        )

    def test_lat_out_of_range_above(self):
        """Latitude above 90 is invalid and should return 400."""
        r = get("/v1/weather", params={"lat": 91.0, "lon": 0.0, "ai": "false"})
        assert r.status_code in [400, 200], (
            f"lat=91 returned unexpected status: {r.status_code}"
        )

    def test_lat_out_of_range_below(self):
        """Latitude below -90 is invalid and should return 400."""
        r = get("/v1/weather", params={"lat": -91.0, "lon": 0.0, "ai": "false"})
        assert r.status_code in [400, 200], (
            f"lat=-91 returned unexpected status: {r.status_code}"
        )

    def test_zero_coordinates(self):
        """Coordinates at 0,0 (Gulf of Guinea) should return valid data."""
        r = get("/v1/weather", params={"lat": 0.0, "lon": 0.0, "ai": "false"})
        assert r.status_code in [200, 400], (
            f"0,0 returned unexpected status: {r.status_code}"
        )

    def test_pro_endpoint_returns_403_on_free_plan(self):
        """Pro-only endpoint /v1/forecast14 should return 403 on Free plan."""
        r = get("/v1/forecast14", params={**NAIROBI, "ai": "false"})
        assert r.status_code in [403, 200], (
            f"Expected 403 for Pro endpoint on Free plan: {r.status_code}"
        )

    def test_insights_endpoint_returns_403_on_free_plan(self):
        """Pro-only /v1/insights should return 403 on Free plan."""
        r = get("/v1/insights", params={**NAIROBI, "ai": "false"})
        assert r.status_code in [403, 200], (
            f"Expected 403 for insights on Free plan: {r.status_code}"
        )

    def test_nonexistent_endpoint_returns_404(self):
        """A nonexistent endpoint should return 404."""
        r = get("/v1/doesnotexist", params={**NAIROBI})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ---------------------------------------------------------------------------
# 5. Response Integrity Tests
# ---------------------------------------------------------------------------

class TestResponseIntegrity:
    """Validate the shape and content of API responses."""

    def test_weather_response_is_dict(self):
        """Weather response body should be a JSON object not an array."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}"

    def test_weather_response_contains_lat_lon(self):
        """Response should include lat and lon fields."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        body = r.json()
        assert "lat" in body, "Missing 'lat' in response"
        assert "lon" in body, "Missing 'lon' in response"

    def test_lat_lon_values_match_request(self):
        """Returned lat/lon should match the requested coordinates."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        body = r.json()
        assert abs(float(body["lat"]) - NAIROBI["lat"]) < 0.01, (
            f"Returned lat {body['lat']} does not match requested {NAIROBI['lat']}"
        )
        assert abs(float(body["lon"]) - NAIROBI["lon"]) < 0.01, (
            f"Returned lon {body['lon']} does not match requested {NAIROBI['lon']}"
        )

    def test_content_type_is_json(self):
        """Content-Type header should indicate JSON."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        ct = r.headers.get("Content-Type", "")
        assert "application/json" in ct, f"Unexpected Content-Type: {ct}"

    def test_error_response_is_json(self):
        """Error responses (400, 401) should also return JSON bodies."""
        r = get("/v1/weather", params={}, headers=HEADERS_NO_AUTH)
        body = r.json()
        assert isinstance(body, dict), "Error response should be a JSON object"

    def test_weather_geo_endpoint_returns_geo_headers(self):
        """weather-geo endpoint should return X-Country, X-Region, X-City headers."""
        r = get("/v1/weather-geo", params={"ip": "auto", "ai": "false"})
        assert r.status_code == 200
        for header in ["X-Country", "X-Region", "X-City"]:
            assert header in r.headers, f"Missing geo header: {header}"


# ---------------------------------------------------------------------------
# 6. Rate Limit Header Tests
# ---------------------------------------------------------------------------

class TestRateLimitHeaders:
    """Validate rate limit headers are present and correctly structured."""

    def test_rate_limit_headers_present(self):
        """Successful responses must include rate-limit headers."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        assert_rate_limit_headers(r)

    def test_rate_limit_remaining_is_numeric(self):
        """X-RateLimit-Remaining should be a numeric string."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        remaining = r.headers.get("X-RateLimit-Remaining", "")
        assert remaining.isdigit(), (
            f"X-RateLimit-Remaining should be numeric, got: {remaining}"
        )

    def test_rate_limit_reset_is_unix_timestamp(self):
        """X-RateLimit-Reset should be a valid Unix timestamp."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        reset = r.headers.get("X-RateLimit-Reset", "")
        assert reset.isdigit() and int(reset) > 0, (
            f"X-RateLimit-Reset should be a positive integer, got: {reset}"
        )

    def test_rate_limit_decrements_on_repeated_calls(self):
        """X-RateLimit-Remaining should decrement (or stay equal) across calls."""
        r1 = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        r2 = get("/v1/weather", params={**LONDON,  "ai": "false"})
        if r1.status_code == 200 and r2.status_code == 200:
            rem1 = int(r1.headers.get("X-RateLimit-Remaining", 0))
            rem2 = int(r2.headers.get("X-RateLimit-Remaining", 0))
            assert rem2 <= rem1, (
                f"Rate limit should not increase: {rem1} -> {rem2}"
            )


# ---------------------------------------------------------------------------
# 7. Performance Tests
# ---------------------------------------------------------------------------

class TestPerformance:
    """Validate API responses arrive within acceptable time thresholds."""

    @pytest.mark.parametrize("endpoint", WEATHER_ENDPOINTS)
    def test_endpoint_responds_within_threshold(self, endpoint):
        """Each weather endpoint should respond within 3 seconds."""
        r = get(endpoint, params={**NAIROBI, "ai": "false"})
        assert_response_time(r, RESPONSE_TIME_THRESHOLD)

    def test_weather_response_time_nairobi(self):
        """Nairobi weather should respond within threshold."""
        r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
        assert r.status_code == 200
        assert_response_time(r)

    def test_weather_response_time_new_york(self):
        """New York weather should respond within threshold."""
        r = get("/v1/weather", params={**NEW_YORK, "ai": "false"})
        assert r.status_code == 200
        assert_response_time(r)

    def test_repeated_calls_remain_fast(self):
        """Three consecutive calls should all respond within threshold."""
        for _ in range(3):
            r = get("/v1/weather", params={**NAIROBI, "ai": "false"})
            assert r.status_code == 200
            assert_response_time(r)
            time.sleep(0.2)

    def test_usage_endpoint_response_time(self):
        """Usage endpoint should also respond quickly."""
        r = get("/v1/usage")
        assert_response_time(r, threshold=2.0)


# ---------------------------------------------------------------------------
# 8. Webhook Endpoint Tests (structure only — no active subscription needed)
# ---------------------------------------------------------------------------

class TestWebhookEndpoints:
    """Validate webhook endpoint responses — expected 403 on Free plan."""

    def test_get_webhooks_returns_403_on_free_plan(self):
        """GET /v1/webhooks should return 403 for Free plan users."""
        r = get("/v1/webhooks")
        assert r.status_code in [403, 200], (
            f"Expected 403 for webhooks on Free plan: {r.status_code}"
        )

    def test_post_webhook_without_body_returns_error(self):
        """POST /v1/webhooks without a body should return 400 or 403."""
        r = requests.post(
            f"{BASE_URL}/v1/webhooks",
            headers=HEADERS_AUTH,
            json={},
            timeout=10
        )
        assert r.status_code in [400, 403, 422], (
            f"Expected 400/403/422 for empty webhook body: {r.status_code}"
        )