# !/bin/bash

# clean up temp files
rm -f output/images/*

# shutdown any running processes
python worker.py shutdown
python app.py shutdown

# start the worker and server
nohup python worker.py work > rq.log 2>&1 &
nohup python app.py > server.log 2>&1 &