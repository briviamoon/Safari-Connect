#!/bin/bash
CURRENT_IP=$(hostname-I | awk '{print $1}')
sed -i "s]proxy_pass https://.*:8000;|proxy_pass https://$CURRENT_IP:8000;|g" /etc/nginx/sites-available/safariconnect
sustemctl reload nginx

