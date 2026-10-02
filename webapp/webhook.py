def changed_paths(old_references, new_references):
    """Compare complete snapshots so folder moves include every descendant."""
    return sorted(
        (old["full_path"], new_references[file_id]["full_path"])
        for file_id, old in old_references.items()
        if file_id in new_references
        and old.get("full_path") is not None
        and new_references[file_id].get("full_path") is not None
        and old["full_path"] != new_references[file_id]["full_path"]
    )


def validate_drive_notification(headers, expected_token):
    """Return whether a Drive push notification carries our secret token."""
    if not expected_token or not headers:
        return False
    if headers.get("X-Goog-Resource-State") not in ("sync", "change"):
        return False
    return (headers.get("X-Goog-Channel-Token") == expected_token)
