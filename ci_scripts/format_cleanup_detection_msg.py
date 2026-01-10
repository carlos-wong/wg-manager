#!/usr/bin/env python3
"""
Format detection message for cleanup_completed_heading_branches job.
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

    headings = data.get("headings-found", data.get("headings_found", 0))
    deleted = data.get("branches-deleted", data.get("branches_deleted", 0))
    details = data.get("details", [])

    branches = []
    titles = []
    for detail in details:
        branches.extend(detail.get("branches-found", []))
        title = detail.get("title")
        if title:
            titles.append(title)

    branch_preview = ", ".join(branches[:5]) if branches else "无分支匹配"
    title_preview = ", ".join(titles[:3]) if titles else "无标题"

    print(f"🔍 cleanup_completed_heading_branches 检测到标题:{headings} 删除分支:{deleted}")
    print(f"分支: {branch_preview}")
    print(f"标题: {title_preview}")


if __name__ == "__main__":
    main()
