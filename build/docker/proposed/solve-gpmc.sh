#!/bin/bash

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 HEAP_SIZE STACK_SIZE ENCODE_METHOD INPUT_FILE"
    exit 1
fi

exec /app/solve.sh "$1" "$2" "$3" gpmc "$4"
