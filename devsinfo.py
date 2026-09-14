import os
import platform
import re
import subprocess
import ctypes
import glob
from pyedid import parse_edid

SYSTEM = platform.system().lower()
if SYSTEM == "windows":
    import wmi

LINUX_REQUEST_GUI_AUTH = True


def is_root() -> bool:
    """Returns True if the current process has root/admin privileges."""
    try:
        # Check for Unix-like systems (Linux, macOS)
        if hasattr(os, 'geteuid'):
            return os.geteuid() == 0

        # Check for Windows
        elif hasattr(ctypes, 'windll'):
            return ctypes.windll.shell32.IsUserAnAdmin() != 0

    except Exception:
        return False


DMIDECODE_RE = [
    ("device_name", r"\s*Product\sName:(.+)"),
    ("serial_number", r"\s*Serial\sNumber:(.+)"),
    ("uuid", r"\s*UUID:(.+)"),
]


def get_devices_info_linux(hostonly):
    devices_info = list()

    if LINUX_REQUEST_GUI_AUTH:
        dmidecode_output = subprocess.check_output([
            "pkexec",
            "dmidecode", "system-serial-number"], text=True)
    else:
        dmidecode_output = subprocess.check_output(["sudo", "dmidecode"], text=True).encode()

    # Computer information
    computer_info = dict()
    for name, regex in DMIDECODE_RE:
        match = re.search(regex, dmidecode_output)
        name = name.upper() if name == "uuid" else name.replace("_", " ").title()
        computer_info[name] = match.group(1).strip()
    computer_info["Category"] = "Computer"
    devices_info.append(computer_info)

    if hostonly:
        return devices_info

    # Monitors information
    for edid_path in sorted(glob.glob("/sys/class/drm/*/edid")):
        print(edid_path)
        if "eDP" in edid_path:
            continue

        with open(edid_path, "rb") as f:
            raw_data = f.read()

        try:
            edid = parse_edid(raw_data)
        except Exception as e:
            continue

        devices_info.append({
            "Device Name": edid.name,
            "Serial Number": edid.serial,
            "UUID": "",
            "Category": "Monitor"
        })

    return devices_info


def get_devices_info_windows(hostonly):
    devices_info = list()
    computer_info = dict()
    try:
        result = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance Win32_ComputerSystem).Model",
             ";", "(Get-CimInstance -ClassName Win32_BIOS).SerialNumber",
             ";", "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
             ],
            text=True
        )

        results = result.strip().split("\n")
        computer_info["Device Name"] = results[0]
        computer_info["Serial Number"] = results[1]
        computer_info["UUID"] = results[2]
        computer_info["Category"] = "Computer"
        devices_info.append(computer_info)
    except:
        pass

    if hostonly:
        return devices_info

    try:
        # Monitor in info
        c = wmi.WMI()
        for monitor in c.Win32_DesktopMonitor():
            if monitor.Name:  # and monitor.SerialNumber:
                devices_info.append({
                    "Device Name": monitor.Name,
                    "Serial Number": "",
                    "UUID": "",
                    "Category": "Monitor"
                })
    except Exception as e:
        # sysinfo["monitors"] = [{"name": "Unknown"}]
        pass

    # try:
    #     # Computer Serial Number
    #     c = wmi.WMI()
    #     for bios in c.Win32_BIOS():
    #         computer_info["serial_number"] = bios.SerialNumber.strip()
    # except:
    #     result = subprocess.check_output(
    #         ["powershell", "-Command", "(Get-CimInstance -ClassName Win32_BIOS).SerialNumber"],
    #         text=True
    #     )
    #     lines = result.strip().split('\n')
    #     if len(lines) > 1:
    #         sysinfo["serial_number"] = lines[1].strip()
    #
    return devices_info


def get_devices_info(hostonly=False):
    system = platform.system().lower()
    if SYSTEM == "linux":
        return get_devices_info_linux(hostonly)
    elif SYSTEM == "windows":
        return get_devices_info_windows(hostonly)

# print(get_devices_info())
