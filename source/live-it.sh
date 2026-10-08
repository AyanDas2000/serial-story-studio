#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3.14 >/dev/null 2>&1; then
  exec python3.14 run_shelf_live.py --sample --default-cap 1 --open
fi
exec python3 run_shelf_live.py --sample --default-cap 1 --open
