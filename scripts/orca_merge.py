#!/usr/bin/python3 -I
"""Publish two Orca verdicts for a PR head and request GitHub auto-merge."""

import argparse
import json
import re
import subprocess
from pathlib import PurePosixPath


REPO = "Joyanggi/TB"
BASE = "main"
CI = "TB CI"
GITHUB_ACTIONS_APP_ID = 15368
REVIEWERS = ("claude", "codex")
CONTEXTS = {role: f"tb/review-{role}" for role in REVIEWERS}
PROTECTED = (
    ".claude", ".github", "AGENTS.md", "CLAUDE.md", "REVIEW.md",
    "docs/development/WORKFLOW.md", "docs/development/PR-ISSUE-GUIDE.md",
    "docs/quality", "docs/product/PRD.md", "docs/product/REQUIREMENTS.md",
    "docs/decisions", "supabase/migrations", "scripts/orca_merge.py",
    "scripts/test_orca_merge.py",
)


class Blocked(Exception):
    """A precondition for publishing or merging is missing."""


def run(*argv):
    return subprocess.run(argv, check=True, text=True, stdout=subprocess.PIPE).stdout


def github(*args):
    return json.loads(run("gh", "api", *args))


def orca(verb, flag, value):
    response = json.loads(run(
        "orca", "orchestration", verb, "--environment", "local", flag, value, "--json", "--full"
    ))
    if not response.get("ok"):
        raise Blocked(f"Orca rejected {verb}.")
    return response["result"]


def verify_review(run_id, sha, role, dispatch_id, worker, tasks):
    dispatch = worker.get("dispatch") or {}
    details = worker.get("worker") or {}
    launch = (details.get("startOptions") or {}).get("launch") or {}
    task = tasks.get(dispatch.get("taskId"), {})
    if (
        dispatch.get("id") != dispatch_id or dispatch.get("runId") != run_id
        or dispatch.get("status") != "completed" or details.get("state") != "succeeded"
        or (launch.get("effective") or {}).get("agent") != role
        or task.get("status") != "completed"
    ):
        raise Blocked(f"{role} lacks a completed review dispatch in this run.")
    report = json.loads(task.get("result") or "{}")
    if (
        report.get("provenance") != "worker_report" or report.get("outcome") != "succeeded"
        or not dispatch.get("assigneeHandle") or report.get("reportedBy") != dispatch["assigneeHandle"]
        or report.get("filesModified") != []
        or f"TB-REVIEW-TARGET {sha}" not in (task.get("spec") or "").splitlines()
    ):
        raise Blocked(f"{role} did not return an attributable read-only report for this SHA.")
    lines = [line.strip() for line in (report.get("body") or "").splitlines() if line.strip()]
    decision = f"TB-REVIEW {sha} PASS"
    markers = [line for line in lines if line.startswith("TB-REVIEW ")]
    if not lines or lines[-1] != decision or markers != [decision]:
        raise Blocked(f"{role} did not pass the requested commit.")
    return task["id"]


def protected_paths(pages):
    paths = set()
    for page in pages:
        for change in page:
            for field in ("filename", "previous_filename"):
                if change.get(field):
                    paths.add(PurePosixPath(change[field]))
    return paths.intersection(map(PurePosixPath, PROTECTED)) | {
        path for path in paths if any(PurePosixPath(item) in path.parents for item in PROTECTED)
    }


def verify_pr(pr, sha):
    if (
        pr.get("state") != "OPEN" or pr.get("isCrossRepository") is not False
        or pr.get("baseRefName") != BASE or not pr.get("headRefName", "").startswith("orca/")
        or pr.get("headRefOid") != sha
    ):
        raise Blocked("The PR must be open, target main, and have the reviewed orca/ head.")


def verify_branch_rules(rules):
    by_type = {rule["type"]: rule for rule in rules}
    status = (by_type.get("required_status_checks") or {}).get("parameters") or {}
    contexts = {check.get("context"): check for check in status.get("required_status_checks", [])}
    if (
        "pull_request" not in by_type or "non_fast_forward" not in by_type
        or "deletion" not in by_type or not status.get("strict_required_status_checks_policy")
        or not set(CONTEXTS.values()).issubset(contexts)
        or contexts.get(CI, {}).get("integration_id") != GITHUB_ACTIONS_APP_ID
    ):
        raise Blocked("main is missing the PR-only or required-check protection.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--claude", required=True)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if (
        args.pr < 1 or not re.fullmatch(r"[a-f0-9]{40}", args.sha)
        or not re.fullmatch(r"run_[a-z0-9]+", args.run)
        or not all(re.fullmatch(r"ctx_[a-z0-9]+", ref) for ref in (args.claude, args.codex))
        or args.claude == args.codex
    ):
        parser.error("Expected a PR number, full Git SHA, Orca run and two distinct dispatch IDs.")

    def get_pr():
        return json.loads(run(
            "gh", "pr", "view", str(args.pr), "--repo", REPO, "--json",
            "baseRefName,headRefName,headRefOid,isCrossRepository,isDraft,state,url",
        ))

    try:
        pr = get_pr()
        verify_pr(pr, args.sha)
        verify_branch_rules(github(f"repos/{REPO}/rules/branches/{BASE}"))
        tasks = {task["id"]: task for task in orca("task-list", "--run", args.run)["tasks"]}
        task_ids = {
            role: verify_review(args.run, args.sha, role, getattr(args, role),
                                orca("worker-show", "--dispatch", getattr(args, role)), tasks)
            for role in REVIEWERS
        }
        if len(set(task_ids.values())) != len(REVIEWERS):
            raise Blocked("The two reviews must be separate tasks.")
        if args.verify_only:
            print(json.dumps({"sha": args.sha, "reviews": task_ids, "pr": pr["url"]}))
            return
        if github("user").get("login", "").casefold() != REPO.split("/", 1)[0].casefold():
            raise Blocked("Only the configured coordinator GitHub account may publish the checks.")
        paths = protected_paths(github(
            f"repos/{REPO}/pulls/{args.pr}/files?per_page=100", "--paginate", "--slurp"
        ))
        if paths:
            raise Blocked("Automation policy changes require owner review: " + ", ".join(map(str, sorted(paths))))
        pr = get_pr()
        verify_pr(pr, args.sha)
        for role, task_id in task_ids.items():
            github(
                "-X", "POST", f"repos/{REPO}/statuses/{args.sha}",
                "-f", "state=success", "-f", f"context={CONTEXTS[role]}",
                "-f", f"description=Orca independent review passed ({task_id})",
                "-f", f"target_url={pr['url']}",
            )
        if pr["isDraft"]:
            run("gh", "pr", "ready", str(args.pr), "--repo", REPO)
        print(run(
            "gh", "pr", "merge", str(args.pr), "--repo", REPO,
            "--squash", "--auto", "--match-head-commit", args.sha,
        ).strip() or pr["url"])
    except (Blocked, OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        parser.exit(1, f"Auto-merge blocked: {exc}\n")


if __name__ == "__main__":
    main()
