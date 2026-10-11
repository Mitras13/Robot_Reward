@echo off
cd /d %~dp0
rem main.py itself kills any previous instance via main.pid
rem before doing anything else - see _kill_previous_instance() there.
start "" pythonw main.py
