#!/usr/bin/env python3
"""
PC Check Client EXE - packaged with PyInstaller
Collects system info and sends to Discord webhook.
DM link version - sends download link via DM to user.
"""

import os
import sys
import json
import platform
import socket
import getpass
import subprocess
import re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ======================== SYSTEM INFO ========================

def get_mac_address():
    mac = "Unknown"
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["getmac", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    mac = match.group(1).replace('-', ':')
                    break
        else:
            result = subprocess.run(["cat", "/sys/class/net/*/address"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                mac = result.stdout.strip().split('\n')[0]
    except:
        pass
    return mac

def get_cpu_name():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=10
            )
            cpu = result.stdout.strip()
            if cpu:
                return cpu
    except:
        pass
    return "Unknown"

def get_gpu_name():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=10
            )
            gpu = result.stdout.strip()
            if gpu:
                return gpu
    except:
        pass
    return "Unknown"

def get_ram_info():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)"],
                capture_output=True, text=True, timeout=10
            )
            gb = result.stdout.strip()
            if gb:
                return f"{gb} GB"
    except:
        pass
    return "Unknown"

def get_gpu_driver():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_VideoController).DriverVersion"],
                capture_output=True, text=True, timeout=10
            )
            driver = result.stdout.strip()
            if driver:
                return driver
    except:
        pass
    return "Unknown"

def is_virtual_machine():
    vm_indicators = ["vmware", "virtualbox", "hyper-v", "parallels", "qemu", "kvm", "vbox", "xen"]
    try:
        if platform.system() == "Windows":
            for cmd in [
                "(Get-CimInstance Win32_BIOS).SerialNumber",
                "(Get-CimInstance Win32_ComputerSystem).Model",
                "(Get-CimInstance Win32_BaseBoard).Product"
            ]:
                result = subprocess.run(
                    ["powershell", "-Command", cmd],
                    capture_output=True, text=True, timeout=10
                )
                output = result.stdout.lower()
                for ind in vm_indicators:
                    if ind in output:
                        return True, ind
    except:
        pass
    return False, None

def check_suspicious_processes():
    suspicious_names = [
        "cheatengine", "cheat engine", "artmoney", "gamecih",
        "igg", "injector", "vape", "novoline", "freefire",
        "pubg", "valorant", "fortnite", "aimbot", "wallhack",
        "triggerbot", "radar", "exploit", "hack"
    ]
    found = []
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                proc_name = line.split(',')[0].strip('"').lower()
                for sus in suspicious_names:
                    if sus in proc_name:
                        found.append(line.split(',')[0].strip('"'))
                        break
    except:
        pass
    return found

def scan_suspicious_files():
    """Scan PC for suspicious files in common locations."""
    # Only scan for actual hack executables and DLLs, not legitimate software
    suspicious_names = [
        "cheatengine", "cheat engine", "artmoney", "gamecih",
        "vape", "novoline", "igg", "injector",
        "aimbot", "wallhack", "triggerbot", "radar",
        "exploit", "cheat", "hacktool", "trainer"
    ]

    # Only these extensions for actual hacks
    suspicious_extensions = [".exe", ".dll"]

    # Common locations to scan - focus on user-accessible folders
    scan_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), ""),
        os.path.join(os.environ.get("APPDATA", ""), ""),
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), ""),
    ]

    found_files = []
    scanned_count = 0

    print("  Scanning for suspicious files...", flush=True)

    for base_path in scan_paths:
        if not os.path.exists(base_path):
            continue
        try:
            for root, dirs, files in os.walk(base_path):
                # Skip certain system folders
                if any(skip in root.lower() for skip in ["\\microsoft\\", "\\windows\\", "\\python", "\\git", "\\node_modules", "\\.cache"]):
                    continue

                for file in files:
                    scanned_count += 1
                    if scanned_count % 5000 == 0:
                        print(f"  Checked {scanned_count} files...", flush=True)

                    file_lower = file.lower()
                    ext = os.path.splitext(file)[1].lower()

                    # Check if suspicious name AND suspicious extension
                    is_suspicious_name = any(sus in file_lower for sus in suspicious_names)
                    is_suspicious_ext = ext in suspicious_extensions

                    if is_suspicious_name and is_suspicious_ext:
                        full_path = os.path.join(root, file)
                        found_files.append(full_path)

                # Limit scan depth and results
                if len(found_files) > 20 or scanned_count > 100000:
                    break
        except:
            continue

    print(f"  File scan complete. Checked {scanned_count} files.", flush=True)
    return found_files[:20]  # Limit to 20 results

# ======================== CONFIGURATION ========================
# The bot URL - hardcoded for this deployment
BOT_URL = "https://omg-pc-checker.onrender.com/webhook"
# ============================================================

def send_to_bot(data):
    """Send data to the bot's webhook endpoint."""
    try:
        payload = json.dumps(data).encode('utf-8')

        req = Request(
            BOT_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "PCCheck/1.0"}
        )

        with urlopen(req, timeout=15) as response:
            return True, "Sent successfully"

    except HTTPError as e:
        return False, f"HTTP Error: {e.code}"
    except URLError as e:
        return False, f"URL Error: {e.reason}"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ======================== MAIN ========================

def win_input(prompt):
    """Windows console input that works with PyInstaller."""
    try:
        from ctypes import windll, c_wchar_p, get_wstring
        import sys

        # Enable console mode
        kernel32 = windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0x4)  # ENABLE_LINE_INPUT

        print(prompt, end="", flush=True)
        buf = c_wchar_p()
        kernel32.ReadConsoleW(kernel32.GetStdHandle(-10), buf, 256, None, None)
        return buf.value.strip()
    except:
        return input(prompt)

def main():
    # Create console window on Windows
    try:
        from ctypes import windll
        windll.kernel32.AllocConsole()
    except:
        pass

    print("=" * 45, flush=True)
    print("        PC VERIFICATION CHECK", flush=True)
    print("=" * 45, flush=True)
    print(flush=True)

    # Terms agreement
    print("TERMS OF AGREEMENT", flush=True)
    print("-" * 45, flush=True)
    print("By running this tool, you agree to:", flush=True)
    print("  - Your system information being collected", flush=True)
    print("  - Results being reviewed by server staff", flush=True)
    print("  - Being banned if cheating software detected", flush=True)
    print("-" * 45, flush=True)
    print(flush=True)

    agree = win_input("Type AGREE to accept and continue: ").strip().upper()
    print(flush=True)

    if agree != "AGREE":
        print("Agreement not accepted. Exiting.", flush=True)
        import time
        time.sleep(2)
        sys.exit(0)

    # Get Check ID
    print("-" * 45, flush=True)
    CHECK_ID = win_input("Enter Check ID: ").strip()
    print(flush=True)

    if not CHECK_ID:
        print("Check ID is required. Exiting.", flush=True)
        import time
        time.sleep(2)
        sys.exit(1)

    # Get Discord User ID
    USER_ID = win_input("Enter Discord User ID: ").strip()
    print(flush=True)

    if not USER_ID:
        print("Discord User ID is required. Exiting.", flush=True)
        import time
        time.sleep(2)
        sys.exit(1)

    print(f"Check ID: {CHECK_ID}", flush=True)
    print(f"User ID: {USER_ID}", flush=True)
    print(flush=True)
    print("Collecting system information...", flush=True)
    print("-" * 45, flush=True)

    # Collect system info
    data = {
        "check_id": CHECK_ID,
        "user_id": USER_ID,
        "hostname": socket.gethostname(),
        "username": getpass.getuser(),
        "os_version": platform.platform(),
        "cpu": get_cpu_name(),
        "gpu": get_gpu_name(),
        "gpu_driver": get_gpu_driver(),
        "ram": get_ram_info(),
        "mac_address": get_mac_address(),
        "timestamp": datetime.now().isoformat(),
        "suspicious_processes": check_suspicious_processes(),
        "suspicious_files": scan_suspicious_files(),
    }

    is_vm, vm_indicator = is_virtual_machine()
    data["is_vm"] = is_vm
    data["vm_indicator"] = vm_indicator

    # Display info
    print(f"  Hostname: {data['hostname']}", flush=True)
    print(f"  Username: {data['username']}", flush=True)
    print(f"  OS: {platform.system()} {platform.release()}", flush=True)
    print(f"  CPU: {data['cpu'][:50]}...", flush=True)
    print(f"  GPU: {data['gpu'][:50]}...", flush=True)
    print(f"  RAM: {data['ram']}", flush=True)
    print(f"  MAC: {data['mac_address']}", flush=True)
    print(f"  VM Detected: {'YES - ' + vm_indicator if is_vm else 'No'}", flush=True)

    if data['suspicious_processes']:
        print(flush=True)
        print("  WARNING - Suspicious processes found:", flush=True)
        for proc in data['suspicious_processes'][:5]:
            print(f"    - {proc}", flush=True)

    if data['suspicious_files']:
        print(flush=True)
        print("  WARNING - Suspicious files found:", flush=True)
        for f in data['suspicious_files'][:10]:
            print(f"    - {f}", flush=True)

    print(flush=True)
    print("-" * 45, flush=True)
    print("Sending verification to Discord...", flush=True)

    # Send to bot
    success, message = send_to_bot(data)

    print(flush=True)
    if success:
        print("=" * 45, flush=True)
        print("  SUCCESS!", flush=True)
        print("=" * 45, flush=True)
        print(flush=True)
        print("Your verification has been submitted.", flush=True)
        print("Staff will review your check shortly.", flush=True)
        import time
        time.sleep(3)
    else:
        print("=" * 45, flush=True)
        print("  ERROR!", flush=True)
        print("=" * 45, flush=True)
        print(flush=True)
        print(f"Failed to send: {message}", flush=True)
        print("Please check your internet connection and try again.", flush=True)
        import time
        time.sleep(5)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
