import win32con, win32service, winreg, os, sys
from configparser import ConfigParser

class_hive = 'SYSTEM\CurrentControlSet\Control\Class'
services_hive = 'SYSTEM\CurrentControlSet\Services'
config = ConfigParser(allow_no_value=True, delimiters=('='))
# prevent lists imported as lowercase
config.optionxform = str

def parse_config(section, array_name, config):
    for i in config[section]:
        if i != '' and i not in array_name:
            array_name.append(i)

def append_filter(filter, filtertype, arr_name):
    key_data = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f'{class_hive}\{filter}', 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        key_data = winreg.QueryValueEx(key, filtertype)[0]
        for i in arr_name:
            if i in key_data:
                key_data.remove(i)
    return split_lines(key_data)

def split_lines(arr_name): 
    string = ''
    for i in arr_name:
        string += i
        if i != arr_name[-1]:
            string += '\\0'
    return string

def read_value(path, value_name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            try:
                return winreg.QueryValueEx(key, value_name)[0]
            except FileNotFoundError:
                return None
    except FileNotFoundError:
        return None

def main():
    config.read(sys.argv[1])

    automatic = []
    manual = []
    service_dump = []
    rename_folders_executables = []

    parse_config('Automatic_Services', automatic, config)
    parse_config('Manual_Services', manual, config)
    parse_config('Drivers_To_Disable', service_dump, config)
    parse_config('Toggle_Files_Folders', rename_folders_executables, config)

    statuses = win32service.EnumServicesStatus(win32service.OpenSCManager(None, None, win32con.GENERIC_READ))

    if len(automatic) > 0 or len(manual) > 0:
        for (service_name, desc, status) in statuses:
            if '_' in service_name:
                svc, _, suffix = service_name.rpartition("_")
                service_name = svc
            if service_name not in service_dump:
                service_dump.append(service_name)

    service_dump = sorted(service_dump, key=str.lower)

    scripts = ['build/Services-Disable.bat', 'build/Services-Enable.bat']
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

    DS_lines = []
    ES_lines = []

    DS_lines.append('@echo off')
    ES_lines.append('@echo off')

    for item in rename_folders_executables:
        file_name = os.path.basename(item)
        last_index = item[-1]
        DS_lines.append(f'REN "{item}" "{file_name}{last_index}"')
        ES_lines.append(f'REN "{item}{last_index}" "{file_name}"')

    for filter in filter_dict:
        for filter_type in filter_dict[filter]:
            if read_value(f'{class_hive}\{filter}', filter_type) != None:
                for driver in filter_dict[filter][filter_type]:
                    if driver in service_dump:
                        DS_value = append_filter(filter, filter_type, service_dump)
                        DS_lines.append(f'Reg.exe add "HKLM\{class_hive}\{filter}" /v "{filter_type}" /t REG_MULTI_SZ /d "{DS_value}" /f')
                        ES_value = split_lines(read_value(f'{class_hive}\{filter}', filter_type))
                        ES_lines.append(f'Reg.exe add "HKLM\{class_hive}\{filter}" /v "{filter_type}" /t REG_MULTI_SZ /d "{ES_value}" /f')
                        break

    for item in service_dump:
        if read_value(f'{services_hive}\{item}', 'Start') != None:
            if item in automatic:
                DS_lines.append(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "2" /f')
            elif item in manual:
                DS_lines.append(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "3" /f')
            else:
                DS_lines.append(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "4" /f')
            start_value = str(read_value(f'{services_hive}\{item}', 'Start'))
            ES_lines.append(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "{start_value}" /f')

    DS_lines.append('shutdown /r /f /t 0')
    ES_lines.append('shutdown /r /f /t 0')

    with open('build/Services-Disable.bat', 'a') as DS:
        for line in DS_lines:
            DS.write(f'{line}\n')

    with open('build/Services-Enable.bat', 'a') as ES:
        for line in ES_lines:
            ES.write(f'{line}\n')

if __name__ == '__main__':
    main()