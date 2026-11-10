"""Workflow safety invariants (no unsafe revert / no manual dispatch)."""
import os
import re
import unittest


class PublishWorkflowSafetyTests(unittest.TestCase):
    def test_publish_workflow_has_no_automatic_revert(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github",
            "workflows",
            "publish-edition.yml",
        )
        with open(path, encoding="utf-8") as f:
            body = f.read()
        self.assertNotIn("git revert", body.lower())
        self.assertIsNone(
            re.search(r"^\s*workflow_dispatch\s*:", body, re.MULTILINE),
            "workflow must not expose workflow_dispatch trigger",
        )

    def test_publish_workflow_records_publish_sha(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".github",
            "workflows",
            "publish-edition.yml",
        )
        with open(path, encoding="utf-8") as f:
            body = f.read()
        self.assertIn("publish_sha", body)
        self.assertIn("NOT reverted", body)


if __name__ == "__main__":
    unittest.main()
