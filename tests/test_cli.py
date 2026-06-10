import unittest

from leakwatch.cli import _preprocess, _read_url_list


class PreprocessTests(unittest.TestCase):
    def test_bare_url_becomes_scan(self):
        self.assertEqual(_preprocess(["example.com"]), ["scan", "example.com"])

    def test_url_with_flags_becomes_scan(self):
        self.assertEqual(
            _preprocess(["example.com", "--json"]), ["scan", "example.com", "--json"]
        )

    def test_known_command_untouched(self):
        self.assertEqual(_preprocess(["batch", "sites.txt"]), ["batch", "sites.txt"])

    def test_help_untouched(self):
        self.assertEqual(_preprocess(["--help"]), ["--help"])


class UrlListTests(unittest.TestCase):
    def test_reads_and_filters(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("# comment\nexample.com\n\n  nytimes.com  \n")
            path = handle.name
        self.assertEqual(_read_url_list(path), ["example.com", "nytimes.com"])


if __name__ == "__main__":
    unittest.main()
