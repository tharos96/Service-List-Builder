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

def key_exists(path, value_name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            try:
                winreg.QueryValueEx(key, value_name)[0]
                return True
            except FileNotFoundError:
                return False
    except FileNotFoundError:
        return False

def read_value(path, value_name):
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        return winreg.QueryValueEx(key, value_name)[0]

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

with open('build/Services-Disable.bat', 'a') as disable_script:
    with open('build/Services-Enable.bat', 'a') as enable_script:
        disable_script.write('@echo off\necho please wait...\n')
        enable_script.write('@echo off\necho please wait...\n')
        for a in rename_folders_executables:
            disable_script.write('REN "' + a + '" "' + os.path.basename(a) + '_old" > NUL 2>&1\n')
            enable_script.write('REN "' + a + '_old" "' + os.path.basename(a) + '" > NUL 2>&1\n')
        for b in service_dump:
            if key_exists('SYSTEM\CurrentControlSet\Services\\' + b, 'Start') == True:
                if b in automatic:
                    disable_script.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "2" /f > NUL 2>&1\n')
                elif b in manual:
                    disable_script.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "3" /f > NUL 2>&1\n')
                else:
                    disable_script.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "4" /f > NUL 2>&1\n')
                start_value = str(read_value('SYSTEM\CurrentControlSet\Services\\' + b, 'Start'))
                enable_script.write('Reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\\' + b + '" /v "Start" /t REG_DWORD /d "' + start_value + '" /f\ > NUL 2>&1\n')
        disable_script.write('shutdown /r /f /t 0\n')
        enable_script.write('shutdown /r /f /t 0\n')