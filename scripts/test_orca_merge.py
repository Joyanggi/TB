import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from orca_merge import (
    Blocked, merge_or_queue, protected_paths, verify_branch_rules, verify_pr,
    verify_review, verify_review_pair,
)


class MergeGateTests(unittest.TestCase):
    sha = "1" * 40

    def test_review_contract_binds_verdict_to_the_worker_and_sha(self):
        dispatch = dict(id="ctx_1", runId="run_1", taskId="task_1",
                        status="completed", assigneeHandle="term_1")
        worker = {"dispatch": dispatch, "worker": {
            "state": "succeeded",
            "startOptions": {"launch": {"effective": {"agent": "claude"}}},
        }}
        report = dict(provenance="worker_report", outcome="succeeded", reportedBy="term_1",
                      filesModified=[], body=f"TB-REVIEW {self.sha} PASS")
        tasks = {"task_1": {"id": "task_1", "status": "completed", "spec": f"TB-REVIEW-TARGET {self.sha}",
                            "result": json.dumps(report)}}
        self.assertEqual(verify_review("run_1", self.sha, "claude", "ctx_1", worker, tasks), "task_1")
        for role, body in [
            ("codex", report["body"]),
            ("claude", f"TB-REVIEW {'2' * 40} PASS"),
            ("claude", f"TB-REVIEW {self.sha} BLOCK"),
            ("claude", report["body"] + "\n" + report["body"]),
            ("claude", report["body"] + "\nReview is inconclusive."),
            ("claude", " " + report["body"]),
            ("claude", report["body"] + "\n\n"),
        ]:
            with self.subTest(role=role, body=body), self.assertRaises(Blocked):
                tasks["task_1"]["result"] = json.dumps({**report, "body": body})
                verify_review("run_1", self.sha, role, "ctx_1", worker, tasks)

    def test_head_or_source_repository_change_blocks_pr(self):
        pr = dict(state="OPEN", isCrossRepository=False, baseRefName="main",
                  headRefName="orca/example", headRefOid=self.sha)
        verify_pr(pr, self.sha)
        for changes in ({"headRefOid": "2" * 40}, {"isCrossRepository": True}, {"baseRefName": "else"}):
            with self.subTest(changes=changes), self.assertRaises(Blocked):
                verify_pr({**pr, **changes}, self.sha)

    def test_initial_pair_can_pass_when_there_is_no_recheck_for_this_sha(self):
        initial = {"claude": "task_1", "codex": "task_2"}
        tasks = {
            "task_1": {"spec": f"TB-REVIEW-TARGET {self.sha}"},
            "task_2": {"spec": f"TB-REVIEW-TARGET {self.sha}"},
            "task_other": {"spec": f"TB-REVIEW-RECHECK {'2' * 40}"},
        }
        verify_review_pair(self.sha, initial, tasks)

    def test_recheck_supersedes_the_initial_pair_as_soon_as_it_is_recorded(self):
        initial = {"claude": "task_1", "codex": "task_2"}
        recheck = {"claude": "task_3", "codex": "task_4"}
        marked = {"spec": f"TB-REVIEW-TARGET {self.sha}\nTB-REVIEW-RECHECK {self.sha}"}
        tasks = {"task_1": {}, "task_2": {}, "task_3": marked}

        with self.assertRaises(Blocked):
            verify_review_pair(self.sha, initial, tasks)

        tasks["task_4"] = marked
        for stale in (initial, {"claude": "task_1", "codex": "task_4"}):
            with self.subTest(pair=stale), self.assertRaises(Blocked):
                verify_review_pair(self.sha, stale, tasks)
        verify_review_pair(self.sha, recheck, tasks)

        # Retries use the same task. An unexpected third recheck task cannot be ignored.
        tasks["task_extra"] = marked
        with self.assertRaises(Blocked):
            verify_review_pair(self.sha, recheck, tasks)

    def test_branch_rules_require_the_github_actions_publisher(self):
        checks = [dict(context="TB CI", integration_id=15368),
                  dict(context="tb/review-claude"), dict(context="tb/review-codex")]
        rules = [dict(type=kind) for kind in ("pull_request", "deletion", "non_fast_forward")]
        rules.append(dict(type="required_status_checks", parameters=dict(
            strict_required_status_checks_policy=True, required_status_checks=checks,
        )))
        verify_branch_rules(rules)
        del checks[0]["integration_id"]
        with self.assertRaises(Blocked):
            verify_branch_rules(rules)

    @patch("orca_merge.run", return_value="done")
    def test_clean_pr_merges_without_auto_flag(self, run):
        pr = dict(state="OPEN", isCrossRepository=False, baseRefName="main",
                  headRefName="orca/example", headRefOid=self.sha, mergeStateStatus="CLEAN")
        self.assertEqual(merge_or_queue(3, self.sha, lambda: pr), "done")
        run.assert_called_once_with("gh", "pr", "merge", "3", "--repo", "Joyanggi/TB",
                                    "--squash", "--match-head-commit", self.sha)

    @patch("orca_merge.run")
    def test_merges_if_checks_finish_during_auto_request(self, run):
        pr = dict(state="OPEN", isCrossRepository=False, baseRefName="main",
                  headRefName="orca/example", headRefOid=self.sha, mergeStateStatus="BLOCKED")
        get_pr = Mock(side_effect=[pr, {**pr, "mergeStateStatus": "CLEAN"}])
        run.side_effect = [subprocess.CalledProcessError(1, "gh"), "done"]
        self.assertEqual(merge_or_queue(3, self.sha, get_pr), "done")
        first, second = [call.args for call in run.call_args_list]
        self.assertEqual(first, (*second, "--auto"))
        self.assertEqual(second[-2:], ("--match-head-commit", self.sha))

    @patch("orca_merge.run")
    def test_race_does_not_merge_another_commit(self, run):
        pr = dict(state="OPEN", isCrossRepository=False, baseRefName="main",
                  headRefName="orca/example", headRefOid=self.sha, mergeStateStatus="BLOCKED")
        get_pr = Mock(side_effect=[pr, {**pr, "mergeStateStatus": "CLEAN", "headRefOid": "2" * 40}])
        run.side_effect = subprocess.CalledProcessError(1, "gh")
        with self.assertRaises(Blocked):
            merge_or_queue(3, self.sha, get_pr)
        run.assert_called_once()

    def test_policy_files_are_gated_even_when_renamed(self):
        pages = [[{"filename": "README.md"}, {"filename": "example.yml",
                                              "previous_filename": ".github/workflows/tb-ci.yml"}]]
        self.assertEqual(protected_paths(pages, 2), {".github/workflows/tb-ci.yml"})
        self.assertEqual(protected_paths([[{"filename": ".GitHub/TB.md"}]], 1), {".GitHub/TB.md"})
        for count in (None, 1, 3, 3000):
            with self.subTest(count=count), self.assertRaises(Blocked):
                protected_paths(pages, count)


if __name__ == "__main__":
    unittest.main()
