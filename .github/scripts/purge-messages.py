#!/usr/bin/env python3
"""Delete every message this webhook has previously sent.

Reads the id history from .github/reminder-state.json (supports both the
new {"ids": [...]} format and the legacy {"message_id": "..."} format) and
DELETEs each one through the webhook API. Only the webhook URL and the
message IDs are needed - no channel permissions.

A delete counts as done when the API returns 204 (success) or 404
(already gone); anything else keeps the id so a later run can retry.
Survivors are written to $RUNNER_TEMP/survivor-ids.json for the caller to
persist. If the file is missing afterwards, treat the purge as incomplete
and keep the state untouched.
"""

import json
import os
import urllib.error
import urllib.request

STATE_FILE = ".github/reminder-state.json"
TMP = os.environ.get("RUNNER_TEMP", "/tmp")


def main():
    url = os.environ.get("WEBHOOK_URL", "").strip()
    if not url:
        # No webhook URL -> nothing was purged, so no survivors file is
        # written and the caller keeps the state untouched.
        print("purge: no WEBHOOK_URL set, nothing to purge")
        return
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    ids = state.get("ids") or []
    legacy = state.get("message_id")
    if legacy:
        ids = ids + [legacy]
    ids = list(dict.fromkeys(ids))  # dedupe, keep order
    print("purge: reading %s - %d tracked message id(s)" % (STATE_FILE, len(ids)))
    survivors = []
    deleted = 0
    gone = 0
    for mid in ids:
        try:
            req = urllib.request.Request(url + "/messages/" + mid, method="DELETE")
            with urllib.request.urlopen(req, timeout=15):
                pass
            deleted += 1
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                gone += 1  # already gone, counts as cleared
            else:
                survivors.append(mid)
        except Exception:
            survivors.append(mid)
    with open(os.path.join(TMP, "survivor-ids.json"), "w", encoding="utf-8") as f:
        json.dump(survivors, f)
    print("purge: %d deleted, %d already gone, %d failed, %d survivor id(s) kept for retry"
          % (deleted, gone, len(survivors), len(survivors)))


if __name__ == "__main__":
    main()
