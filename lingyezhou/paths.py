"""Separate bundled read-only resources from writable user data."""
import os
import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / relative


def user_data_dir() -> Path:
    if os.environ.get("LINGYEZHOU_DATA_DIR"):
        return Path(os.environ["LINGYEZHOU_DATA_DIR"]).expanduser().absolute()
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "Lingyezhou"


def initialize_working_directory() -> None:
    if getattr(sys, "frozen", False):
        directory = user_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        os.chdir(directory)
