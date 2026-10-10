#!/usr/bin/env bash
# usage: ./build.sh app|app_opt   -> dist/<dir>.zip  (Linux x86_64 wheels for Lambda py3.12)
set -e
D=$1; rm -rf build/$D && mkdir -p build/$D dist
pip install numpy pandas pillow requests matplotlib --platform manylinux2014_x86_64 --python-version 3.12 \
    --only-binary=:all: --target build/$D -q
cp $D/handler.py build/$D/
(cd build/$D && zip -qr ../../dist/$D.zip . -x "*/__pycache__/*" "*.pyc")
ls -lh dist/$D.zip
