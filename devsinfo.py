import platform
import re
import subprocess

SYSTEM = platform.system().lower()

if SYSTEM == "windows":
    import wmi

LINUX_REQUEST_GUI_AUTH = True


def get_devices_info_linux(hostonly):
    devices_info = list()
    MATCH_RE = [
        ("device_name", r"\s*Product\sName:(.+)"),
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
    computer_info = dict()
    for name, regex in MATCH_RE:
        match = re.search(regex, dmidecode_output)
        name = name.upper() if name == "uuid" else name.replace("_", " ").title()
        computer_info[name] = match.group(1).strip()
    computer_info["Category"] = "Computer"
    devices_info.append(computer_info)

    # if hostonly:
    #     return devices_info
    # devices_info.curr_device = computer_info

    # Monitor in info
    result = subprocess.check_output(["xrandr", "--query"], text=True)
    # print("MONITORS:", result)
    lines = result.split('\n')
    for line in lines:
        if " connected" in line:
            name = line.split()[0]
            devices_info.append({
                "Device Name": name,
                "Serial Number": "",
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
