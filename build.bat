@echo off

:: Requirements
::
:: - Python 3.8.6 preferred
:: - 7-Zip

set "path_err=0"
for %%i in (
    "python.exe",
    "pip.exe",
    "7z.exe"
) do (
    where %%i > NUL
    if not %errorlevel% == 0 (
        set "path_err=1"
        echo error: %%i not found in path
    )
)
if not %path_err% == 0 exit /b

set "CURRENT_DIR=%~dp0"
set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

set "BUILD_ENV=%CURRENT_DIR%\BUILD_ENV"
set "PROJECT_DIR=%BUILD_ENV%\main"
set "PUBLISH_DIR=%BUILD_ENV%\Service-List-Builder"

if exist "%BUILD_ENV%" (
    rd /s /q "%BUILD_ENV%"
)
mkdir "%BUILD_ENV%"
mkdir "%PROJECT_DIR%"

python -m venv "%BUILD_ENV%"
call "%BUILD_ENV%\Scripts\activate.bat"

pip install -r requirements.txt

copy /y "%CURRENT_DIR%\src\service-list-builder.py" "%PROJECT_DIR%"
cd "%PROJECT_DIR%"

pyinstaller "service-list-builder.py" --onefile --uac-admin

call "%BUILD_ENV%\Scripts\deactivate.bat"

cd "%CURRENT_DIR%"

xcopy /s /i /e "%CURRENT_DIR%\src" "%PUBLISH_DIR%"
del /f /q "%PUBLISH_DIR%\service-list-builder.py"
move "%PROJECT_DIR%\dist\service-list-builder.exe" "%PUBLISH_DIR%"

if exist "Service-List-Builder.zip" (
    del /f /q "Service-List-Builder.zip"
)
7z a -tzip "Service-List-Builder.zip" "%PUBLISH_DIR%"

rd /s /q "%BUILD_ENV%"

exit /b
