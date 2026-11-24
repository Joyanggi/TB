#!/usr/bin/python3 -I
"""Publish two Orca verdicts for a PR head and request GitHub auto-merge."""

import argparse
import fcntl
import json
import os
import re
import subprocess
import unicodedata
from contextlib import contextmanager
from pathlib import Path, PurePosixPath


REPO = "Joyanggi/TB"
BASE = "main"
CI = "TB CI"
GITHUB_ACTIONS_APP_ID = 15368
REVIEWERS = ("claude", "codex")
CONTEXTS = {role: f"tb/review-{role}" for role in REVIEWERS}
REVIEW_RECORDS = Path.home() / "Library" / "Application Support" / "tb-orca-merge" / "rechecks"
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
    lines = (report.get("body") or "").splitlines()
    decision = f"TB-REVIEW {sha} PASS"
    markers = [line for line in lines if line.lstrip().startswith("TB-REVIEW ")]
    if not lines or lines[-1] != decision or markers != [decision]:
        raise Blocked(f"{role} did not pass the requested commit.")
    return task["id"]


def verify_review_pair(sha, task_ids, tasks, *, must_recheck=False):
    selected = set(task_ids.values())
    if len(selected) != len(REVIEWERS):
        raise Blocked("The two reviews must be separate tasks.")
    marker = f"TB-REVIEW-RECHECK {sha}"
    rechecks = {
        task_id for task_id, task in tasks.items()
        if marker in map(str.strip, (task.get("spec") or "").splitlines())
    }
    # A recorded recheck supersedes the first pair even before either recheck finishes.
    if (must_recheck or rechecks) and selected != rechecks:
        raise Blocked("Both PASS reports must come from the disagreement recheck for this SHA.")


@contextmanager
def review_record(pr_number, sha):
    REVIEW_RECORDS.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (REVIEW_RECORDS / f"{pr_number}-{sha}").open("a+", encoding="utf-8") as record:
        fcntl.flock(record, fcntl.LOCK_EX)
        record.seek(0)
        yield record


def protected_paths(pages, expected_count):
    changes = [change for page in pages for change in page]
    # GitHub returns at most 3,000 files, irrespective of pagination.
    if not isinstance(expected_count, int) or not 0 < expected_count < 3000 or len(changes) != expected_count:
        raise Blocked("The complete PR file list could not be verified.")
    guarded = {PurePosixPath(item.casefold()) for item in PROTECTED}
    paths = set()
    for change in changes:
        for field in ("filename", "previous_filename"):
            raw_path = change.get(field)
            if not raw_path:
                continue
            path = PurePosixPath(unicodedata.normalize("NFC", raw_path).casefold())
            if path in guarded or guarded.intersection(path.parents):
                paths.add(raw_path)
    return paths


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


def merge_or_queue(pr_number, sha, get_pr):
    command = ("gh", "pr", "merge", str(pr_number), "--repo", REPO,
               "--squash", "--match-head-commit", sha)
    pr = get_pr()
    verify_pr(pr, sha)
    if pr.get("mergeStateStatus") == "CLEAN":
        return run(*command)
    try:
        return run(*command, "--auto")
    except subprocess.CalledProcessError:
        # The last required check can settle while GitHub is receiving the request.
        pr = get_pr()
        if pr.get("state") == "MERGED" and pr.get("headRefOid") == sha:
            return pr["url"]
        verify_pr(pr, sha)
        if pr.get("mergeStateStatus") != "CLEAN":
            raise
        return run(*command)


def process_pr(args, record):
    def get_pr():
        return json.loads(run(
            "gh", "pr", "view", str(args.pr), "--repo", REPO, "--json",
            "baseRefName,headRefName,headRefOid,isCrossRepository,isDraft,state,url,changedFiles,mergeStateStatus",
        ))

    registered_run = record.read()
    if registered_run and registered_run != f"{args.run}\n":
        raise Blocked("This PR head must use the Orca run registered for disagreement recheck.")
    pr = get_pr()
    verify_pr(pr, args.sha)
    verify_branch_rules(github(f"repos/{REPO}/rules/branches/{BASE}"))
    if args.require_recheck:
        if pr.get("isDraft") is not True:
            raise Blocked("Register a disagreement recheck while the PR is in draft.")
        if not registered_run:
            orca("run-show", "--id", args.run)
            record.write(f"{args.run}\n")
            record.flush()
            os.fsync(record.fileno())
        print(json.dumps({"sha": args.sha, "recheckRun": args.run, "pr": pr["url"]}))
        return
    tasks = {task["id"]: task for task in orca("task-list", "--run", args.run)["tasks"]}
    task_ids = {
        role: verify_review(args.run, args.sha, role, getattr(args, role),
                            orca("worker-show", "--dispatch", getattr(args, role)), tasks)
        for role in REVIEWERS
    }
    verify_review_pair(args.sha, task_ids, tasks, must_recheck=bool(registered_run))
    if args.verify_only:
        print(json.dumps({"sha": args.sha, "reviews": task_ids, "pr": pr["url"]}))
        return
    if github("user").get("login", "").casefold() != REPO.split("/", 1)[0].casefold():
        raise Blocked("Only the configured coordinator GitHub account may publish the checks.")
    pages = github(f"repos/{REPO}/pulls/{args.pr}/files?per_page=100", "--paginate", "--slurp")
    paths = protected_paths(pages, pr.get("changedFiles"))
    if paths:
        raise Blocked("Automation policy changes require owner review: " + ", ".join(sorted(paths)))
    pr = get_pr()
    verify_pr(pr, args.sha)
    for role, task_id in task_ids.items():
        github(
            "-X", "POST", f"repos/{REPO}/statuses/{args.sha}",
            "-f", "state=success", "-f", f"context={CONTEXTS[role]}",
            "-f", f"description=Orca review passed ({task_id})",
            "-f", f"target_url={pr['url']}",
        )
    if pr["isDraft"]:
        run("gh", "pr", "ready", str(args.pr), "--repo", REPO)
    print(merge_or_queue(args.pr, args.sha, get_pr).strip() or pr["url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--claude")
    parser.add_argument("--codex")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--require-recheck", action="store_true")
    args = parser.parse_args()
    if (
        args.pr < 1 or not re.fullmatch(r"[a-f0-9]{40}", args.sha)
        or not re.fullmatch(r"run_[a-z0-9]+", args.run)
    ):
        parser.error("Expected a PR number, full Git SHA and Orca run.")
    refs = (args.claude, args.codex)
    if args.require_recheck:
        if any(ref is not None for ref in refs):
            parser.error("Register a recheck without dispatch IDs.")
    elif not all(ref and re.fullmatch(r"ctx_[a-z0-9]+", ref) for ref in refs) or refs[0] == refs[1]:
        parser.error("Expected two distinct review dispatch IDs.")

    try:
        with review_record(args.pr, args.sha) as record:
            process_pr(args, record)
    except (Blocked, OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        parser.exit(1, f"Auto-merge blocked: {exc}\n")


if __name__ == "__main__":
    main()
