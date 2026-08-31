from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"
APPLICATION_VERSION = VERSION_FILE.read_text(encoding="utf-8").strip()

if not APPLICATION_VERSION:
    raise RuntimeError("VERSION must contain the application release")
