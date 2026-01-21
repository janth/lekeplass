# Git & PR Check Script

This repository includes a small helper script that checks the local git working tree and pull request status.

Files:
- [git_pr_check.py](git_pr_check.py)

Usage:

1. (Optional) Install requirements for GitHub API fallback:

```bash
pip install -r requirements.txt
```

2. Run the script from the repository root:

```bash
python git_pr_check.py
```

Notes:
- The script uses the `gh` CLI if available. When `gh` is not installed, it falls back to the GitHub REST API and requires a `GITHUB_TOKEN` environment variable with repo access.
- Note: the script now lives at the repository root as `git_pr_check.py` (not in `scripts/`).
- The script prints:
  - whether the working tree is clean/dirty
  - tracking branch ahead/behind
  - comparison against `origin` default branch (ahead/behind)
  - if the current branch has a PR: checks passing, approved, needs update from origin default
