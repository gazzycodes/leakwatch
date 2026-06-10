import json
import unittest

from leakwatch.classify import classify_hosts
from leakwatch.model import ScanResult
from leakwatch.report import (
    diff_against_baseline,
    render_json,
    render_scorecard,
    render_text,
)
from leakwatch.score import compute_verdict


def _scan(url, hosts):
    result = ScanResult(url=url, final_url=url)
    result.trackers, result.companies = classify_hosts(hosts, "example.com")
    result.verdict = compute_verdict(result)
    return result


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.result = _scan(
            "https://example.com",
            ["www.google-analytics.com", "bluekai.com", "static.hotjar.com"],
        )

    def test_render_text_contains_companies(self):
        text = render_text(self.result)
        self.assertIn("leakwatch", text)
        self.assertIn("Google", text)
        self.assertIn("leakage score", text)

    def test_render_json_is_valid(self):
        payload = json.loads(render_json(self.result))
        self.assertEqual(payload["url"], "https://example.com")
        self.assertIn("verdict", payload)
        self.assertGreater(len(payload["trackers"]), 0)

    def test_scorecard_ranks_worst_first(self):
        clean = _scan("https://clean.example", [])
        card = render_scorecard([clean, self.result], fmt="text")
        worst_line = card.splitlines()[3]
        self.assertIn("example.com", worst_line)

    def test_scorecard_markdown(self):
        card = render_scorecard([self.result], fmt="markdown")
        self.assertIn("| # | Site |", card)

    def test_diff_detects_new_tracker(self):
        baseline = {"trackers": [{"domain": "google-analytics.com"}]}
        new = diff_against_baseline(self.result, baseline)
        self.assertIn("bluekai.com", new)
        self.assertNotIn("google-analytics.com", new)


if __name__ == "__main__":
    unittest.main()
