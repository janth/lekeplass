#!/usr/bin/env python3
"""Check git working tree and pull request status.

Usage: python git_pr_check.py

This script uses `git` for local checks, `gh` (if available) for PR queries,
and falls back to the GitHub REST API when needed (requires `GITHUB_TOKEN`).
The script now lives at the repository root as `git_pr_check.py` (not in
`scripts/`).
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
from typing import Optional, Tuple

try:
    import requests
except Exception:
    requests = None


def run(cmd: str, capture_output=True, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(shlex.split(cmd), capture_output=capture_output, text=True)


def repo_root() -> str:
    p = run("git rev-parse --show-toplevel")
    if p.returncode != 0:
        raise RuntimeError("Not a git repository")
    return p.stdout.strip()


def working_tree_clean() -> bool:
    p = run("git status --porcelain")
    return p.returncode == 0 and p.stdout.strip() == ""


def current_branch() -> str:
    p = run("git rev-parse --abbrev-ref HEAD")
    if p.returncode != 0:
        raise RuntimeError("Failed to get current branch")
    return p.stdout.strip()


def upstream_branch() -> Optional[str]:
    p = run("git rev-parse --abbrev-ref --symbolic-full-name @{u}")
    if p.returncode != 0:
        return None
    return p.stdout.strip()


def ahead_behind(ref_a: str, ref_b: str) -> Tuple[int, int]:
    # returns (ahead, behind) where ahead = commits in ref_a not in ref_b
    p = run(f"git rev-list --left-right --count {ref_a}...{ref_b}")
    if p.returncode != 0:
        return (0, 0)
    parts = p.stdout.strip().split()
    if len(parts) != 2:
        return (0, 0)
    left, right = int(parts[0]), int(parts[1])
    # left = commits only in ref_a, right = commits only in ref_b
    return (left, right)


def origin_default_branch() -> Optional[str]:
    p = run("git remote show origin")
    if p.returncode != 0:
        return None
    for line in p.stdout.splitlines():
        if "HEAD branch:" in line:
            return line.split(":", 1)[1].strip()
    return None


def git_remote_owner_repo() -> Tuple[Optional[str], Optional[str]]:
    p = run("git remote get-url origin")
    if p.returncode != 0:
        return (None, None)
    url = p.stdout.strip()
    # handle ssh and https
    if url.startswith("git@"):
        # git@github.com:owner/repo.git
        _, path = url.split(":", 1)
    elif url.startswith("https://") or url.startswith("http://"):
        parts = url.split("/")
        path = "/".join(parts[-2:])
    else:
        path = url
    if path.endswith(".git"):
        path = path[:-4]
    if "/" in path:
        owner, repo = path.split("/", 1)
        return owner, repo
    return (None, None)


def run_gh_pr_view_by_branch(branch: str) -> Optional[dict]:
    if not shutil.which("gh"):
        return None
    p = run(f"gh pr view --json number,headRefName,baseRefName,headRefOid,mergeStateStatus,reviewDecision --jq '.' --source {branch}")
    # The --source flag returns the PR for the branch when present
    if p.returncode != 0:
        # fallback: try without source
        p2 = run(f"gh pr view --json number,headRefName,baseRefName,headRefOid,mergeStateStatus,reviewDecision")
        if p2.returncode != 0:
            return None
        try:
            return json.loads(p2.stdout)
        except Exception:
            return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def gh_api_get(path: str, token: Optional[str]):
    if requests is None:
        raise RuntimeError("requests not installed; install requirements.txt or install 'requests' manually")
    owner, repo = git_remote_owner_repo()
    if not owner or not repo:
        raise RuntimeError("Could not determine owner/repo from origin url")
    url = f"https://api.github.com/repos/{owner}/{repo}{path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def find_pr_via_api(branch: str, token: Optional[str]):
    # list pulls filtered by head format owner:branch. We need owner from origin
    owner, repo = git_remote_owner_repo()
    if not owner or not repo:
        return None
    q = f"/pulls?state=open&head={owner}:{branch}"
    res = gh_api_get(q, token)
    if isinstance(res, list) and res:
        return res[0]
    return None


def pr_checks_passing(pr_number: int, sha: str, token: Optional[str]) -> Optional[bool]:
    # Check combined status
    try:
        res = gh_api_get(f"/commits/{sha}/status", token)
    except Exception:
        return None
    state = res.get("state")
    if state == "success":
        return True
    if state in ("failure", "error"):
        return False
    return None


def pr_is_approved(pr_number: int, token: Optional[str]) -> Optional[bool]:
    try:
        reviews = gh_api_get(f"/pulls/{pr_number}/reviews", token)
    except Exception:
        return None
    for r in reversed(reviews):
        if r.get("state") == "APPROVED":
            return True
    return False


def check_commit_signatures(base_ref: str, head_ref: str):
    """
    Check GPG signatures for commits in the range `base_ref..head_ref`.

    Returns:
      - None on error (git command failed)
      - Empty list when all commits have valid signatures
      - List of dicts for commits with missing or invalid signatures. Each dict
        contains keys: sha, gstatus, gkey, gsigner, author, email, date, subject
    """
    # Use git's pretty format placeholders for signature info:
    # %G? = signature status (G = good, B = bad, U = untrusted, N = no signature, etc.)
    # %GK = key fingerprint (may be empty)
    # %GS = signer (name/email)
    fmt = "%H%x00%G?%x00%GK%x00%GS%x00%an%x00%ae%x00%ad%x00%s"
    p = run(f"git log --pretty=format:{fmt} {base_ref}..{head_ref}")
    if p.returncode != 0:
        return None
    out = p.stdout
    if not out:
        return []
    lines = out.splitlines()
    bad = []
    for line in lines:
        if not line:
            continue
        parts = line.split("\x00")
        # ensure we have at least 8 parts
        while len(parts) < 8:
            parts.append("")
        sha, gstatus, gkey, gsigner, author, email, date, subject = parts[:8]
        if gstatus == "":
            gstatus = "N"
        if gstatus != "G":
            bad.append({
                "sha": sha,
                "gstatus": gstatus,
                "gkey": gkey,
                "gsigner": gsigner,
                "author": author,
                "email": email,
                "date": date,
                "subject": subject,
            })
    return bad


def main():
    try:
        root = repo_root()
    except Exception as e:
        print("Not a git repository.")
        sys.exit(2)

    print(f"Repo: {root}")
    clean = working_tree_clean()
    print("Working tree:", "clean" if clean else "dirty")

    branch = current_branch()
    print("Current branch:", branch)

    up = upstream_branch()
    if up:
        ahead, behind = ahead_behind("HEAD", up)
        print(f"Tracking branch: {up} (ahead={ahead}, behind={behind})")
    else:
        print("No upstream/tracking branch set.")

    origin_default = origin_default_branch()
    if origin_default:
        # Compare with origin/default
        # fetch to ensure we have refs
        run("git fetch origin --quiet")
        origin_ref = f"origin/{origin_default}"
        a2, b2 = ahead_behind("HEAD", origin_ref)
        print(f"Compared to origin default ({origin_ref}): ahead={a2}, behind={b2}")
        # Check commit signatures for commits introduced on this branch
        sigs = check_commit_signatures(origin_ref, "HEAD")
        if sigs is None:
            print("Could not determine commit signatures (git log failed).")
        elif not sigs:
            print("All commits from origin default to HEAD are signed and valid.")
        else:
            print("Unsigned or invalidly-signed commits between origin default and HEAD:")
            for c in sigs:
                print(f"- {c['sha']} | status={c['gstatus']} | key={c['gkey']} | signer={c['gsigner']}")
                print(f"  {c['author']} <{c['email']}> | {c['date']}")
                print(f"  {c['subject']}")
    else:
        print("Could not determine origin default branch.")

    # PR checks
    gh_pr = None
    pr = None
    token = os.environ.get("GITHUB_TOKEN")
    # Try gh first
    if shutil.which("gh"):
        try:
            p = run(f"gh pr view --json number,headRefName,baseRefName,headRefOid --source {branch}")
            if p.returncode == 0 and p.stdout.strip():
                gh_pr = json.loads(p.stdout)
        except Exception:
            gh_pr = None

    if gh_pr:
        pr_number = gh_pr.get("number")
        head_sha = gh_pr.get("headRefOid")
        print(f"This branch has PR #{pr_number}")
        checks = pr_checks_passing(pr_number, head_sha, token)
        print("PR checks:", "passing" if checks else ("failing" if checks is False else "unknown"))
        approved = pr_is_approved(pr_number, token)
        print("PR approved:", "yes" if approved else ("no" if approved is False else "unknown"))
        # check if out of sync with origin default
        if origin_default:
            base_ref = f"origin/{origin_default}"
            ahead3, behind3 = ahead_behind("HEAD", base_ref)
            needs_update = behind3 > 0
            print("PR needs update from origin default:", "yes" if needs_update else "no")
    else:
        # Try API lookup
        found = find_pr_via_api(branch, token)
        if found:
            pr_number = found.get("number")
            head_sha = found.get("head", {}).get("sha")
            print(f"This branch has PR #{pr_number}")
            checks = pr_checks_passing(pr_number, head_sha, token)
            print("PR checks:", "passing" if checks else ("failing" if checks is False else "unknown"))
            approved = pr_is_approved(pr_number, token)
            print("PR approved:", "yes" if approved else ("no" if approved is False else "unknown"))
            if origin_default:
                base_ref = f"origin/{origin_default}"
                ahead3, behind3 = ahead_behind("HEAD", base_ref)
                needs_update = behind3 > 0
                print("PR needs update from origin default:", "yes" if needs_update else "no")
        else:
            print("No pull request found for this branch.")


if __name__ == "__main__":
    main()
