#!/usr/bin/env python3
import sys

PLUGIN_ROOT = '/Users/ysingh/.claude/plugins/cache/alfred-dev/alfred-dev/0.5.1'
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.continuity import main

if __name__ == "__main__":
    raise SystemExit(main())
