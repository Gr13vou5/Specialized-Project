#!/bin/bash

if [[ $# -ne 5 ]]; then
    echo "Usage: $0 HEAP_SIZE STACK_SIZE ENCODE_METHOD INPUT_FILE DECOT"
    exit 1
fi

exec /app/solve.sh "$1" "$2" "$3" "sharpSAT -decot $5 -tmpdir ." "$4"
