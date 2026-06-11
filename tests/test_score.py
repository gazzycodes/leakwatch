import unittest

from leakwatch.classify import classify_hosts
from leakwatch.model import (
    CONSENT_ACCEPTED,
    Fingerprint,
    Request,
    ScanResult,
)
from leakwatch.score import compute_verdict


def _result_with(hosts, *, fingerprints=None, before_consent=False, consent_state="none"):
    result = ScanResult(url="https://example.com", consent_state=consent_state)
    result.requests = [
        Request(
            url="https://" + h + "/x",
            host=h,
            method="GET",
            resource_type="script",
            is_third_party=True,
            elapsed_ms=10,
            before_consent=before_consent,
        )
        for h in hosts
    ]
    result.fingerprints = fingerprints or []
    result.trackers, result.companies = classify_hosts(hosts, "example.com")
    return result


class ScoreTests(unittest.TestCase):
    def test_clean_site_scores_zero(self):
        result = ScanResult(url="https://example.com")
        verdict = compute_verdict(result)
        self.assertEqual(verdict.score, 0)
        self.assertEqual(verdict.grade, "A")
        self.assertIn("No known trackers", verdict.headline)

    def test_brokers_and_replay_raise_score(self):
        result = _result_with(
            ["bluekai.com", "static.hotjar.com", "www.google-analytics.com"]
        )
        verdict = compute_verdict(result)
        self.assertGreater(verdict.score, 25)
        self.assertEqual(verdict.broker_count, 1)
        self.assertTrue(verdict.records_screen)
        self.assertIn("records your screen", verdict.headline)

    def test_fingerprint_counted(self):
        result = _result_with(
            ["www.google-analytics.com"],
            fingerprints=[Fingerprint("canvas", "canvas.toDataURL", count=3)],
        )
        verdict = compute_verdict(result)
        self.assertEqual(verdict.fingerprint_count, 1)
        self.assertIn("fingerprints you", verdict.headline)

    def test_pre_consent_only_counts_when_consent_accepted(self):
        # Banner was found and accepted -> the pre-consent trackers count.
        accepted = _result_with(
            ["stats.g.doubleclick.net"],
            before_consent=True,
            consent_state=CONSENT_ACCEPTED,
        )
        verdict = compute_verdict(accepted)
        self.assertEqual(verdict.pre_consent_count, 1)
        self.assertIn("before consent", verdict.headline)

    def test_no_banner_means_no_pre_consent_claim(self):
        # No consent banner -> we must not claim "fired before consent".
        none = _result_with(["stats.g.doubleclick.net"], before_consent=True)
        verdict = compute_verdict(none)
        self.assertEqual(verdict.pre_consent_count, 0)
        self.assertNotIn("before consent", verdict.headline)

    def test_score_capped(self):
        hosts = list(
            {
                "bluekai.com",
                "rlcdn.com",
                "crwdcntrl.net",
                "static.hotjar.com",
                "fullstory.com",
                "doubleclick.net",
            }
        )
        verdict = compute_verdict(_result_with(hosts))
        self.assertLessEqual(verdict.score, 100)
        self.assertEqual(verdict.grade, "F")


if __name__ == "__main__":
    unittest.main()
