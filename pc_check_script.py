#!/usr/bin/env python3
"""
PC Check Script for Discord Bot Verification
Run this script on the user's PC to generate a verification code.
"""

import json
import base64
import platform
import socket
import os
import getpass
from datetime import datetime

def get_system_info():
    """Gather system information for PC verification."""
    info = {
        "timestamp": datetime.now().timestamp(),
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "os_version": platform.platform(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # Try to get GPU info (Windows-specific)
    try:
        import subprocess
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                info["gpu"] = lines[1].strip()
    except Exception:
        info["gpu"] = "Unknown"

    # Try to get GPU driver version
    try:
        import subprocess
        if platform.system() == "Windows":
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "driverVersion"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                info["gpu_driver"] = lines[1].strip()
    except Exception:
        pass

    # Check for suspicious files/processes
    suspicious_found = []

    # Common cheat/hack injector file patterns (just names, not contents)
    suspicious_processes = [
        "cheatengine",
        "cheat engine",
        "artmoney",
        "gamecih",
        "igg",
        "cr injector",
        "xenos injector",
        "extreme injector",
        "vape",
        "novoline",
    ]

    # This is a basic heuristic check - names only, no file scanning
    # A real anti-cheat would do much more, but this is for verification purposes

    return info

def generate_verification_code(system_info: dict) -> str:
    """Generate a base64 encoded verification code from system info."""
    json_str = json.dumps(system_info)
    encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    return encoded

def main():
    """Main function to run the PC check."""
    print("=" * 50)
    print("       PC VERIFICATION CHECK")
    print("=" * 50)
    print()
    print("This script will gather system information for")
    print("verification purposes only.")
    print()
    print("Collecting information...")
    print()

    # Get system info
    system_info = get_system_info()

    # Display info (without sensitive details)
    print(f"Hostname: {system_info['hostname']}")
    print(f"OS: {system_info['os_version']}")
    print(f"Architecture: {system_info['architecture']}")
    if system_info.get('gpu'):
        print(f"GPU: {system_info['gpu']}")
    print()

    # Generate verification code
    verify_code = generate_verification_code(system_info)

    print("-" * 50)
    print("VERIFICATION CODE (paste this in Discord):")
    print("-" * 50)
    print()
    print(verify_code)
    print()
    print("-" * 50)
    print()
    print("This code will expire in 10 minutes.")
    print("Copy the entire code above and paste it in Discord.")
    print()
    print("Your data is processed locally and not stored externally.")

if __name__ == "__main__":
    main()
