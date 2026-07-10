#!/bin/bash
cp /root/aziza-build/configs/nginx/aziza.conf /etc/nginx/conf.d/aziza.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t && nginx -s reload
echo "NGINX reloaded with Aziza configuration."
