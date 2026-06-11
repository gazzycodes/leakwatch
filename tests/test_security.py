import unittest

from leakwatch.security import (
    audit_headers,
    header_grade,
    missing_headers,
)


class AuditTests(unittest.TestCase):
    def test_all_present_grades_a(self):
        headers = {
            "strict-transport-security": "max-age=63072000",
            "content-security-policy": "default-src 'self'",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
            "permissions-policy": "geolocation=()",
        }
        findings = audit_headers(headers)
        self.assertTrue(all(f.present for f in findings))
        self.assertEqual(header_grade(findings), "A")
        self.assertEqual(missing_headers(findings), [])

    def test_none_present_grades_f(self):
        findings = audit_headers({})
        self.assertTrue(all(not f.present for f in findings))
        self.assertEqual(header_grade(findings), "F")
        self.assertEqual(len(missing_headers(findings)), 6)

    def test_case_insensitive(self):
        findings = audit_headers({"Strict-Transport-Security": "max-age=1"})
        hsts = next(f for f in findings if f.name == "HSTS")
        self.assertTrue(hsts.present)

    def test_partial_grade_between(self):
        # The two high-severity headers present, rest missing.
        headers = {
            "strict-transport-security": "max-age=1",
            "content-security-policy": "default-src 'self'",
        }
        grade = header_grade(audit_headers(headers))
        self.assertIn(grade, {"B", "C"})


if __name__ == "__main__":
    unittest.main()
