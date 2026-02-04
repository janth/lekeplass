#!/usr/bin/env python3
"""aws-grok

Read ~/.aws/config, list profiles with SSO account id and role name, let user pick one and log in.
"""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

AWS_CONFIG = Path(os.path.expanduser("~")) / ".aws" / "config"


def read_aws_config(path: Path) -> Dict[str, Dict[str, str]]:
    cp = configparser.RawConfigParser()
    if not path.exists():
        raise FileNotFoundError(f"AWS config not found at: {path}")
    cp.read(path)
    profiles: Dict[str, Dict[str, str]] = {}
    for section in cp.sections():
        # Sections are usually like '[profile NAME]' or '[default]'
        name = section
        if name.startswith("profile "):
            name = name[len("profile "):]
        profiles[name] = {k: v for k, v in cp.items(section)}
    return profiles


def summarize_profiles(profiles: Dict[str, Dict[str, str]]) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for name, data in sorted(profiles.items()):
        acct = data.get("sso_account_id") or data.get("sso_account") or "-"
        role = data.get("sso_role_name") or data.get("role_name") or data.get("role_arn", "-")
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


def run_aws_command(args: List[str]) -> int:
    try:
        p = subprocess.run(args, check=False)
        return p.returncode
    except FileNotFoundError:
        print("ERROR: 'aws' command not found. Please install AWS CLI v2 and ensure it's on PATH.")
        return 127


def profile_is_sso(profile_conf: Dict[str, str]) -> bool:
    return any(k.startswith("sso_") for k in profile_conf.keys())


def main() -> int:
    try:
        profiles = read_aws_config(AWS_CONFIG)
    except FileNotFoundError as e:
        print(e)
        return 2

    items = summarize_profiles(profiles)
    if not items:
        print("No profiles found in ~/.aws/config")
        return 1

    print_menu(items)
    selected = choose_profile(items)
    if not selected:
        print("No profile selected, exiting.")
        return 0

    conf = profiles.get(selected, {})
    print(f"Selected profile: {selected}")

    if profile_is_sso(conf):
        print("Detected SSO profile. Attempting 'aws sso login'...")
        rc = run_aws_command(["aws", "sso", "login", "--profile", selected])
        if rc != 0:
            print("aws sso login failed (exit code {}).".format(rc))
            return rc
        print("Login succeeded. Verifying with 'aws sts get-caller-identity'...")
        rc2 = run_aws_command(["aws", "sts", "get-caller-identity", "--profile", selected])
        if rc2 != 0:
            print("Warning: Could not verify identity (exit code {}).".format(rc2))
            return rc2
        return 0
    else:
        print("Profile does not appear to be SSO-configured.")
        print("You can still try to use it if credentials are already configured.")
        print("Attempting to call 'aws sts get-caller-identity' with that profile...")
        rc = run_aws_command(["aws", "sts", "get-caller-identity", "--profile", selected])
        if rc == 0:
            print("Profile appears valid and working.")
            return 0
        print("Profile is not logged in or credentials are missing. To configure SSO for this profile run:")
        print(f"  aws configure sso --profile {selected}")
        print("Or configure static credentials with 'aws configure --profile <name>'.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
