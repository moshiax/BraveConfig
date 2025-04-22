@echo off
echo Clearing Brave registry settings...

REG DELETE "HKLM\Software\Policies\BraveSoftware\Brave" /f
REG DELETE "HKCU\Software\Policies\BraveSoftware\Brave" /f

echo Brave registry settings cleared.

set USERDATA_DIR=%USERPROFILE%\AppData\Local\BraveSoftware\Brave-Browser\User Data

if exist "%USERDATA_DIR%\Local State" (
    del /f /q "%USERDATA_DIR%\Local State"
    echo Local State file cleared.
) else (
    echo Local State file not found.
)

if exist "%USERDATA_DIR%\Default\Preferences" (
    del /f /q "%USERDATA_DIR%\Default\Preferences"
    echo Preferences file cleared.
) else (
    echo Preferences file not found.
)

echo Brave data cleared successfully.
pause
