# !/bin/bash
nohup python worker.py work > rq.log 2>&1 &
nohup python app.py > server.log 2>&1 &