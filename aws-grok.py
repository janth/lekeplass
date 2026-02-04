#!/usr/bin/env python3
"""aws-grok

Read ~/.aws/config, list profiles with SSO account id and role name, let user pick one and log in using boto3.
"""

from __future__ import annotations

import configparser
import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime, timezone

try:
    import boto3
    import botocore.exceptions as boto_exceptions
except ImportError:  # pragma: no cover - runtime environment
    print("Missing dependency: boto3. Install with 'pip install boto3' and try again.")
    sys.exit(2)

AWS_CONFIG = Path(os.path.expanduser("~")) / ".aws" / "config"


def read_aws_config(path: Path) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """Read AWS config and return (profiles, sso_sessions).

    - profiles: mapping of profile name -> options
    - sso_sessions: mapping of session name -> options (from sections like '[sso-session NAME]')
    """
    cp = configparser.RawConfigParser()
    if not path.exists():
        raise FileNotFoundError(f"AWS config not found at: {path}")
    cp.read(path)
    profiles: Dict[str, Dict[str, str]] = {}
    sso_sessions: Dict[str, Dict[str, str]] = {}
    for section in cp.sections():
        name = section
        if name.startswith("profile "):
            name = name[len("profile "):]
            profiles[name] = {k: v for k, v in cp.items(section)}
        elif name.startswith("sso-session "):
            # section header is 'sso-session NAME'
            sess = name[len("sso-session "):]
            sso_sessions[sess] = {k: v for k, v in cp.items(section)}
        else:
            # keep other sections as profiles (eg 'default')
            profiles[name] = {k: v for k, v in cp.items(section)}
    return profiles, sso_sessions


def resolve_sso_conf(profile_conf: Dict[str, str], sso_sessions: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Return a merged configuration where session keys fill missing profile sso values."""
    out = dict(profile_conf)
    session_name = profile_conf.get("sso_session")
    sess: Dict[str, str] = {}
    if session_name:
        sess = sso_sessions.get(session_name) or {}
        if sess:
            # session values should not override explicit profile values
            for k, v in sess.items():
                out.setdefault(k, v)

    # Preserve/propagate an AWS region if present on profile or session
    # Priority: explicit profile 'region' -> sso-session 'region' -> sso_region
    region = profile_conf.get("region") or sess.get("region") or sess.get("sso_region") or profile_conf.get("sso_region")
    if region:
        out.setdefault("region", region)
    return out


def summarize_profiles(profiles: Dict[str, Dict[str, str]], sso_sessions: Dict[str, Dict[str, str]]) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for name, data in sorted(profiles.items()):
        merged = resolve_sso_conf(data, sso_sessions)
        acct = merged.get("sso_account_id") or merged.get("sso_account") or "-"
        role = merged.get("sso_role_name") or merged.get("role_name") or merged.get("role_arn") or "-"
        out.append((name, acct, role))
    return out


def print_menu(items: List[Tuple[str, str, str]]) -> None:
    print("Available AWS profiles:\n")
    print("  #  Profile                 Account ID       Role")
    print("  -- ----------------------  ---------------  -------------------------------")
    for i, (name, acct, role) in enumerate(items, start=1):
        print(f"  {i:2d} {name:22.22s}  {acct:15.15s}  {role}")
    print()
    print("Enter a number or profile name to select, or 'q' to quit.")


def choose_profile(items: List[Tuple[str, str, str]]) -> Optional[str]:
    name_map = {str(i): name for i, (name, *_ ) in enumerate(items, start=1)}
    name_map.update({name: name for name, *_ in items})
    while True:
        choice = input("Select profile> ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            return None
        if choice in name_map:
            return name_map[choice]
        print("Invalid selection. Try again or type 'q' to quit.")


def profile_is_sso(profile_conf: Dict[str, str]) -> bool:
    # SSO profile may either have 'sso_*' keys or an 'sso_session' reference
    return any(k.startswith("sso_") for k in profile_conf.keys()) or ("sso_session" in profile_conf)


def verify_profile_with_boto3(profile_name: str, extra_session_kwargs: Optional[Dict] = None, region_name: Optional[str] = None) -> bool:
    try:
        if extra_session_kwargs:
            # When given explicit temporary credentials, use them directly
            session_args = dict(extra_session_kwargs)
            # allow region_name override if provided
            if region_name and "region_name" not in session_args:
                session_args["region_name"] = region_name
            session = boto3.Session(**session_args)
        else:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
        sts = session.client("sts")
        ident = sts.get_caller_identity()
        print("Caller identity:")
        print(json.dumps(ident, indent=2, default=str))
        return True
    except boto_exceptions.NoCredentialsError:
        print("No credentials available for profile.")
        return False
    except boto_exceptions.ClientError as e:
        print("AWS ClientError:", e)
        return False
    except Exception as e:  # pragma: no cover - best effort
        print("Unexpected error while verifying profile:", e)
        return False


def sso_device_flow_login(profile_name: str, profile_conf: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Perform SSO device flow and return temporary credentials dict on success, otherwise None."""
    # profile_conf should already be merged with its sso-session.
    start_url = profile_conf.get("sso_start_url") or profile_conf.get("sso_starturl")
    sso_region = profile_conf.get("sso_region")
    account_id = profile_conf.get("sso_account_id") or profile_conf.get("sso_account")
    role_name = profile_conf.get("sso_role_name") or profile_conf.get("role_name")

    if not (start_url and sso_region and account_id and role_name):
        print("Missing required SSO configuration keys (sso_start_url, sso_region, sso_account_id, sso_role_name).")
        return None

    oidc = boto3.client("sso-oidc", region_name=sso_region)

    try:
        reg = oidc.register_client(clientName="aws-grok", clientType="public")
        client_id = reg["clientId"]
        client_secret = reg["clientSecret"]
    except boto_exceptions.ClientError as e:
        print("Failed to register OIDC client:", e)
        return None

    try:
        dev = oidc.start_device_authorization(clientId=client_id, clientSecret=client_secret, startUrl=start_url)
        verification_uri_complete = dev.get("verificationUriComplete") or dev.get("verificationUri")
        user_code = dev.get("userCode")
        device_code = dev.get("deviceCode")
        interval = dev.get("interval", 5)
        expires_in = dev.get("expiresIn", 600)
    except boto_exceptions.ClientError as e:
        print("Failed to start device authorization:", e)
        return None

    print("Open the following URL in your browser and complete the authentication:")
    print(verification_uri_complete)
    if user_code:
        print("Code:", user_code)
    try:
        webbrowser.open(verification_uri_complete)
    except Exception:
        pass

    # Poll for token
    token = None
    start = time.time()
    while True:
        try:
            resp = oidc.create_token(
                clientId=client_id,
                clientSecret=client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=device_code,
            )
            token = resp.get("accessToken")
            break
        except boto_exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("AuthorizationPendingException",):
                time.sleep(interval)
                if time.time() - start > expires_in:
                    print("Device authorization timed out.")
                    return None
                continue
            elif code in ("SlowDownException",):
                interval = min(interval + 5, 60)
                time.sleep(interval)
                continue
            else:
                print("Error creating token:", e)
                return None

    if not token:
        print("Failed to obtain SSO access token.")
        return None

    # Use SSO token to get role credentials
    sso = boto3.client("sso", region_name=sso_region)
    try:
        role_resp = sso.get_role_credentials(accountId=account_id, roleName=role_name, accessToken=token)
        creds = role_resp["roleCredentials"]
        access_key = creds["accessKeyId"]
        secret_key = creds["secretAccessKey"]
        session_token = creds["sessionToken"]
    except boto_exceptions.ClientError as e:
        print("Failed to get role credentials:", e)
        return None

    # Prepare temporary creds dict (include region for subsequent sessions)
    extra = {"aws_access_key_id": access_key, "aws_secret_access_key": secret_key, "aws_session_token": session_token}
    # include region_name so boto3.Session(...) uses correct region
    extra["region_name"] = profile_conf.get("region") or sso_region
    print("Obtained temporary role credentials; verifying identity...")
    ok = verify_profile_with_boto3(profile_name, extra_session_kwargs=extra, region_name=extra.get("region_name"))
    if ok:
        print("SSO login and verification succeeded.")
        return extra
    return None


# --------------------------- CodeCommit helpers ---------------------------
def _iso_to_dt(s: str) -> datetime:
    # AWS commit dates look like '2021-01-01T12:00:00Z' — convert to timezone-aware
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


def _rel_time(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    return f"{weeks}w ago"


def _list_all_files(cc, repo_name: str, commit_spec: str) -> List[str]:
    files: List[str] = []
    # BFS over folders
    queue = ["/"]
    while queue:
        path = queue.pop(0)
        try:
            resp = cc.get_folder(repositoryName=repo_name, commitSpecifier=commit_spec, folderPath=path)
        except cc.exceptions.FolderDoesNotExistException:
            continue
        for f in resp.get("files", []):
            p = f.get("absolutePath") or f.get("relativePath") or ""
            if p.startswith("/"):
                p = p[1:]
            files.append(p)
        for sub in resp.get("subFolders", []):
            sp = sub.get("absolutePath") or sub.get("relativePath") or ""
            queue.append(sp)
    return sorted(files)


def _find_last_commit_for_file(cc, repo_name: str, head_commit: str, file_path: str, cache: Dict[str, dict]) -> Optional[str]:
    # Walk commits from head backwards and find the first commit that changed file_path
    commit_id = head_commit
    checked = 0
    while commit_id and checked < 2000:
        checked += 1
        if commit_id in cache:
            commit = cache[commit_id]
        else:
            commit = cc.get_commit(repositoryName=repo_name, commitId=commit_id)["commit"]
            cache[commit_id] = commit
        parents = commit.get("parents", [])
        if not parents:
            # root commit; assume it introduced the file if present
            return commit_id
        parent = parents[0]
        # check differences between parent and commit
        try:
            diffs = cc.get_differences(repositoryName=repo_name, beforeCommitSpecifier=parent, afterCommitSpecifier=commit_id)
        except Exception:
            # fall back to assuming this commit
            return commit_id
        found = False
        for d in diffs.get("differences", []):
            after = d.get("afterBlob") or {}
            before = d.get("beforeBlob") or {}
            paths = [after.get("path"), before.get("path"), d.get("afterPath"), d.get("beforePath")]
            for p in paths:
                if not p:
                    continue
                p_clean = p[1:] if p.startswith("/") else p
                if p_clean == file_path:
                    found = True
                    break
            if found:
                break
        if found:
            return commit_id
        commit_id = parent
    return None


def _is_commit_ancestor(cc, repo_name: str, ancestor: str, descendant: str, cache: Dict[str, dict]) -> bool:
    # walk parents from descendant to see if we hit ancestor
    to_visit = [descendant]
    visited = set()
    steps = 0
    while to_visit and steps < 5000:
        cur = to_visit.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur == ancestor:
            return True
        if cur in cache:
            parents = cache[cur].get("parents", [])
        else:
            try:
                c = cc.get_commit(repositoryName=repo_name, commitId=cur)["commit"]
            except Exception:
                parents = []
            else:
                cache[cur] = c
                parents = c.get("parents", [])
        to_visit.extend(parents)
        steps += 1
    return False


def codecommit(repo_name: str, branch: Optional[str] = None, max_files: int = 1000, session: Optional[boto3.Session] = None) -> int:
    try:
        if session is None:
            cc = boto3.client("codecommit")
        else:
            cc = session.client("codecommit")
    except boto_exceptions.NoCredentialsError:
        print("No AWS credentials available for CodeCommit. Provide a profile or credentials.")
        return 2
    except boto_exceptions.ClientError as e:
        print("Failed to create CodeCommit client:", e)
        return 2
    except Exception as e:  # pragma: no cover - defensive
        print("Unexpected error creating CodeCommit client:", e)
        return 2
    # Get repository and default branch if needed
    try:
        repo = cc.get_repository(repositoryName=repo_name)["repositoryMetadata"]
    except Exception as e:
        print("Failed to get repository:", e)
        return 2
    default_branch = repo.get("defaultBranch")
    if not branch:
        branch = default_branch or "main"

    try:
        br = cc.get_branch(repositoryName=repo_name, branchName=branch)["branch"]
        head_commit = br.get("commitId")
    except Exception as e:
        print("Failed to determine head commit for branch:", e)
        return 2

    print(f"Repository: {repo_name} (branch: {branch}, head: {head_commit})")

    files = _list_all_files(cc, repo_name, head_commit)
    if not files:
        print("No files found in repository at head commit")
        return 1
    if len(files) > max_files:
        print(f"Repository has {len(files)} files; limiting to first {max_files}")
        files = files[:max_files]

    # Preload pull requests for the repo
    pr_ids = []
    try:
        resp = cc.list_pull_requests(repositoryName=repo_name)
        pr_ids = resp.get("pullRequestIds", [])
    except Exception:
        pr_ids = []

    prs = {}
    for pr_id in pr_ids:
        try:
            p = cc.get_pull_request(pullRequestId=pr_id)["pullRequest"]
            prs[pr_id] = p
        except Exception:
            continue

    commit_cache: Dict[str, dict] = {}

    print("\nFile | commit | author | date (iso) | ago | message | pull_request")
    print("----|--------|--------|-----------|-----|---------|-------------")
    for f in files:
        last = _find_last_commit_for_file(cc, repo_name, head_commit, f, commit_cache)
        if not last:
            cshort = "-"
            author = "-"
            datestr = "-"
            rel = "-"
            msg = "-"
            pr_list = []
        else:
            commit = commit_cache.get(last) or cc.get_commit(repositoryName=repo_name, commitId=last)["commit"]
            commit_cache[last] = commit
            cshort = last[:7]
            author = commit.get("author", {}).get("name") or commit.get("committer", {}).get("name") or "-"
            date_raw = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
            dt = _iso_to_dt(date_raw) if date_raw else datetime.now(timezone.utc)
            datestr = dt.isoformat()
            rel = _rel_time(dt)
            msg = (commit.get("message") or "").splitlines()[0]
            pr_list = []
            # find PRs that include this commit (heuristic: commit is ancestor of sourceCommit)
            for pr_id, pr in prs.items():
                for tgt in pr.get("pullRequestTargets", []):
                    src = tgt.get("sourceCommit")
                    dst = tgt.get("destinationCommit")
                    if not src:
                        continue
                    try:
                        if _is_commit_ancestor(cc, repo_name, last, src, commit_cache):
                            pr_list.append((pr_id, pr.get("title")))
                            break
                    except Exception:
                        continue
        pr_text = "; ".join([f"{pid} ({(title or '')[:40]})" for pid, title in pr_list]) or "-"
        print(f"{f} | {cshort} | {author} | {datestr} | {rel} | {msg} | {pr_text}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="aws-grok", description="Interact with AWS profiles and CodeCommit")
    sub = parser.add_subparsers(dest="cmd")
    prof_parser = sub.add_parser("list-profiles")
    prof_parser.add_argument("--profile", "-p", help="AWS profile to use (will login first if SSO)")
    # cc_parser = sub.add_parser("codecommit")
    # cc_parser.add_argument("repository", help="CodeCommit repository name")
    # cc_parser.add_argument("--branch", help="Branch name (defaults to repo default)")
    # cc_parser.add_argument("--max-files", type=int, default=1000, help="Max number of files to process")

    args, unknown = parser.parse_known_args()

    # if args.cmd == "codecommit":
    #     # If a profile is supplied, attempt to login (SSO if needed) and create a session for CodeCommit
    #     session = None
    #     if getattr(args, "profile", None):
    #         try:
    #             profiles, sso_sessions = read_aws_config(AWS_CONFIG)
    #         except FileNotFoundError as e:
    #             print(e)
    #             return 2
    #         if args.profile not in profiles:
    #             print(f"Profile '{args.profile}' not found in ~/.aws/config")
    #             return 2
    #         conf = profiles.get(args.profile, {})
    #         merged_conf = resolve_sso_conf(conf, sso_sessions)
    #         if profile_is_sso(merged_conf):
    #             print("SSO profile detected; initiating login...")
    #             creds = sso_device_flow_login(args.profile, merged_conf)
    #             if not creds:
    #                 print("SSO login failed or cancelled.")
    #                 return 1
    #             session = boto3.Session(aws_access_key_id=creds.get("aws_access_key_id"), aws_secret_access_key=creds.get("aws_secret_access_key"), aws_session_token=creds.get("aws_session_token"))
    #         else:
    #             # Non-SSO: try to create session from profile (assumes credentials in config/credentials)
    #             session = boto3.Session(profile_name=args.profile)
    #     return codecommit(args.repository, branch=args.branch, max_files=args.max_files, session=session)

    # interactive profile selection (default behavior)
    try:
        profiles, sso_sessions = read_aws_config(AWS_CONFIG)
    except FileNotFoundError as e:
        print(e)
        return 2

    items = summarize_profiles(profiles, sso_sessions)
    if not items:
        print("No profiles found in ~/.aws/config")
        return 1

    print_menu(items)
    selected = choose_profile(items)
    if not selected:
        print("No profile selected, exiting.")
        return 0

    conf = profiles.get(selected, {})
    merged_conf = resolve_sso_conf(conf, sso_sessions)
    print(f"Selected profile: {selected}")

    if profile_is_sso(merged_conf):
        print("Detected SSO profile. Attempting SSO device authorization flow (via boto3)...")
        creds = sso_device_flow_login(selected, merged_conf)
        if not creds:
            return 1
    else:
        print("Profile does not appear to be SSO-configured. Verifying credentials using boto3...")
        ok = verify_profile_with_boto3(selected, region_name=merged_conf.get("region"))
        if ok:
            print("Profile appears valid and working.")
            return 0
        print("Profile is not logged in or credentials are missing. To configure SSO for this profile run:")
        print(f"  aws configure sso --profile {selected}")
        print("Or configure static credentials with 'aws configure --profile <name>'.")
        return 1

    print("Done login process; temporary session acquired.")
    # create a boto3 Session using temporary credentials and configured region (if present)
    session = boto3.Session(
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        aws_session_token=creds.get("aws_session_token"),
        region_name=merged_conf.get("region"),
    )

    print("Now doing CodeCommit operation using the authenticated session...")
    codecommit("aws-accelerator-config", branch="main", max_files=1000, session=session)
    return 0

if __name__ == "__main__":
    sys.exit(main())
