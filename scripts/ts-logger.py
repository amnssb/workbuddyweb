#!/usr/bin/env python3
"""ts-logger.py - Prepend RFC3339 timestamp to each log line for tasklog parsing."""
import sys
from datetime import datetime, timezone

def main():
    try:
        for line in sys.stdin:
            now_iso = datetime.now(timezone.utc).isoformat()
            # Ensure format ends with Z
            if now_iso.endswith('+00:00'):
                now_iso = now_iso[:-6] + 'Z'
            sys.stdout.write(f"{now_iso} {line}")
            sys.stdout.flush()
    except (KeyboardInterrupt, BrokenPipeError):
        pass

if __name__ == '__main__':
    main()
