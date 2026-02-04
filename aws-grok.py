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

try:
    import boto3
    import botocore.exceptions as boto_exceptions
except ImportError:  # pragma: no cover - runtime environment
    print("Missing dependency: boto3. Install with 'pip install boto3' and try again.")
    sys.exit(2)

AWS_CONFIG = Path(os.path.expanduser("~")) / ".aws" / "config"


def read_aws_config(path: Path) -> Dict[str, Dict[str, str]]:
    cp = configparser.RawConfigParser()
    if not path.exists():
        raise FileNotFoundError(f"AWS config not found at: {path}")
    cp.read(path)
    profiles: Dict[str, Dict[str, str]] = {}
    for section in cp.sections():
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


def profile_is_sso(profile_conf: Dict[str, str]) -> bool:
    return any(k.startswith("sso_") for k in profile_conf.keys())


def verify_profile_with_boto3(profile_name: str, extra_session_kwargs: Optional[Dict] = None) -> bool:
    try:
        session_args = {"profile_name": profile_name}
        if extra_session_kwargs:
            session_args.update(extra_session_kwargs)
        session = boto3.Session(**session_args)
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


def sso_device_flow_login(profile_name: str, profile_conf: Dict[str, str]) -> bool:
    start_url = profile_conf.get("sso_start_url") or profile_conf.get("sso_starturl")
    sso_region = profile_conf.get("sso_region")
    account_id = profile_conf.get("sso_account_id") or profile_conf.get("sso_account")
    role_name = profile_conf.get("sso_role_name") or profile_conf.get("role_name")

    if not (start_url and sso_region and account_id and role_name):
        print("Missing required SSO configuration keys (sso_start_url, sso_region, sso_account_id, sso_role_name).")
        return False

    oidc = boto3.client("sso-oidc", region_name=sso_region)

    try:
        reg = oidc.register_client(clientName="aws-grok", clientType="public")
        client_id = reg["clientId"]
        client_secret = reg["clientSecret"]
    except boto_exceptions.ClientError as e:
        print("Failed to register OIDC client:", e)
        return False

    try:
        dev = oidc.start_device_authorization(clientId=client_id, clientSecret=client_secret, startUrl=start_url)
        verification_uri_complete = dev.get("verificationUriComplete") or dev.get("verificationUri")
        user_code = dev.get("userCode")
        device_code = dev.get("deviceCode")
        interval = dev.get("interval", 5)
        expires_in = dev.get("expiresIn", 600)
    except boto_exceptions.ClientError as e:
        print("Failed to start device authorization:", e)
        return False

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
                    return False
                continue
            elif code in ("SlowDownException",):
                interval = min(interval + 5, 60)
                time.sleep(interval)
                continue
            else:
                print("Error creating token:", e)
                return False

    if not token:
        print("Failed to obtain SSO access token.")
        return False

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
        return False

    # Verify with temporary creds
    extra = {"aws_access_key_id": access_key, "aws_secret_access_key": secret_key, "aws_session_token": session_token}
    print("Obtained temporary role credentials; verifying identity...")
    ok = verify_profile_with_boto3(profile_name, extra_session_kwargs=extra)
    if ok:
        print("SSO login and verification succeeded.")
    return ok


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
        print("Detected SSO profile. Attempting SSO device authorization flow (via boto3)...")
        ok = sso_device_flow_login(selected, conf)
        return 0 if ok else 1
    else:
        print("Profile does not appear to be SSO-configured. Verifying credentials using boto3...")
        ok = verify_profile_with_boto3(selected)
        if ok:
            print("Profile appears valid and working.")
            return 0
        print("Profile is not logged in or credentials are missing. To configure SSO for this profile run:")
        print(f"  aws configure sso --profile {selected}")
        print("Or configure static credentials with 'aws configure --profile <name>'.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
