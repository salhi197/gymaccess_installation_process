@echo off
setlocal EnableDelayedExpansion
title REPERE - System Repair Tool

:: ============================================================
:: SELF-ELEVATE TO ADMIN
:: ============================================================
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: ============================================================
:: CONFIGURATION
:: ============================================================
set MYSQL_USER=root
set MYSQL_PASS=
set MYSQL_HOST=localhost
set MYSQL_PORT=3306

set MYGYM_DB=mygym
set GYM_DB=gym
set ENTRES_DB=mygym

set ETHERNET_NAME=Ethernet
set STATIC_IP=192.168.0.4
set SUBNET_MASK=255.255.255.0
set GATEWAY=192.168.0.1

:: ============================================================
:: FIND MYSQL.EXE
:: ============================================================
set MYSQL_EXE=
for %%P in (
    "C:\xampp\mysql\bin\mysql.exe"
    "C:\wamp64\bin\mysql\mysql8.0.31\bin\mysql.exe"
    "C:\wamp\bin\mysql\mysql5.7.31\bin\mysql.exe"
    "C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysql.exe"
    "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
    "C:\Program Files\MariaDB 10.11\bin\mysql.exe"
) do (
    if exist %%P set MYSQL_EXE=%%P
)
if "!MYSQL_EXE!"=="" (
    where mysql >nul 2>&1
    if !errorLevel! equ 0 (
        for /f "delims=" %%M in ('where mysql') do set MYSQL_EXE=%%M
    )
)

set MYSQL_CMD="!MYSQL_EXE!" -h%MYSQL_HOST% -P%MYSQL_PORT% -u%MYSQL_USER%
if not "%MYSQL_PASS%"=="" set MYSQL_CMD=!MYSQL_CMD! -p%MYSQL_PASS%

:: ============================================================
:: STEP 1 - REPAIR DATABASES
:: ============================================================
set DB_STATUS=OK

if "!MYSQL_EXE!"=="" (
    set DB_STATUS=FAILED_NO_MYSQL
    goto :after_db
)

call :repair_db %MYGYM_DB% membres inscriptions paiements presences
call :repair_db %GYM_DB% equipements maintenance personnel horaires

:after_db

:: ============================================================
:: STEP 2 - SET ETHERNET IP
:: ============================================================
set ETH_STATUS=OK

netsh interface show interface "%ETHERNET_NAME%" >nul 2>&1
if errorLevel 1 (
    set ETH_STATUS=FAILED_NOT_FOUND
    goto :after_eth
)

netsh interface ip set address name="%ETHERNET_NAME%" static %STATIC_IP% %SUBNET_MASK% >nul 2>&1
if errorLevel 1 (
    set ETH_STATUS=FAILED_IP
    goto :after_eth
)

netsh interface ip set address name="%ETHERNET_NAME%" gateway %GATEWAY% >nul 2>&1
if errorLevel 1 (
    set ETH_STATUS=FAILED_GATEWAY
    goto :after_eth
)

netsh interface ip set dns name="%ETHERNET_NAME%" static 8.8.8.8 primary >nul 2>&1

:after_eth

:: ============================================================
:: STEP 3 - RECREATE ENTRES / SORTIES
:: ============================================================
set TBL_STATUS=OK

if "!MYSQL_EXE!"=="" (
    set TBL_STATUS=FAILED_NO_MYSQL
    goto :after_tbl
)

(
echo USE %ENTRES_DB%;
echo DROP TABLE IF EXISTS `entres`;
echo DROP TABLE IF EXISTS `sorties`;
echo CREATE TABLE IF NOT EXISTS `entres` (
echo   `id` int NOT NULL AUTO_INCREMENT,
echo   `matricule` text,
echo   `tripode` int DEFAULT NULL,
echo   `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
echo   `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
echo   `user` int DEFAULT NULL,
echo   `type` text,
echo   `inscription` int DEFAULT NULL,
echo   `nom` text,
echo   `prenom` text,
echo   `membre` int DEFAULT NULL,
echo   `vider` int DEFAULT NULL,
echo   PRIMARY KEY (`id`),
echo   KEY `id` (`id`)
echo ^) ENGINE=MyISAM AUTO_INCREMENT=1693 DEFAULT CHARSET=latin1;
echo CREATE TABLE IF NOT EXISTS `sorties` (
echo   `id` int NOT NULL AUTO_INCREMENT,
echo   `matricule` text,
echo   `tripode` int DEFAULT NULL,
echo   `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
echo   `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
echo   `user` int DEFAULT NULL,
echo   `inscription` int DEFAULT NULL,
echo   `vider` int DEFAULT NULL,
echo   `entrer` int DEFAULT NULL,
echo   PRIMARY KEY (`id`),
echo   KEY `id` (`id`)
echo ^) ENGINE=MyISAM AUTO_INCREMENT=1220 DEFAULT CHARSET=latin1;
) > "%TEMP%\repere_tables.sql"

%MYSQL_CMD% < "%TEMP%\repere_tables.sql" >nul 2>&1
if errorLevel 1 set TBL_STATUS=FAILED
del "%TEMP%\repere_tables.sql" >nul 2>&1

:after_tbl

:: ============================================================
:: STEP 4 - DISABLE PUBLIC FIREWALL
:: ============================================================
set FW_STATUS=OK

netsh advfirewall set publicprofile state off >nul 2>&1
if errorLevel 1 (
    set FW_STATUS=FAILED
    goto :after_fw
)

netsh advfirewall show publicprofile state > "%TEMP%\fw.txt" 2>&1
findstr /C:"OFF" "%TEMP%\fw.txt" >nul
if errorLevel 1 (
    set FW_STATUS=UNCERTAIN
) else (
    set FW_STATUS=OK
)
del "%TEMP%\fw.txt" >nul 2>&1

:after_fw

:: ============================================================
:: BUILD SUMMARY MESSAGE
:: ============================================================
set MSG=REPERE - RESULT%%0A%%0A

if "%DB_STATUS%"=="OK"               set MSG=!MSG!DATABASE :  OK%%0A
if "%DB_STATUS%"=="FAILED_NO_MYSQL"  set MSG=!MSG!DATABASE :  FAILED - MySQL not found%%0A

if "%ETH_STATUS%"=="OK"               set MSG=!MSG!ETHERNET :  OK (IP %STATIC_IP%)%%0A
if "%ETH_STATUS%"=="FAILED_NOT_FOUND" set MSG=!MSG!ETHERNET :  FAILED - adapter "%ETHERNET_NAME%" not found%%0A
if "%ETH_STATUS%"=="FAILED_IP"        set MSG=!MSG!ETHERNET :  FAILED - could not set IP%%0A
if "%ETH_STATUS%"=="FAILED_GATEWAY"   set MSG=!MSG!ETHERNET :  FAILED - could not set gateway%%0A

if "%TBL_STATUS%"=="OK"               set MSG=!MSG!TABLES :    OK (entres / sorties)%%0A
if "%TBL_STATUS%"=="FAILED"           set MSG=!MSG!TABLES :    FAILED%%0A
if "%TBL_STATUS%"=="FAILED_NO_MYSQL"  set MSG=!MSG!TABLES :    FAILED - MySQL not found%%0A

if "%FW_STATUS%"=="OK"         set MSG=!MSG!FIREWALL :  OK (public OFF)%%0A
if "%FW_STATUS%"=="FAILED"     set MSG=!MSG!FIREWALL :  FAILED - could not disable%%0A
if "%FW_STATUS%"=="UNCERTAIN"  set MSG=!MSG!FIREWALL :  UNCERTAIN - check manually%%0A

set MSG=!MSG!%%0A%%0ADone.

:: ============================================================
:: SHOW POPUP
:: ============================================================
mshta "javascript:alert('!MSG!');close();"

exit /b 0

:: ============================================================
:: SUBROUTINE - REPAIR DB
:: ============================================================
:repair_db
set DBNAME=%1
shift

:repair_loop
if "%~1"=="" goto :repair_done
set TBL=%~1
%MYSQL_CMD% -N -B -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='%DBNAME%' AND table_name='%TBL%'" > "%TEMP%\repere_chk.txt" 2>nul
set /p EXISTS=<"%TEMP%\repere_chk.txt"
del "%TEMP%\repere_chk.txt" >nul 2>&1

if "%EXISTS%"=="1" (
    %MYSQL_CMD% -e "USE %DBNAME%; REPAIR TABLE `%TBL%`; ANALYZE TABLE `%TBL%`; OPTIMIZE TABLE `%TBL%`;" >nul 2>&1
    if errorLevel 1 set DB_STATUS=FAILED_TABLE
)
shift
goto :repair_loop

:repair_done
exit /b 0