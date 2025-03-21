# !/bin/bash

# Initiate environment
export ADMIN_API_KEY="your_api_key_here"

# clean up temp files
rm -f output/images/*

# shutdown any running processes
python worker.py shutdown
curl -X POST http://localhost:9721/admin/shutdown -H "X-Admin-API-Key: your_api_key_here" >> /dev/null 2>&1 &
sleep 10

# start the worker and server
nohup python worker.py work > rq.log 2>&1 &
nohup python app.py > server.log 2>&1 &