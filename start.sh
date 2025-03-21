# !/bin/bash

# clean up temp files
rm -f output/images/*

# shutdown any running processes
python worker.py shutdown
nohup python app.py shutdown >> /dev/null 2>&1 &

# start the worker and server
nohup python worker.py work > rq.log 2>&1 &
nohup python app.py start > server.log 2>&1 &