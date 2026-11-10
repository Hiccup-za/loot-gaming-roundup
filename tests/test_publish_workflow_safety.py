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
        dispatch = re.search(
            r"workflow_dispatch:\s*\n\s*inputs:\s*\n\s*submission_sha:",
            body,
        )
        self.assertIsNotNone(
            dispatch,
            "only workflow_dispatch allowed is validated submission_sha replay",
        )
        self.assertNotIn("edition_date", body.split("workflow_dispatch")[1][:400])

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
        self.assertIn("not auto-reverted", body.lower())


if __name__ == "__main__":
    unittest.main()
