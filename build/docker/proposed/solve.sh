#!/bin/bash

if [[ $# -ne 5 ]]; then
    echo "Usage: $0 HEAP_SIZE STACK_SIZE ENCODE_METHOD SOLVER INPUT_FILE"
    exit 1
fi

INPUT_FILE=$(realpath "$5")
readonly INPUT_FILE

readonly JAR_FILE="/app/bsaf.jar"

unset cmd_pid tmp_dir cnf_tmp

kill_proc() {
    if [[ -n "${cmd_pid-}" ]]; then
        kill -s TERM "$cmd_pid"
    fi
}

rm_tmp() {
    if [[ -n ${cnf_tmp-} ]]; then
        rm -f "$cnf_tmp"
    fi

    if [[ -n ${tmp_dir-} ]]; then
        rm -rf "$tmp_dir"
    fi
}

trap 'kill_proc; exit' INT TERM
trap rm_tmp EXIT

input_file_arg="--sbml"
if [[ $INPUT_FILE == *.bnet ]]; then
    input_file_arg="--bnet"
fi

tmp_dir=$(mktemp -d)
cd "$tmp_dir" || exit
cnf_tmp=$(mktemp --suffix .cnf)

echo "# ENCODE START"
set -x
java -Xms"$1" -Xmx"$1" -Xss"$2" -jar $JAR_FILE \
    $input_file_arg "$INPUT_FILE" --cnf "$cnf_tmp" -"$3" &
cmd_pid="$!"
wait "$cmd_pid"
exit_status=$?
set +x
echo "# ENCODE END"
echo

if [[ $exit_status -eq 0 ]]; then
    if [[ $4 == sharpSAT* ]]; then
        echo "# Copying flow_cutter_pace17 for sharpSAT"
        cp -v /usr/local/bin/flow_cutter_pace17 .
    elif [[ $4 == bdd_minisat_all* ]]; then
        echo "# Using CaDiCaL to detect UNSAT"
        cadical -c 10000 "$cnf_tmp" &
        cmd_pid="$!"
        wait "$cmd_pid"
        exit_status=$?
        echo

        if [[ $exit_status -eq 20 ]]; then
            echo "# UNSAT detected"
            exit
        fi
    fi

    echo "# SAT SOLVE START"
    set -x
    $4 "$cnf_tmp" &
    cmd_pid="$!"
    wait "$cmd_pid"
    set +x
    echo "# SAT SOLVE END"
    echo
fi
