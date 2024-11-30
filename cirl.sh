#!/bin/bash
curl -v -X POST "https://0697-41-209-3-162.ngrok-free.app/payment/mpesa/callback" -H "Content-Type: application/json" -d @callback.json
