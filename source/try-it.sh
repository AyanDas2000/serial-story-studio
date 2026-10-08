#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3.14 >/dev/null 2>&1; then
  exec python3.14 try_it.py --open
fi
exec python3 try_it.py --open
