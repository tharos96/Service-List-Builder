from __future__ import annotations
import winreg
import os
import sys
from configparser import ConfigParser
import win32con
import win32service

CLASS_HIVE = "SYSTEM\\CurrentControlSet\\Control\\Class"
SERVICES_HIVE = "SYSTEM\\CurrentControlSet\\Services"


def parse_config(section: str, array_name: list, cfg: ConfigParser) -> None:
    """Parses the configuration file for this program"""
    for i in cfg[section]:
        if i != "" and i not in array_name:
            array_name.append(i)


def append_filter(filter_name: str, filter_type: str, arr_name: list) -> str:
    """Prepares a list in the REG_MULTI_SZ format"""
    key_data = []
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        f"{CLASS_HIVE}\\{filter_name}",
        0,
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
    ) as key:
        key_data = winreg.QueryValueEx(key, filter_type)[0]
        for i in arr_name:
            if i in key_data:
                key_data.remove(i)
    return split_lines(key_data)


def split_lines(arr_name: list) -> str:
    """Prepares a list in the REG_MULTI_SZ format"""
    string = ""
    for i in arr_name:
        string += i
        if i != arr_name[-1]:
            string += "\\0"
    return string


def read_value(path: str, value_name: str) -> list | None:
    """Read keys in Windows Registry"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) as key:
            try:
                return winreg.QueryValueEx(key, value_name)[0]
            except FileNotFoundError:
                return None
    except FileNotFoundError:
        return None


def print_usage() -> None:
    """Prints program usage message"""
    print("usage: service-list-builder.exe [OPTIONS] file\n")
    print("\t-h\tshow this help message and exit")
    print("\tfile\tpass lists.ini configuration file to program")


def main() -> int:
    """CLI Entrypoint"""
    argc = len(sys.argv)
    argv = sys.argv

    # change directory to location of program
    program_path = ""
    if getattr(sys, 'frozen', False):
        program_path = os.path.dirname(sys.executable)
    elif __file__:
        program_path = os.path.dirname(__file__)
    os.chdir(program_path)

    if argc != 2 or "-h" in argv:
        print_usage()
        return 0

    config = ConfigParser(allow_no_value=True, delimiters=("="))
    # prevent lists imported as lowercase
    config.optionxform = str  # type: ignore
    config.read(sys.argv[1])

    automatic = []
    manual = []
    service_dump = []
    rename_folders_executables = []

    parse_config("Automatic_Services", automatic, config)
    parse_config("Manual_Services", manual, config)
    parse_config("Drivers_To_Disable", service_dump, config)
    parse_config("Toggle_Files_Folders", rename_folders_executables, config)

    statuses = win32service.EnumServicesStatus(
        win32service.OpenSCManager(None, None, win32con.GENERIC_READ)  # type: ignore
    )

    if len(automatic) > 0 or len(manual) > 0:
        for (service_name, _desc, _status) in statuses:
            if "_" in service_name:
                svc, _, _suffix = service_name.rpartition("_")
                service_name = svc
            if service_name not in service_dump:
                service_dump.append(service_name)

    service_dump = sorted(service_dump, key=str.lower)

    scripts = ["build/Services-Disable.bat", "build/Services-Enable.bat"]
    for script in scripts:
        if os.path.exists(script):
            os.remove(script)

    filter_dict = {
        '{4d36e967-e325-11ce-bfc1-08002be10318}': {
            'LowerFilters': ['EhStorClass']
        },
        '{71a27cdd-812a-11d0-bec7-08002be2092f}': {
            'LowerFilters': ['fvevol', 'iorate', 'rdyboost'],
            'UpperFilters': ['volsnap']
        },
        '{4d36e96c-e325-11ce-bfc1-08002be10318}': {
            'UpperFilters': ['ksthunk']
        },
        '{6bdd1fc6-810f-11d0-bec7-08002be2092f}': {
            'UpperFilters': ['ksthunk']
        },
        '{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}': {
            'UpperFilters': ['ksthunk']
        }
    }

    ds_lines = []
    es_lines = []

    ds_lines.append("@echo off")
    es_lines.append("@echo off")

    for item in rename_folders_executables:
        file_name = os.path.basename(item)
        last_index = item[-1]
        ds_lines.append(f"REN '{item}'' '{file_name}{last_index}'")
        es_lines.append(f"REN '{item}{last_index}' '{file_name}'")

    for filter_name in filter_dict:
        for filter_type in filter_dict[filter_name]:
            if read_value(f"{CLASS_HIVE}\\{filter_name}", filter_type) is not None:
                for driver in filter_dict[filter_name][filter_type]:
                    if driver in service_dump:
                        ds_value = append_filter(filter_name, filter_type, service_dump)
                        ds_lines.append(
                            f'Reg.exe add "HKLM\\{CLASS_HIVE}\\{filter_name}" /v "{filter_type}" /t REG_MULTI_SZ /d "{ds_value}" /f'
                        )
                        es_value = split_lines(read_value(f"{CLASS_HIVE}\\{filter_name}", filter_type))  # type: ignore
                        es_lines.append(
                            f'Reg.exe add "HKLM\\{CLASS_HIVE}\\{filter_name}" /v "{filter_type}" /t REG_MULTI_SZ /d "{es_value}" /f'
                        )
                        break

    ds_start_value = 0
    for item in service_dump:
        if read_value(f"{SERVICES_HIVE}\\{item}", "Start") is not None:
            if item in automatic:
                ds_start_value = 2
            elif item in manual:
                ds_start_value = 3
            else:
                ds_start_value = 4
            ds_lines.append(f'Reg.exe add "HKLM\\{SERVICES_HIVE}\\{item}" /v "Start" /t REG_DWORD /d "{ds_start_value}" /f')

            es_start_value = str(read_value(f"{SERVICES_HIVE}\\{item}", "Start"))
            es_lines.append(f'Reg.exe add "HKLM\\{SERVICES_HIVE}\\{item}" /v "Start" /t REG_DWORD /d "{es_start_value}" /f')

    ds_lines.append("shutdown /r /f /t 0")
    es_lines.append("shutdown /r /f /t 0")

    with open("build/Services-Disable.bat", "a", encoding="UTF-8") as disable_script:
        for line in ds_lines:
            disable_script.write(f"{line}\n")

    with open("build/Services-Enable.bat", "a", encoding="UTF-8") as enable_script:
        for line in es_lines:
            enable_script.write(f"{line}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
