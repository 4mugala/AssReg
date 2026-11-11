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
    ("device_name", r"\s*Product\sName:(?P<device_name>.+)"),
    ("serial_number", r"\s*Serial\sNumber:(?P<serial_number>.+)"),
    ("uuid", r"\s*UUID:(?P<uuid>.+)"),
    ("category", r"Chassis Information\n(?:.*\n)*?\s*Type:\s*(?P<category>.+)"),
]


def get_devices_info_linux(hostonly):
    devices_info = list()

    if LINUX_REQUEST_GUI_AUTH:
        dmidecode_output = subprocess.check_output([
            "pkexec",
            "dmidecode"], text=True)
    else:
        dmidecode_output = subprocess.check_output(["sudo", "dmidecode"], text=True).encode()

    # Computer information
    computer_info = dict()
    for group_name, regex in DMIDECODE_RE:
        match = re.search(regex, dmidecode_output)
        device_property = group_name.upper() if group_name == "uuid" else group_name.replace("_", " ").title()
        computer_info[device_property] = match.group(group_name).strip()
    devices_info.append(computer_info)

    if hostonly:
        return devices_info

    # Monitors information
    for edid_path in sorted(glob.glob("/sys/class/drm/*/edid")):
        if "eDP" in edid_path:
            continue

        with open(edid_path, "rb") as f:
            raw_data = f.read()

        try:
            edid = parse_edid(raw_data)
        except Exception as e:
            continue
        monitor = {
            "Device Name": edid.name,
            "Serial Number": edid.serial,
            "UUID": "",
            "Category": "Monitor"
        }

        if monitor not in devices_info:
            devices_info.append(monitor)

    return devices_info


def get_devices_info_windows(hostonly):
    devices_info = list()
    computer_info = dict()

    def decode_wmi_array(char_array):
        """Converts a WMI uint16 character array into a clean Python string."""
        if not char_array:
            raise ValueError
        # Convert each integer code to a character, filtering out null terminators (0)
        return "".join(chr(char) for char in char_array if char != 0).strip()

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

    # Force connection to the root\wmi namespace instead of default cimv2
    c = wmi.WMI(namespace="root\\wmi")

    # Query the WmiMonitorID class
    for monitor in c.WmiMonitorID():
        try:
            monitor_info = {
                # InstanceName acts as the OS-level unique ID for the monitor instance
                "Device Name": decode_wmi_array(monitor.UserFriendlyName),
                "Serial Number": decode_wmi_array(monitor.SerialNumberID),
                "UUID": monitor.InstanceName,
                "Category": "Monitor"
            }
            devices_info.append(monitor_info)
        except:
            pass

    return devices_info


def get_devices_info(hostonly=False):
    system = platform.system().lower()
    if SYSTEM == "linux":
        return get_devices_info_linux(hostonly)
    elif SYSTEM == "windows":
        return get_devices_info_windows(hostonly)

# print(get_devices_info())
