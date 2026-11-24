import io
import json
import subprocess
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from orca_merge import (
    Blocked, merge_or_queue, process_pr, protected_paths, recheck_context, registered_recheck,
    verify_branch_rules, verify_pr, verify_review, verify_review_pair,
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
        with self.assertRaises(Blocked):
            verify_review_pair(self.sha, initial, tasks, must_recheck=True)

    def test_recheck_supersedes_the_initial_pair_as_soon_as_it_is_recorded(self):
        initial = {"claude": "task_1", "codex": "task_2"}
        recheck = {"claude": "task_3", "codex": "task_4"}
        marked = {"spec": f"TB-REVIEW-TARGET {self.sha}\n  TB-REVIEW-RECHECK {self.sha} "}
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

    @patch("orca_merge.orca")
    @patch("orca_merge.verify_branch_rules")
    @patch("orca_merge.registered_recheck", side_effect=[None, "run_recheck", "run_recheck"])
    @patch("orca_merge.github")
    @patch("orca_merge.run")
    def test_registration_is_published_once_and_blocks_another_run(
        self, run, github, registration, verify_branch_rules, orca,
    ):
        pr = dict(state="OPEN", isCrossRepository=False, baseRefName="main",
                  headRefName="orca/example", headRefOid=self.sha, isDraft=True, url="https://example.invalid")
        run.return_value = json.dumps(pr)
        github.return_value = {"login": "Joyanggi"}
        args = Namespace(pr=6, sha=self.sha, run="run_recheck", require_recheck=True)
        with redirect_stdout(io.StringIO()):
            process_pr(args)
            process_pr(args)
            orca.assert_called_once_with("run-show", "--id", "run_recheck")
            posts = [call.args for call in github.call_args_list if call.args[:1] == ("-X",)]
            self.assertEqual(len(posts), 1)
            self.assertIn(f"context={recheck_context(args.pr)}", posts[0])

            old_run = Namespace(pr=args.pr, sha=self.sha, run="run_initial", require_recheck=False)
            with self.assertRaisesRegex(Blocked, "run registered"):
                process_pr(old_run)
            orca.assert_called_once()

    @patch("orca_merge.github")
    def test_registration_uses_paginated_github_history_and_checks_the_publisher(self, github):
        entry = dict(context=recheck_context(6), description="Orca run run_recheck",
                     state="success", creator={"login": "Joyanggi"})
        github.return_value = [[{**entry, "context": recheck_context(7)}], [entry]]
        self.assertEqual(registered_recheck(6, self.sha), "run_recheck")
        github.assert_called_once_with(
            f"repos/Joyanggi/TB/commits/{self.sha}/statuses?per_page=100", "--paginate", "--slurp",
        )
        self.assertIsNone(registered_recheck(8, self.sha))
        for bad in ({"creator": {"login": "other"}}, {"description": "Orca run run_other"},
                    {"state": "failure"}):
            github.return_value = [[entry], [{**entry, **bad}]]
            with self.subTest(bad=bad), self.assertRaises(Blocked):
                registered_recheck(6, self.sha)

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
