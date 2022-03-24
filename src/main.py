import win32con, win32service, winreg, os, sys
from configparser import ConfigParser

class_hive = 'SYSTEM\CurrentControlSet\Control\Class'
services_hive = 'SYSTEM\CurrentControlSet\Services'

def parse_config(section, array_name):
    config = ConfigParser(allow_no_value=True, delimiters=('='))
    # prevent lists imported as lowercase
    config.optionxform = str
    config.read(sys.argv[1])
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
    automatic = []
    manual = []
    service_dump = []
    rename_folders_executables = []

    parse_config('Automatic_Services', automatic)
    parse_config('Manual_Services', manual)
    parse_config('Drivers_To_Disable', service_dump)
    parse_config('Toggle_Files_Folders', rename_folders_executables)

    statuses = win32service.EnumServicesStatus(win32service.OpenSCManager(None, None, win32con.GENERIC_READ))

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

    DS = open('build/Services-Disable.bat', 'a')
    ES = open('build/Services-Enable.bat', 'a')

    DS.write('@echo off\n')
    ES.write('@echo off\n')

    for item in rename_folders_executables:
        file_name = os.path.basename(item)
        last_index = item[-1]
        DS.write(f'REN "{item}" "{file_name}{last_index}"\n')
        ES.write(f'REN "{item}{last_index}" "{file_name}"\n')

    for filter in filter_dict:
        for filtertype in filter_dict[filter]:
            if read_value(f'{class_hive}\{filter}', filtertype) != None:
                for driver in filter_dict[filter][filtertype]:
                    if driver in service_dump:
                        DS_value = append_filter(filter, filtertype, service_dump)
                        DS.write(f'Reg.exe add "HKLM\{class_hive}\{filter}" /v "{filtertype}" /t REG_MULTI_SZ /d "{DS_value}" /f\n')
                        ES_value = split_lines(read_value(f'{class_hive}\{filter}', filtertype))
                        ES.write(f'Reg.exe add "HKLM\{class_hive}\{filter}" /v "{filtertype}" /t REG_MULTI_SZ /d "{ES_value}" /f\n')
                        break

    for item in service_dump:
        if read_value(f'{services_hive}\{item}', 'Start') != None:
            if item in automatic:
                DS.write(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "2" /f\n')
            elif item in manual:
                DS.write(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "3" /f\n')
            else:
                DS.write(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "4" /f\n')
            start_value = str(read_value(f'{services_hive}\{item}', 'Start'))
            ES.write(f'Reg.exe add "HKLM\{services_hive}\{item}" /v "Start" /t REG_DWORD /d "{start_value}" /f\n')

    DS.write('shutdown /r /f /t 0\n')
    ES.write('shutdown /r /f /t 0\n')

    DS.close()
    ES.close()

if __name__ == '__main__':
    main()