# Task 3 Evidence — Failure / Regression Coverage

Coverage included the negative paths exercised by the focused test run:

- invalid stash valuation request handling in `tests/unit/test_api_stash_valuations.py`
- empty fallback / zero-comparable helper behavior in `tests/unit/test_valuation_helpers.py`
- pricing-outliers regression checks in `tests/test_pricing_outliers.py`
- price-check comparable query stability in `tests/test_price_check_comparables.py`

Verified command:

```bash
.venv/bin/pytest tests/unit/test_valuation_helpers.py tests/unit/test_api_stash_valuations.py tests/test_price_check_comparables.py tests/test_pricing_outliers.py
```

Result: 24 passed.
