"""Fixtures shared by more than one test file."""
import pytest

import remote_sync
from remote_sync import SyncAnswer


class FakeSync:
    """Stands in for remote_sync.send_status. A test sets `answer` or `error`
    before syncing, and afterwards reads what the monitor sent."""

    def __init__(self):
        self.answer = SyncAnswer(pending_grants=[], settings_change=None)
        self.error = None
        self.calls = 0
        self.status = None
        self.applied_grant_ids = None
        self.server_url = None
        self.token = None

    def send_status(self, status, applied_grant_ids, server_url, token):
        self.calls += 1
        self.status = status
        self.applied_grant_ids = applied_grant_ids
        self.server_url = server_url
        self.token = token
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture
def sync(monkeypatch):
    fake = FakeSync()
    monkeypatch.setattr(remote_sync, "send_status", fake.send_status)
    return fake
