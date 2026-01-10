#!/usr/bin/env python3
"""
Format completion message for cleanup_completed_heading_branches job.
Reads SUMMARY_JSON from environment variable and outputs formatted message.
"""

import json
import os
import sys


def main():
    summary_json = os.environ.get("SUMMARY_JSON", "")
    if not summary_json:
        print("Error: SUMMARY_JSON environment variable not set", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(summary_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in SUMMARY_JSON: {e}", file=sys.stderr)
        sys.exit(1)

    deleted = data.get("branches-deleted", data.get("branches_deleted", 0))
    print(f"✅ cleanup_completed_heading_branches 完成，删除分支数: {deleted}")


if __name__ == "__main__":
    main()
