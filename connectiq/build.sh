#!/usr/bin/env bash
# Build, test, or package the HR Thresholds data field.
#   ./build.sh            debug .prg for edge540 (or DEVICE=...)
#   ./build.sh test       compile unit tests and run them in the simulator
#   ./build.sh package    store-ready .iq for every product in manifest.xml
# Needs CIQ_SDK (Connect IQ SDK root) and CIQ_KEY (developer_key.der).
set -euo pipefail
cd "$(dirname "$0")"
SDK="${CIQ_SDK:?set CIQ_SDK to the Connect IQ SDK directory}"
KEY="${CIQ_KEY:?set CIQ_KEY to your developer_key.der}"
DEVICE="${DEVICE:-edge540}"
mkdir -p bin
case "${1:-build}" in
  build)
    "$SDK/bin/monkeyc" -f monkey.jungle -d "$DEVICE" -y "$KEY" -o "bin/HrThresholds-$DEVICE.prg" -w ;;
  test)
    "$SDK/bin/monkeyc" -f monkey.jungle -d "$DEVICE" -y "$KEY" -o bin/HrThresholds-test.prg --unit-test -w
    "$SDK/bin/monkeydo" bin/HrThresholds-test.prg "$DEVICE" -t ;;
  package)
    "$SDK/bin/monkeyc" -f monkey.jungle -e -r -y "$KEY" -o bin/HrThresholds.iq -w ;;
  *) echo "usage: $0 [build|test|package]" >&2; exit 2 ;;
esac
