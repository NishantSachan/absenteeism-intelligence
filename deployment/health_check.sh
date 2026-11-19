#!/usr/bin/env bash
# health_check.sh - ask a running deployment whether it is alive.
#   On the server:     bash deployment/health_check.sh http://127.0.0.1
#   From anywhere:     bash deployment/health_check.sh https://dxxxxxxxx.cloudfront.net/api
URL="${1:-http://127.0.0.1}"
if out=$(curl -fsS --max-time 10 "$URL/health"); then echo "HEALTHY $out ($URL)"; else echo "NOT HEALTHY: $URL/health did not answer"; exit 1; fi
