import win32con, win32service, winreg, os
from configparser import ConfigParser

def parse_config(section, array_name):
    config = ConfigParser(allow_no_value=True, delimiters=('='))
    # prevent lists imported as lowercase
    config.optionxform = str
    config.read('lists.ini')
    for i in config[section]:
        if i != '' and i not in array_name:
            array_name.append(i)

def append_filter(filter, lowerupper, arr_name):
    key_data = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SYSTEM\CurrentControlSet\Control\Class\\' + filter, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        key_data = winreg.QueryValueEx(key, lowerupper)[0]
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
                return 'Not exists'
    except FileNotFoundError:
        return 'Not exists'

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
    if "_" in service_name and len(service_name) > 6 and service_name[-6] == '_':
        service_name = service_name[:-6]
    if service_name not in service_dump:
        service_dump.append(service_name)

service_dump = sorted(service_dump, key=str.lower)

scripts = ['build/Services-Disable.bat', 'build/Services-Enable.bat']
for script in scripts:
    if os.path.exists(script):
        os.remove(script)

filter_data = {
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

with open('build/Services-Disable.bat', 'a') as DS:
    with open('build/Services-Enable.bat', 'a') as ES:
        DS.write('@echo off\n')
        ES.write('@echo off\n')
        for item in rename_folders_executables:
            DS.write('REN "' + item + '" "' + os.path.basename(item) + '_old" > NUL 2>&1\n')
            ES.write('REN "' + item + '_old" "' + os.path.basename(item) + '" > NUL 2>&1\n')
        for a in filter_data:
            for b in filter_data[a]:
                for c in filter_data[a][b]:
                    if c in service_dump:
                        DS_value = append_filter(a, b, service_dump)
                        DS.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Control\Class\\' + a + '" /v "' + b + '" /t REG_MULTI_SZ /d "' + DS_value + '" /f > NUL 2>&1\n')
                        ES_value = split_lines(read_value('SYSTEM\CurrentControlSet\Control\Class\\' + a, b))
                        ES.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Control\Class\\' + a + '" /v "' + b + '" /t REG_MULTI_SZ /d "' + ES_value + '" /f > NUL 2>&1\n')
                        break
        for b in service_dump:
            if read_value('SYSTEM\CurrentControlSet\Services\\' + b, 'Start') != 'Not exists':
                if b in automatic:
                    DS.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "2" /f > NUL 2>&1\n')
                elif b in manual:
                    DS.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "3" /f > NUL 2>&1\n')
                else:
                    DS.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "4" /f > NUL 2>&1\n')
                start_value = str(read_value('SYSTEM\CurrentControlSet\Services\\' + b, 'Start'))
                ES.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "' + start_value + '" /f > NUL 2>&1\n')
        DS.write('shutdown /r /f /t 0\n')
        ES.write('shutdown /r /f /t 0\n')