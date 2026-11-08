@echo off
REM Manual deployment: run the pipeline once on this machine
set SKYROUTE_TRIGGER=manual
python src\pipeline.py --workers 4
