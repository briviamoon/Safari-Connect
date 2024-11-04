#!/bin/bash
python3 -m uvicorn Backend.captive.CaptivePortalAPI:app --host 192.168.0.102 --port 8000 --reload
