import json
import unittest

from leakwatch.classify import classify_hosts
from leakwatch.model import (
    CONSENT_ACCEPTED,
    CONSENT_PRESENT,
    CONSENT_SKIPPED,
    ScanResult,
)
from leakwatch.report import (
    consent_label,
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
        self.assertIn("consent:", text)

    def test_render_text_shows_blocked(self):
        self.result.blocked = True
        self.result.blocked_reason = "server returned HTTP 403"
        text = render_text(self.result)
        self.assertIn("blocked", text)
        self.assertIn("403", text)

    def test_render_json_is_valid(self):
        payload = json.loads(render_json(self.result))
        self.assertEqual(payload["url"], "https://example.com")
        self.assertIn("verdict", payload)
        self.assertIn("consent_state", payload)
        self.assertIn("blocked", payload)
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


class ConsentLabelTests(unittest.TestCase):
    def test_accepted_with_cmp(self):
        r = ScanResult(url="x", consent_state=CONSENT_ACCEPTED, consent_cmp="OneTrust")
        self.assertEqual(consent_label(r), "accepted (OneTrust)")

    def test_skipped(self):
        r = ScanResult(url="x", consent_state=CONSENT_SKIPPED)
        self.assertEqual(consent_label(r), "skipped")

    def test_none(self):
        self.assertEqual(consent_label(ScanResult(url="x")), "no banner detected")

    def test_present_not_accepted(self):
        r = ScanResult(url="x", consent_state=CONSENT_PRESENT, consent_cmp="IAB TCF")
        label = consent_label(r)
        self.assertIn("banner present", label)
        self.assertIn("IAB TCF", label)


if __name__ == "__main__":
    unittest.main()
