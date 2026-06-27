from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CALIBRE_ROOT = Path("/srv/media/calibre-library")
DEFAULT_MUSIC_ROOT = Path("/srv/media/music")
GITHUB_PAGES_BASE = "https://rib-thiago.github.io/pages-library"
MAX_RESULTS = 30
PAGE_SIZE = 100

AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav"}
MIME_TYPES = {
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
}
COVER_NAMES = [
    "cover.jpg",
    "cover.jpeg",
    "folder.jpg",
    "folder.jpeg",
    "front.jpg",
    "front.jpeg",
    "cover.png",
    "folder.png",
    "front.png",
]
FORBIDDEN_SOURCE_ROOTS = [DEFAULT_MUSIC_ROOT.resolve(), DEFAULT_CALIBRE_ROOT.resolve()]


@dataclass(frozen=True)
class AppConfig:
    repo_root: Path
    catalog: Path
    calibre_root: Path
    music_root: Path

