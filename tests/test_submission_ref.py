"""Immutable submission ref naming and idempotency keys."""
import unittest

from publish.submission_ref import submission_content_id, submission_ref_name


class SubmissionRefTests(unittest.TestCase):
    def test_same_content_same_ref(self):
        j = "a" * 64
        p = "b" * 64
        r1 = submission_ref_name("2026-11-11", j, p)
        r2 = submission_ref_name("2026-11-11", j, p)
        self.assertEqual(r1, r2)
        self.assertTrue(r1.startswith("publish/submissions/2026-11-11-"))

    def test_different_png_different_ref(self):
        j = "a" * 64
        r1 = submission_ref_name("2026-11-11", j, "b" * 64)
        r2 = submission_ref_name("2026-11-11", j, "c" * 64)
        self.assertNotEqual(r1, r2)

    def test_content_id_length(self):
        self.assertEqual(len(submission_content_id("x", "y")), 16)


if __name__ == "__main__":
    unittest.main()
