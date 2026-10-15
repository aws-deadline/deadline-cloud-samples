"""Assert that one clip index has a summary under a dreams directory.

Step 1 runs this after generate_dream.py to check the task wrote its OWN
artifact. Counting summaries is not enough: dreams/ is shared, and peer clips'
summaries arrive as synced inputs, so a count passes even when this task wrote
nothing. Match on the clip_index each summary records instead.

    python3 assert_clip_summary.py <clip-index> <dreams-dir>

Exit 0 when a summary for that index exists, 1 otherwise. Unparsable or
unreadable siblings are skipped rather than failing the check, since another
task may be mid-write.
"""

import glob
import json
import os
import sys


def has_summary(clip_index, dreams_dir):
    for path in sorted(glob.glob(os.path.join(dreams_dir, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                summary = json.load(handle)
        except (ValueError, OSError):
            continue
        if isinstance(summary, dict) and summary.get("clip_index") == clip_index:
            return True
    return False


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        clip_index = int(argv[0])
    except ValueError:
        print("clip index must be an integer, got %r" % argv[0], file=sys.stderr)
        return 2
    dreams_dir = argv[1]
    if has_summary(clip_index, dreams_dir):
        return 0
    print(
        "no summary under %s records clip_index=%d" % (dreams_dir, clip_index),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
