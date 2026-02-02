#!/usr/bin/env python3
"""Extract and print Terraform AWS provider source and version from HCL files.

Usage: terraform-requiredx-version.py <file> [files...]
"""

from pathlib import Path
import sys
from typing import Optional, Tuple

import hcl2


def extract_aws_provider(file_path: Path) -> Optional[Tuple[str, str]]:
    """Return (source, version) for the AWS provider if found, otherwise None.

    The function is defensive about HCL structure and logs parse errors to stderr.
    """
    try:
        with file_path.open("r", encoding="utf-8") as fh:
            data = hcl2.load(fh)
    except Exception as e:
        print(f"# Error parsing file {file_path}: {e}", file=sys.stderr)
        return None

    terraform_blocks = data.get("terraform")
    if not terraform_blocks or not isinstance(terraform_blocks, list):
        return None

    for terraform in terraform_blocks:
        required_providers = terraform.get("required_providers")
        if not required_providers or not isinstance(required_providers, list):
            continue
        for rp in required_providers:
            if not isinstance(rp, dict):
                continue
            aws = rp.get("aws")
            if not isinstance(aws, dict):
                continue
            source = aws.get("source")
            version = aws.get("version")
            if source == "hashicorp/aws" and version:
                return source, version

    return None


def main(argv=None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv:
        print("Usage: terraform-requiredx-version.py <file> [files...]", file=sys.stderr)
        return 2

    exit_code = 0
    for path_str in argv:
        path = Path(path_str)
        if not path.exists():
            print(f"# File not found: {path}", file=sys.stderr)
            exit_code = 1
            continue

        result = extract_aws_provider(path)
        if result:
            source, version = result
            print(f"{path}: {source} {version}")
        else:
            # Keep the original behavior quiet on success but log when nothing matches.
            print(f"# No matching provider in {path}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
