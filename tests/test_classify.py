import unittest

from leakwatch.classify import (
    classify_host,
    classify_hosts,
    count_brokers,
    host_from_url,
    is_session_replay,
    is_third_party,
    registrable_domain,
)


class HostParsingTests(unittest.TestCase):
    def test_host_from_url(self):
        self.assertEqual(host_from_url("https://www.Example.com/path"), "www.example.com")
        self.assertEqual(host_from_url("not a url"), "")

    def test_registrable_domain_simple(self):
        self.assertEqual(registrable_domain("www.example.com"), "example.com")
        self.assertEqual(registrable_domain("a.b.c.example.com"), "example.com")

    def test_registrable_domain_multi_suffix(self):
        self.assertEqual(registrable_domain("www.bbc.co.uk"), "bbc.co.uk")

    def test_is_third_party(self):
        self.assertTrue(is_third_party("doubleclick.net", "example.com"))
        self.assertFalse(is_third_party("cdn.example.com", "example.com"))
        self.assertFalse(is_third_party("", "example.com"))


class ClassifyTests(unittest.TestCase):
    def test_known_tracker(self):
        hit = classify_host("stats.g.doubleclick.net")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.entity, "Google")
        self.assertEqual(hit.category, "advertising")

    def test_subdomain_match(self):
        hit = classify_host("connect.facebook.net")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.entity, "Meta")

    def test_unknown_host(self):
        self.assertIsNone(classify_host("totally-unknown-domain.example"))

    def test_session_replay_flag(self):
        self.assertTrue(is_session_replay("script.hotjar.com"))
        self.assertFalse(is_session_replay("example.com"))

    def test_rollup_and_brokers(self):
        hosts = [
            "www.google-analytics.com",
            "stats.g.doubleclick.net",
            "connect.facebook.net",
            "tags.bluekai.com",
        ]
        hits, companies = classify_hosts(hosts, "example.com")
        names = {c.name for c in companies}
        self.assertIn("Google", names)
        self.assertIn("Meta", names)
        self.assertIn("Oracle", names)
        self.assertEqual(count_brokers(hits), 1)


if __name__ == "__main__":
    unittest.main()
