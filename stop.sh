#!/bin/bash
# clean up temp files
rm -f output/images/*
# shutdown any running processes
python worker.py shutdown >> /dev/null 2>&1 &
curl -X POST 'http://localhost:9721/shutdown' >> /dev/null 2>&1 &