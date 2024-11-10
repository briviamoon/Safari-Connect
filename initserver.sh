#!/bin/bash
python3.9 -m uvicorn app.main:app --host 192.168.0.102 --port 8000 --reload
