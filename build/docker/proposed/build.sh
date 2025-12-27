#!/bin/bash

readonly IMAGE_NAME="bsaf"

cd "$(dirname "$0")" || exit

exec docker build -t $IMAGE_NAME .
