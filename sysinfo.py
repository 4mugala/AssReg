import platform
import re
import subprocess

SYSTEM = platform.system().lower()

if SYSTEM == "windows":
    import wmi

LINUX_REQUEST_GUI_AUTH = True


def get_computer_info_linux():
    sysinfo = dict()
    MATCH_RE = [
        ("computer_name", r"\s*Product\sName:(.+)"),
        ("serial_number", r"\s*Serial\sNumber:(.+)"),
        ("uuid", r"\s*UUID:(.+)"),
    ]
    if LINUX_REQUEST_GUI_AUTH:
        dmidecode_output = subprocess.check_output([
            "pkexec",
            "dmidecode", "system-serial-number"], text=True)  # .encode()
    else:
        dmidecode_output = subprocess.check_output(["sudo", "dmidecode"], text=True).encode()

    # Computer Serial Number
    for name, regex in MATCH_RE:
        match = re.search(regex, dmidecode_output)
        sysinfo[name] = match.group(1).strip()

    # Monitor in info
    monitors = []
    result = subprocess.check_output(["xrandr", "--query"], text=True)
    lines = result.split('\n')
    for line in lines:
        if " connected" in line:
            name = line.split()[0]
            monitors.append({name: "N/A"})

    sysinfo["monitors"] = monitors
    return sysinfo


def get_computer_info_windows():
    sysinfo = dict()
    try:
        result = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance Win32_ComputerSystem).Model",
             ";", "(Get-CimInstance -ClassName Win32_BIOS).SerialNumber",
             ";", "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
             ],
            text=True
        )

        results = result.strip().split("\n")
        sysinfo["computer_name"] = results[0]
        sysinfo["serial_number"] = results[1]
        sysinfo["uuid"] = results[2]
    except:
        pass

    try:
        # Monitor in info
        c = wmi.WMI()
        monitors = []
        for monitor in c.Win32_DesktopMonitor():
            if monitor.Name:  # and monitor.SerialNumber:
                monitors.append({"name": monitor.Name})
        sysinfo["monitors"] = monitors
    except Exception as e:
        sysinfo["monitors"] = [{"name": "Unknown"}]

    try:
        # Computer Serial Number
        c = wmi.WMI()
        for bios in c.Win32_BIOS():
            sysinfo["serial_number"] = bios.SerialNumber.strip()
    except:
        result = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance -ClassName Win32_BIOS).SerialNumber"],
            text=True
        )
        lines = result.strip().split('\n')
        if len(lines) > 1:
            sysinfo["serial_number"] = lines[1].strip()

    return sysinfo


def get_computer_info():
    system = platform.system().lower()
    if SYSTEM == "linux":
        return get_computer_info_linux()
    elif SYSTEM == "windows":
        return get_computer_info_windows()

# print(get_computer_info())
