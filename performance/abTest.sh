#!/bin/bash 

ab -c 50 -n 10000 -p ./post -T 'application/x-www-form-urlencoded' http://127.0.0.1:9000/forbid
#ab -c 1 -n 1 -p ./post -T 'application/x-www-form-urlencoded' http://127.0.0.1:9000/forbid
