# WeatherAI API Test Automation Framework

**Author:** Esther Naisimoi  
**Role:** QA Automation Engineer Assignment  
**API:** [weather-ai.co/docs](https://weather-ai.co/docs)

---

## What This Tests

| Category | Tests | Description |
|---|---|---|
| Authentication | 6 | Valid key, missing key, malformed key, empty token |
| Core Endpoints | 23 | All 5 weather endpoints, multiple locations, unit params |
| Parameter Validation | 11 | Required params, boundaries, invalid values |
| Edge Cases | 10 | Poles, boundary coords, Pro-only endpoints, 404 |
| Response Integrity | 6 | Schema, lat/lon match, content-type, error body shape |
| Rate Limit Headers | 4 | Header presence, numeric types, decrement check |
| Performance | 9 | 3s threshold across all endpoints, repeated calls |
| Webhooks | 2 | Plan-gate enforcement, empty body handling |
| **Total** | **71** | **64 Passed, 7 Failed (Discovered Bugs)** |

---

## Setup

```bash
# 1. Clone this repository
git clone [https://github.com/essiebx/weatherai-qa-esther-naisimoi](https://github.com/essiebx/weatherai-qa-esther-naisimoi)
cd weatherai-qa-esther-naisimoi

# 2. Create project virtual environment
python -m venv .myenv

# 3. Activate project virtual environment
# Windows PowerShell:
.myenv\Scripts\activate
# Linux / macOS:
source .myenv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set your API key
## get the api key from https://weather-ai.co/
# Windows PowerShell:
$env:WEATHERAI_API_KEY="wai...your_key_here"
# Linux / macOS:
export WEATHERAI_API_KEY=wai...your_key_here

## Running the Tests

```bash
# Run all tests with verbose output
pytest test_weatherai.py -v

# Run with HTML report (opens in browser)
pytest test_weatherai.py -v --html=report.html --self-contained-html

# Run only performance tests
pytest test_weatherai.py::TestPerformance -v

# Run and stop on first failure
pytest test_weatherai.py -v -x
```

---

## Example Output

```
test_weatherai.py::TestAuthentication::test_valid_key_returns_200         PASSED
test_weatherai.py::TestAuthentication::test_missing_auth_header_returns_401 PASSED
test_weatherai.py::TestAuthentication::test_malformed_key_returns_401      PASSED
test_weatherai.py::TestWeatherEndpoints::test_endpoint_returns_200[/v1/weather] PASSED
test_weatherai.py::TestWeatherEndpoints::test_endpoint_returns_200[/v1/current] PASSED
...
57 passed in 18.4s
```

---

## Discovered API Bugs

During automated test runs against the API environment, 7 test cases failed across 3 core defect categories:

1. **BUG-001**: Server Returns 502 Bad Gateway on Out-of-Bounds Latitude
**Severity:** Medium
**Affected Tests:**
- TestEdgeCases::test_lat_out_of_range_above
- TestEdgeCases::test_lat_out_of_range_below
**Endpoint:** GET /v1/weather
**Description:** Supplying invalid latitude values (e.g., lat=91.0 or lat=-91.0) causes the API to fail with HTTP status 502 Bad Gateway instead of validating input and returning HTTP status 400 Bad Request.
**Reproduction Query:**
```http
GET /v1/weather?lat=91.0&lon=0.0&ai=false
```
**Expected Result:** 400 Bad Request with an error payload explaining coordinate constraints.
**Actual Result:** 502 Bad Gateway.

2. **BUG-002**: Missing Rate-Limit HTTP Response Headers
**Severity:** Medium
**Affected Tests:**
- TestRateLimitHeaders::test_rate_limit_headers_present
- TestRateLimitHeaders::test_rate_limit_remaining_is_numeric
- TestRateLimitHeaders::test_rate_limit_reset_is_unix_timestamp
**Endpoint:** All endpoints (e.g., GET /v1/weather)
**Description:** Successful HTTP responses do not contain expected rate-limiting metadata headers.
**Missing Headers:**
- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset
**Expected Result:** Responses include valid, numeric rate-limit tracking headers.
**Actual Result:** Headers are completely absent from the response object.

3. **BUG-003**: /v1/webhooks Route Unreachable (404 Not Found)
**Severity:** Low / Feature Parity
**Affected Tests:**
- TestWebhookEndpoints::test_get_webhooks_returns_403_on_free_plan
- TestWebhookEndpoints::test_post_webhook_without_body_returns_error
**Endpoint:** GET /v1/webhooks, POST /v1/webhooks
**Description:** Webhook endpoints return 404 Not Found, indicating the route is unmapped, unreleased, or not routed in the target environment.
**Expected Result:** 403 Forbidden for Free plan API keys, or 400/422 for invalid payloads.
**Actual Result:** 404 Not Found.
   
## Framework Design Decisions

**Why Pytest?**
Clean parametrize decorator for testing multiple endpoints/locations in one test definition. Fixtures in conftest.py keep auth and shared params DRY across all classes.

**Why classes?**
Groups tests by concern (auth, schema, performance) making the report scannable. Each class maps to a specific quality risk area.

**Why ai=false on most tests?**
The Free plan includes 200 AI requests/month. Running the full suite multiple times would exhaust AI quota quickly. AI behaviour is tested separately where needed.

**Why assert_response_time as a helper?**
Keeps the threshold value in one place. Change `RESPONSE_TIME_THRESHOLD` at the top of the file to adjust globally.

**Edge case philosophy:**
Tests assert `in [200, 400]` for boundary coordinates rather than a hard 400 because the API may have valid weather data even at extreme coordinates. The important thing is it does not 500.

---

## CI Integration (GitHub Actions example)

```yaml
name: WeatherAI API Tests

on:
  schedule:
    - cron: '0 */6 * * *'
  push:
    branches: [ master, main ]
  pull_request:
    branches: [ master, main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/test_weatherai.py -v --html=report.html --self-contained-html
        env:
          WEATHERAI_API_KEY: ${{ secrets.WEATHERAI_API_KEY }}
          WAI_API_KEY: ${{ secrets.WEATHERAI_API_KEY }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-report
          path: report.html
```
