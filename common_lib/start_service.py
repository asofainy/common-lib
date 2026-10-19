#!/usr/bin/env python3
"""Shared startup launcher for microservices."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if candidate.name == '00 - microservices':
            return candidate
        if (candidate / 'wallet-manager' / 'src' / 'main.py').exists():
            return candidate
    return current.parents[3]


def list_services() -> list[str]:
    repo_root = find_repo_root()
    services = []
    for child in sorted(repo_root.iterdir()):
        if child.is_dir() and (child / 'src' / 'main.py').exists():
            services.append(child.name)
    return services


def run_service(service_name: str) -> int:
    repo_root = find_repo_root()
    service_dir = repo_root / service_name
    if not service_dir.exists():
        print(f"Service not found: {service_name}", file=sys.stderr)
        return 1

    main_file = service_dir / 'src' / 'main.py'
    if not main_file.exists():
        print(f"Main entrypoint not found: {main_file}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(main_file)]
    print("$", shlex.join(cmd))
    return subprocess.run(cmd, cwd=str(service_dir)).returncode


if __name__ == '__main__':
    if len(sys.argv) < 2:
        services = list_services()
        if not services:
            print("No microservices found.", file=sys.stderr)
            raise SystemExit(1)

        print("Available services:")
        for service in services:
            print(f"  - {service}")
        print("\nUsage: python -m common_lib.start_service <service-name>")
        raise SystemExit(1)

    if sys.argv[1] in {'-h', '--help', 'help'}:
        services = list_services()
        print("Usage: python -m common_lib.start_service <service-name>")
        print("Available services:")
        for service in services:
            print(f"  - {service}")
        raise SystemExit(0)

    raise SystemExit(run_service(sys.argv[1]))
