"""Turn a saved call recording into timestamped transcript files."""

from pathlib import Path
from typing import Any, Protocol

from voice_bot.transcripts import Speaker, TranscriptSegment, save_transcript


class TranscriptionError(ValueError):
    """Raised when a call recording cannot be transcribed safely."""


class TranscriptionProvider(Protocol):
    """Provider interface implemented by an offline fake and OpenAI."""

    def transcribe(self, recording_path: Path) -> list[TranscriptSegment]:
        """Return speaker-labeled, timestamped segments for an audio file."""


class InMemoryTranscriptionProvider:
    """Return scripted transcript segments without reading or uploading audio."""

    def __init__(self, segments: list[TranscriptSegment]) -> None:
        self._segments = list(segments)
        self.requested_paths: list[Path] = []

    def transcribe(self, recording_path: Path) -> list[TranscriptSegment]:
        """Record the request and return a copy of the scripted response."""
        self.requested_paths.append(recording_path)
        return list(self._segments)


class OpenAITranscriptionProvider:
    """Transcribe a completed recording with speaker diarization."""

    def __init__(
        self,
        client: Any,
        *,
        speaker_map: dict[str, Speaker],
        model: str = "gpt-4o-transcribe-diarize",
    ) -> None:
        self._client = client
        self._speaker_map = dict(speaker_map)
        self._model = model

    def transcribe(self, recording_path: Path) -> list[TranscriptSegment]:
        with recording_path.open("rb") as audio_file:
            result = self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                response_format="diarized_json",
                chunking_strategy="auto",
            )

        raw_segments = getattr(result, "segments", None)
        if not isinstance(raw_segments, list):
            raise TranscriptionError("OpenAI did not return diarized segments.")

        segments: list[TranscriptSegment] = []
        for raw in raw_segments:
            speaker_label = _field(raw, "speaker")
            speaker = self._speaker_map.get(str(speaker_label))
            if speaker is None:
                raise TranscriptionError(
                    f"No project speaker mapping exists for {speaker_label!r}."
                )
            segments.append(
                TranscriptSegment(
                    speaker=speaker,
                    start_ms=round(float(_field(raw, "start")) * 1000),
                    end_ms=round(float(_field(raw, "end")) * 1000),
                    text=str(_field(raw, "text")),
                )
            )
        return segments


def _field(value: Any, name: str) -> Any:
    """Read a field from an SDK object or a plain test dictionary."""
    if isinstance(value, dict):
        if name in value:
            return value[name]
    elif hasattr(value, name):
        return getattr(value, name)
    raise TranscriptionError(f"Transcription segment is missing {name!r}.")


def transcribe_recording(
    call_directory: Path,
    provider: TranscriptionProvider,
) -> tuple[Path, Path]:
    """Transcribe recording.mp3 and save transcript.json and transcript.md."""
    recording_path = call_directory / "recording.mp3"
    if not recording_path.is_file():
        raise TranscriptionError(f"Call recording not found: {recording_path}.")

    segments = provider.transcribe(recording_path)
    return save_transcript(call_directory, segments)
