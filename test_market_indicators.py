import unittest

from market_indicators import (
    build_report,
    lead_correlations,
    monthly_average,
    monthly_changes,
    parse_fred_csv,
)


class MarketIndicatorTests(unittest.TestCase):
    def test_parse_and_average_fred_observations(self):
        text = "DATE, value\n2020-01-01,10\n2020-01-15,14\n2020-02-01,.\n"
        self.assertEqual(monthly_average(parse_fred_csv(text)), {"2020-01": 12.0})

    def test_lead_correlation_finds_one_month_lead(self):
        months = [f"{year}-{month:02d}" for year in (2020, 2021) for month in range(1, 13)]
        indicator = dict(zip(months, (float(index + 1) for index in range(24))))
        market = dict(zip(months, (float(index + 2) for index in range(24))))
        self.assertIn(1, lead_correlations(indicator, market))

    def test_report_names_copper_and_requests_provider_only_when_needed(self):
        months = [f"{year}-{month:02d}" for year in (2020, 2021) for month in range(1, 13)]
        values = dict(zip(months, (float(index + 1) for index in range(24))))
        report = build_report({"S&P 500": values, "Copper (USD/metric ton)": values})
        self.assertIn("copper is a cyclical", report)
        self.assertIn("no charting account is needed", report)

    def test_monthly_changes(self):
        self.assertAlmostEqual(monthly_changes({"2020-01": 10, "2020-02": 12})["2020-02"], 0.2)


if __name__ == "__main__":
    unittest.main()
