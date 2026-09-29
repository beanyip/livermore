# Livermore

## Copper and US-stock leading-indicator analysis

Run the dependency-free report (it downloads public monthly/daily observations
from FRED):

```bash
python market_indicators.py --start 1990-01-01
```

The report converts levels to month-over-month changes, then tests whether each
indicator correlates with S&P 500 returns one through twelve months later. It
reports copper alongside oil, consumer sentiment, the 10-year/2-year yield
spread, and VIX. This is a screening tool, not investment advice: correlations
can change by regime, and copper is affected by China, supply disruptions, the
dollar, and financial speculation.

No charting account is needed because the input is public FRED data. For
interactive TradingView or Bloomberg charts, provide the charting provider (not
credentials) and the desired account context.

Run focused tests with:

```bash
python -m unittest test_market_indicators.py
```