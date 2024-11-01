#!/usr/bin/env bash
opkg update
opkg install nodogsplash
opkg install iptables-mod-extra

# setup SSL
opkg install acme
acme.sh --issue -d safariconnect.com -w /Path/to/webroot

# configure Data Base
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres createdb captive_portal
sudo -u postgres createuser admin

#deploying the bacend
# Install dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary africastalking

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8000