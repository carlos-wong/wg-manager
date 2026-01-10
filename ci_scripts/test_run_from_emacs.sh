#!/bin/bash
# Test script for Emacs integration
# Loops 10 times, waits 1 second each iteration, outputs timestamp and script path via emacsclient

SCRIPT_PATH="$(realpath "$0")"
SOCKET_NAME="${EMACS_SOCKET:-/tmp/emacs_server/server}"

for i in {1..10}; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    MESSAGE="[Loop $i/10] Timestamp: $TIMESTAMP | Script: $SCRIPT_PATH"

    # Output to terminal
    echo "$MESSAGE"

    # Wait 1 second before next iteration (skip wait on last iteration)
    if [ $i -lt 10 ]; then
        sleep 1
    fi
done

echo "Script completed successfully."
