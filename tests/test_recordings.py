"""Tests for provider-neutral MP3 recording storage."""

import tempfile
import unittest
from pathlib import Path

from voice_bot.recordings import (
    InMemoryRecordingProvider,
    RecordingError,
    TwilioRecordingProvider,
    save_recording,
)
from voice_bot.runs import create_call_run


class FakeRecordingProvider:
    """Returns in-memory bytes and never performs a download."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.requested_ids: list[str] = []

    def download_mp3(self, recording_id: str) -> bytes:
        self.requested_ids.append(recording_id)
        return self.content


class RecordingTests(unittest.TestCase):
    def test_twilio_recording_adapter_requests_mp3(self) -> None:
        requests = []

        def request(url, **kwargs):
            requests.append((url, kwargs))
            return type(
                "Response",
                (),
                {"status_code": 200, "content": b"ID3twilio"},
            )()

        provider = TwilioRecordingProvider(
            "AC-test",
            "test-token",
            requester=request,
        )

        content = provider.download_mp3("RE-test")

        self.assertEqual(content, b"ID3twilio")
        self.assertEqual(
            requests,
            [
                (
                "https://api.twilio.com/2010-04-01/Accounts/AC-test/"
                "Recordings/RE-test.mp3",
                    {"auth": ("AC-test", "test-token"), "timeout": 30},
                )
            ],
        )

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.call_directory = create_call_run(
            "schedule_appointment_001",
            call_id="recording-test-001",
            output_root=Path(self.temporary_directory.name),
        )

    def test_saves_mp3_from_fake_provider(self) -> None:
        content = b"ID3" + b"fictional mp3 bytes"
        provider = FakeRecordingProvider(content)

        path = save_recording(self.call_directory, provider, "RE-fake-001")

        self.assertEqual(path.name, "recording.mp3")
        self.assertEqual(path.read_bytes(), content)
        self.assertEqual(provider.requested_ids, ["RE-fake-001"])

    def test_in_memory_provider_never_needs_a_download(self) -> None:
        provider = InMemoryRecordingProvider(b"ID3fictional bytes")

        path = save_recording(self.call_directory, provider, "offline-recording")

        self.assertEqual(path.read_bytes(), b"ID3fictional bytes")
        self.assertEqual(provider.requested_ids, ["offline-recording"])

    def test_accepts_mpeg_frame_sync_header(self) -> None:
        provider = FakeRecordingProvider(b"\xff\xfb" + b"fictional frame")

        path = save_recording(self.call_directory, provider, "RE-fake-002")

        self.assertTrue(path.exists())

    def test_rejects_non_mp3_provider_response(self) -> None:
        provider = FakeRecordingProvider(b"not an mp3")

        with self.assertRaises(RecordingError):
            save_recording(self.call_directory, provider, "RE-fake-003")

    def test_rejects_unsafe_recording_id_before_provider_call(self) -> None:
        provider = FakeRecordingProvider(b"ID3fake")

        with self.assertRaises(RecordingError):
            save_recording(self.call_directory, provider, "../outside")

        self.assertEqual(provider.requested_ids, [])

    def test_refuses_to_overwrite_existing_recording(self) -> None:
        provider = FakeRecordingProvider(b"ID3first")
        save_recording(self.call_directory, provider, "RE-first")

        with self.assertRaises(RecordingError):
            save_recording(self.call_directory, provider, "RE-second")

        self.assertEqual(provider.requested_ids, ["RE-first"])

    def test_requires_call_metadata_before_provider_call(self) -> None:
        provider = FakeRecordingProvider(b"ID3fake")
        missing_run = Path(self.temporary_directory.name) / "missing"
        missing_run.mkdir()

        with self.assertRaises(RecordingError):
            save_recording(missing_run, provider, "RE-fake-004")

        self.assertEqual(provider.requested_ids, [])


if __name__ == "__main__":
    unittest.main()
