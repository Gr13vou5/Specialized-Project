#!/bin/bash

if [[ $# -ne 5 ]]; then
    echo "Usage: $0 HEAP_SIZE STACK_SIZE ENCODE_METHOD INPUT_FILE THRESHOLD"
    exit 1
fi

exec /app/solve.sh "$1" "$2" "$3" "d4 -m anyTimeCounter -t $5 -i" "$4"
