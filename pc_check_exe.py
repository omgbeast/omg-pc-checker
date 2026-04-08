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

def get_public_ip():
    try:
        req = Request("https://api.ipify.org", headers={"User-Agent": "PCCheck/1.0"})
        with urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except:
        return "Unable to get"

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
            result = subprocess.run(["wmic", "cpu", "get", "name"],
                capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                return lines[1]
    except:
        pass
    return "Unknown"

def get_gpu_name():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                return lines[1]
    except:
        pass
    return "Unknown"

def get_ram_info():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                bytes_val = int(lines[1])
                gb = bytes_val / (1024**3)
                return f"{gb:.1f} GB"
    except:
        pass
    return "Unknown"

def get_gpu_driver():
    try:
        if platform.system() == "Windows":
            result = subprocess.run(["wmic", "path", "win32_VideoController", "get", "DriverVersion"],
                capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                return lines[1]
    except:
        pass
    return "Unknown"

def is_virtual_machine():
    vm_indicators = ["vmware", "virtualbox", "hyper-v", "parallels", "qemu", "kvm", "vbox", "xen"]
    try:
        if platform.system() == "Windows":
            for cmd in ["wmic bios get serialnumber", "wmic computersystem get model", "wmic baseboard get product"]:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
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

# ======================== SEND TO DISCORD ========================

def send_to_discord(data, webhook_url):
    if not webhook_url or webhook_url == "YOUR_BOT_URL":
        return False, "Bot URL not configured"

    try:
        embed = {
            "title": "PC Verification Check",
            "color": 16776960,
            "fields": [
                {"name": "User", "value": f"<@{data['user_id']}>", "inline": True},
                {"name": "Check ID", "value": data.get('check_id', 'N/A'), "inline": True},
                {"name": "Status", "value": "PENDING - Awaiting Review", "inline": True},
                {"name": "Hostname", "value": data.get('hostname', 'N/A'), "inline": True},
                {"name": "Username", "value": data.get('username', 'N/A'), "inline": True},
                {"name": "OS", "value": data.get('os_version', 'N/A'), "inline": False},
                {"name": "CPU", "value": data.get('cpu', 'N/A'), "inline": False},
                {"name": "GPU", "value": data.get('gpu', 'N/A'), "inline": True},
                {"name": "RAM", "value": data.get('ram', 'N/A'), "inline": True},
                {"name": "MAC Address", "value": data.get('mac_address', 'N/A'), "inline": True},
                {"name": "Public IP", "value": data.get('public_ip', 'N/A'), "inline": True},
                {"name": "GPU Driver", "value": data.get('gpu_driver', 'N/A'), "inline": True},
            ],
            "footer": {"text": f"Check ID: {data.get('check_id', 'N/A')} | Use buttons to Approve/Reject"},
            "timestamp": data.get('timestamp', datetime.now().isoformat())
        }

        if data.get('suspicious_processes'):
            embed["fields"].append({
                "name": "WARNING - Suspicious Processes",
                "value": ", ".join(data['suspicious_processes'][:5]),
                "inline": False
            })
            embed["color"] = 16724787

        if data.get('is_vm'):
            embed["fields"].append({
                "name": "WARNING - Virtual Machine",
                "value": f"VM detected: {data.get('vm_indicator', 'Unknown type')}",
                "inline": False
            })
            embed["color"] = 16750848

        payload = json.dumps({"embeds": [embed]}).encode('utf-8')

        req = Request(
            webhook_url,
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

def main():
    # Create console window on Windows
    try:
        from ctypes import windll
        windll.kernel32.AllocConsole()
    except:
        pass

    print("=" * 45)
    print("        PC VERIFICATION CHECK")
    print("=" * 45)
    print()

    # Parse arguments: CHECK_ID USER_ID WEBHOOK_URL
    args = sys.argv
    if len(args) > 1:
        CHECK_ID = args[1]
    else:
        CHECK_ID = ""
    if len(args) > 2:
        USER_ID = args[2]
    else:
        USER_ID = ""
    if len(args) > 3:
        WEBHOOK_URL = args[3]
    else:
        WEBHOOK_URL = ""

    if len(args) < 3 or not CHECK_ID or not USER_ID:
        print("Usage: PCCheck.exe <CHECK_ID> <USER_ID> [WEBHOOK_URL]")
        print()
        print("This tool should be launched automatically.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    if not WEBHOOK_URL or WEBHOOK_URL == "YOUR_BOT_URL":
        print("ERROR: Bot URL not configured!")
        print("Please contact staff for the correct tool.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"Check ID: {CHECK_ID}")
    print(f"User ID: {USER_ID}")
    print()
    print("Collecting system information...")
    print("-" * 45)

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
        "public_ip": get_public_ip(),
        "timestamp": datetime.now().isoformat(),
        "suspicious_processes": check_suspicious_processes(),
    }

    is_vm, vm_indicator = is_virtual_machine()
    data["is_vm"] = is_vm
    data["vm_indicator"] = vm_indicator

    # Display info
    print(f"  Hostname: {data['hostname']}")
    print(f"  Username: {data['username']}")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  CPU: {data['cpu'][:50]}...")
    print(f"  GPU: {data['gpu'][:50]}...")
    print(f"  RAM: {data['ram']}")
    print(f"  MAC: {data['mac_address']}")
    print(f"  Public IP: {data['public_ip']}")
    print(f"  VM Detected: {'YES - ' + vm_indicator if is_vm else 'No'}")

    if data['suspicious_processes']:
        print()
        print("  WARNING - Suspicious processes found:")
        for proc in data['suspicious_processes'][:5]:
            print(f"    - {proc}")

    print()
    print("-" * 45)
    print("Sending verification to Discord...")

    # Send to Discord
    success, message = send_to_discord(data, WEBHOOK_URL)

    print()
    if success:
        print("=" * 45)
        print("  SUCCESS!")
        print("=" * 45)
        print()
        print("Your verification has been submitted.")
        print("Staff will review your check shortly.")
    else:
        print("=" * 45)
        print("  ERROR!")
        print("=" * 45)
        print()
        print(f"Failed to send: {message}")
        print("Please check your internet connection and try again.")

    input()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
