import unittest
from unittest.mock import Mock, patch

from webapp.googledrive import GoogleDrive, TARGET_DRIVE
from webapp.webhook import changed_paths, validate_drive_notification


def nav(paths):
    return Mock(
        doc_reference_dict={
            file_id: {"full_path": path} for file_id, path in paths.items()
        }
    )


class TestProcessChanges(unittest.TestCase):
    def test_folder_move_redirects_every_descendant(self):
        from webapp import app as module

        old = nav({"folder": "/a", "child": "/a/doc", "same": "/c"})
        new = nav({"folder": "/b", "child": "/b/doc", "same": "/c"})
        with patch.object(
            module, "construct_navigation_data", return_value=new
        ), patch.object(module, "GoggleSheet") as sheet, patch.object(
            module, "cache"
        ) as cache:
            result = module.process_changes([{"fileId": "folder"}], old, None)
        self.assertIs(result, new)
        sheet.assert_any_call("a", "b")
        sheet.assert_any_call("a/doc", "b/doc")
        self.assertEqual(sheet.call_count, 2)
        cache.delete_many.assert_any_call("view//a", "view//b")
        cache.delete_many.assert_any_call("view//a/doc", "view//b/doc")

    def test_changed_paths_ignores_added_and_removed_files(self):
        old = {"kept": {"full_path": "/x"}, "gone": {"full_path": "/gone"}}
        new = {"kept": {"full_path": "/y"}, "added": {"full_path": "/new"}}
        self.assertEqual(changed_paths(old, new), [("/x", "/y")])


class TestWebhookRoute(unittest.TestCase):
    def setUp(self):
        from webapp import app as module

        self.module = module
        self.client = module.app.test_client()
        self.headers = {
            "X-Goog-Channel-Token": "secret",
            "X-Goog-Resource-State": "change",
        }
        self.scheduler = Mock()
        patches = [
            patch.dict(
                module.os.environ, {"GOOGLE_DRIVE_WEBHOOK_TOKEN": "secret"}
            ),
            patch.object(module, "scheduler", self.scheduler),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def post(self):
        return self.client.post("/webhook/watch-changes", headers=self.headers)

    def test_change_schedules_get_changes(self):
        self.assertEqual(self.post().status_code, 200)
        self.scheduler.add_job.assert_called_once()
        args, kwargs = self.scheduler.add_job.call_args
        self.assertIs(args[0], self.module.run_scheduled_get_changes)
        self.assertEqual(kwargs["max_instances"], 2)
        self.assertTrue(kwargs["replace_existing"])

    def test_handshake_is_acknowledged_without_running(self):
        self.headers["X-Goog-Resource-State"] = "sync"
        self.assertEqual(self.post().status_code, 200)
        self.scheduler.add_job.assert_not_called()

    def test_wrong_token_is_rejected(self):
        self.headers["X-Goog-Channel-Token"] = "wrong"
        self.assertEqual(self.post().status_code, 401)
        self.scheduler.add_job.assert_not_called()


class TestRegisterDriveChannel(unittest.TestCase):
    def setUp(self):
        from webapp import app as module

        self.module = module
        self.drive = Mock()
        self.cache = Mock()
        self.cache.add.return_value = True
        patches = [
            patch.object(module, "gdrive_instance", self.drive),
            patch.object(module, "cache", self.cache),
            patch.dict(
                module.os.environ,
                {
                    "GOOGLE_DRIVE_WEBHOOK_URL": "https://example.com/hook",
                    "GOOGLE_DRIVE_WEBHOOK_TOKEN": "secret",
                },
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_registers_prefixed_channel(self):
        self.drive.watch_changes.return_value = {
            "id": "library-x",
        }
        self.module.register_drive_channel()
        address, channel_id, token, _ = self.drive.watch_changes.call_args.args
        self.assertEqual(address, "https://example.com/hook")
        self.assertTrue(channel_id.startswith("library-"))
        self.assertEqual(token, "secret")

    def test_each_registration_uses_a_new_channel_id(self):
        self.drive.watch_changes.return_value = {
            "id": "x",
        }
        self.module.register_drive_channel()
        self.module.register_drive_channel()
        first, second = (
            c.args[1] for c in self.drive.watch_changes.call_args_list
        )
        self.assertNotEqual(first, second)

    def test_failure_releases_lock(self):
        self.drive.watch_changes.side_effect = RuntimeError("down")
        self.module.register_drive_channel()
        self.cache.delete.assert_called_once_with("drive_channel")

    def test_skips_when_not_configured(self):
        with patch.dict(
            self.module.os.environ, {"GOOGLE_DRIVE_WEBHOOK_URL": ""}
        ):
            self.module.register_drive_channel()
        self.drive.watch_changes.assert_not_called()


class TestDriveWebhookValidation(unittest.TestCase):
    def setUp(self):
        self.headers = {
            "X-Goog-Channel-Token": "secret",
            "X-Goog-Resource-State": "change",
        }

    def test_accepts_matching_token(self):
        self.assertTrue(validate_drive_notification(self.headers, "secret"))

    def test_accepts_sync_notification(self):
        self.headers["X-Goog-Resource-State"] = "sync"
        self.assertTrue(validate_drive_notification(self.headers, "secret"))

    def test_rejects_wrong_or_missing_token(self):
        self.assertFalse(validate_drive_notification(self.headers, "other"))
        del self.headers["X-Goog-Channel-Token"]
        self.assertFalse(validate_drive_notification(self.headers, "secret"))

    def test_rejects_when_no_token_is_configured(self):
        self.assertFalse(validate_drive_notification(self.headers, None))
        self.assertFalse(validate_drive_notification(self.headers, ""))

    def test_rejects_missing_or_unknown_state(self):
        self.headers["X-Goog-Resource-State"] = "update"
        self.assertFalse(validate_drive_notification(self.headers, "secret"))
        del self.headers["X-Goog-Resource-State"]
        self.assertFalse(validate_drive_notification(self.headers, "secret"))


class TestWatchChanges(unittest.TestCase):
    def test_watch_uses_fresh_shared_drive_token(self):
        drive = GoogleDrive.__new__(GoogleDrive)
        drive.service = Mock()
        changes = drive.service.changes.return_value
        changes.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": "cursor"
        }
        drive.watch_changes("https://example.com/hook", "id", "secret", 99)
        changes.getStartPageToken.assert_called_once_with(
            driveId=TARGET_DRIVE, supportsAllDrives=True
        )
        kwargs = changes.watch.call_args.kwargs
        self.assertEqual(kwargs["pageToken"], "cursor")
        self.assertEqual(kwargs["driveId"], TARGET_DRIVE)
        self.assertEqual(
            kwargs["body"],
            {
                "id": "id",
                "type": "web_hook",
                "address": "https://example.com/hook",
                "token": "secret",
                "expiration": 99,
            },
        )


if __name__ == "__main__":
    unittest.main()
