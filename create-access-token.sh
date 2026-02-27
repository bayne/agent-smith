#!/bin/bash
set -e
HOST=https://southroute.chat
USER=agent-jones
echo "Password:"
read -s PASSWORD
curl -XPOST "${HOST}/_matrix/client/r0/login" -H "Content-Type: application/json" -d '{"type":"m.login.password", "user":"'${USER}'", "password":"'${PASSWORD}'"}' 
