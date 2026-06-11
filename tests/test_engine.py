import unittest

from leakwatch.engine import _looks_blocked, _normalise_url


class NormaliseTests(unittest.TestCase):
    def test_adds_scheme(self):
        self.assertEqual(_normalise_url("example.com"), "https://example.com")

    def test_keeps_scheme(self):
        self.assertEqual(_normalise_url("http://example.com"), "http://example.com")


class BlockDetectionTests(unittest.TestCase):
    def test_blocked_status(self):
        blocked, reason = _looks_blocked(403, "Home")
        self.assertTrue(blocked)
        self.assertIn("403", reason)

    def test_blocked_title_cloudflare(self):
        blocked, reason = _looks_blocked(200, "Just a moment...")
        self.assertTrue(blocked)
        self.assertIn("challenge", reason.lower())

    def test_blocked_title_captcha(self):
        blocked, _ = _looks_blocked(200, "Please complete the CAPTCHA")
        self.assertTrue(blocked)

    def test_not_blocked(self):
        blocked, reason = _looks_blocked(200, "The New York Times")
        self.assertFalse(blocked)
        self.assertEqual(reason, "")

    def test_none_status_ok(self):
        blocked, _ = _looks_blocked(None, "Welcome")
        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
