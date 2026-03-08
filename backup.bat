@echo off
setlocal

:: Konfigurasi
set SRC=C:\Users\MxCel\Documents\BotTradingSaham
set DEST=gdrive:BotSahamBackup
set LOG=%SRC%\backup.log

echo [%date% %time%] Mulai backup... >> %LOG%

:: Backup folder data (database dan file lain) dengan backup-dir
C:\rclone\rclone.exe sync %SRC%\data %DEST%\data --backup-dir %DEST%\data_old --exclude *.tmp --log-file %LOG% --log-level INFO

:: Backup file JSON konfigurasi di folder proyek
C:\rclone\rclone.exe sync %SRC%\*.json %DEST%\config\ --log-file %LOG% --log-level INFO

:: Backup file log
C:\rclone\rclone.exe sync %SRC%\trading_bot.log %DEST%\logs\ --log-file %LOG% --log-level INFO

echo [%date% %time%] Backup selesai. >> %LOG%