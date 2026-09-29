"""Measure whether copper leads the US equity market.

The module deliberately uses only the Python standard library.  FRED's public
CSV endpoint is used for data, so an API key or charting account is not
required.  The calculations are kept as small, testable functions so another
data source can be supplied by callers.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable, Mapping


FRED_SERIES = {
    "Copper (USD/metric ton)": "PCOPPUSDM",
    "S&P 500": "SP500",
    "WTI oil (USD/barrel)": "DCOILWTICO",
    "Consumer sentiment": "UMCSENT",
    "Yield spread (10Y-2Y)": "T10Y2Y",
    "VIX": "VIXCLS",
}


def fred_csv(series_id: str, start: str = "1990-01-01") -> str:
    """Download one FRED series as CSV."""
    query = urllib.parse.urlencode({"cosd": start})
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "livermore-market-analysis/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_fred_csv(csv_text: str) -> dict[str, float]:
    """Parse FRED dates and values, ignoring missing observations."""
    values: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            raw_value = next(value for key, value in row.items() if key != "DATE")
            values[row["DATE"]] = float(raw_value.strip())
        except (KeyError, StopIteration, TypeError, ValueError):
            continue
    return values


def monthly_average(values: Mapping[str, float]) -> dict[str, float]:
    """Convert daily or irregular observations to calendar-month averages."""
    buckets: dict[str, list[float]] = {}
    for timestamp, value in values.items():
        buckets.setdefault(timestamp[:7], []).append(value)
    return {month: sum(items) / len(items) for month, items in buckets.items()}


def monthly_changes(values: Mapping[str, float]) -> dict[str, float]:
    """Return month-over-month percentage changes for a monthly level series."""
    months = sorted(values)
    return {
        month: (values[month] / values[previous] - 1.0)
        for previous, month in zip(months, months[1:])
        if values[previous] > 0 and values[month] > 0
    }


def pearson(x: Iterable[float], y: Iterable[float]) -> float:
    """Calculate Pearson correlation, returning 0 for insufficient variance."""
    left, right = list(x), list(y)
    if len(left) != len(right) or len(left) < 3:
        return 0.0
    mean_x, mean_y = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - mean_x) ** 2 for a in left) * sum((b - mean_y) ** 2 for b in right)
    )
    return numerator / denominator if denominator else 0.0


def lead_correlations(
    indicator: Mapping[str, float],
    market: Mapping[str, float],
    max_lead_months: int = 12,
) -> dict[int, float]:
    """Correlate an indicator's change with equity returns 1..N months later."""
    indicator_change = monthly_changes(indicator)
    market_change = monthly_changes(market)
    correlations: dict[int, float] = {}
    for lead in range(1, max_lead_months + 1):
        pairs = [
            (indicator_change[month], market_change[later_month])
            for month in indicator_change
            if (later_month := _month_offset(month, lead)) in market_change
        ]
        if len(pairs) >= 12:
            correlations[lead] = pearson((p[0] for p in pairs), (p[1] for p in pairs))
    return correlations


def _month_offset(month: str, offset: int) -> str:
    year, month_number = map(int, month.split("-"))
    month_number += offset
    year += (month_number - 1) // 12
    month_number = (month_number - 1) % 12 + 1
    return f"{year:04d}-{month_number:02d}"


def summarize(name: str, correlations: Mapping[int, float]) -> str:
    """Produce a cautious interpretation suitable for a human-readable report."""
    if not correlations:
        return f"{name}: insufficient overlapping observations."
    lead, correlation = max(correlations.items(), key=lambda item: abs(item[1]))
    strength = "strong" if abs(correlation) >= 0.5 else "moderate" if abs(correlation) >= 0.3 else "weak"
    return (
        f"{name}: best {lead}-month lead, Pearson r={correlation:+.2f} "
        f"({strength}; changes, not levels)."
    )


def build_report(series: Mapping[str, Mapping[str, float]]) -> str:
    """Build an analysis report from named monthly series."""
    market = monthly_average(series["S&P 500"])
    lines = [
        "US stock-market leading-indicator analysis",
        "Method: monthly percentage changes; Pearson correlation with S&P 500 returns 1–12 months later.",
        "",
    ]
    results: dict[str, dict[int, float]] = {}
    for name, values in series.items():
        if name == "S&P 500":
            continue
        results[name] = lead_correlations(monthly_average(values), market)
        lines.append(summarize(name, results[name]))
    copper = results.get("Copper (USD/metric ton)", {})
    if copper:
        best = max(copper.values(), key=abs)
        lines.extend(
            [
                "",
                "Conclusion: copper is a cyclical risk/industrial-demand signal, not a dependable "
                "standalone forecast of US equities. Treat it as useful only when confirmed by "
                "the yield curve, credit/volatility, and macro data.",
                f"Copper's strongest observed 1–12 month relationship was r={best:+.2f}; "
                "this is correlation, not causation, and is sensitive to the sample period.",
            ]
        )
    lines.extend(
        [
            "",
            "Charting: no charting account is needed for this public-data report. If you want "
            "interactive TradingView/Bloomberg charts, tell me which provider/account you use; "
            "do not share credentials.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="1990-01-01", help="FRED start date (YYYY-MM-DD)")
    args = parser.parse_args()
    try:
        series = {
            name: parse_fred_csv(fred_csv(series_id, args.start))
            for name, series_id in FRED_SERIES.items()
        }
    except urllib.error.URLError as error:
        print(f"Unable to download FRED data: {error.reason}", file=sys.stderr)
        raise SystemExit(2)
    print(build_report(series))


if __name__ == "__main__":
    main()
