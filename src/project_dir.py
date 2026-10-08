import os
from pathlib import Path
import flet as ft


def get_projects_dir(page: ft.Page) -> Path:
    if page.platform == ft.PagePlatform.ANDROID:
        # App-private storage: no permissions needed, works on every Android version
        base = Path(os.environ["FLET_APP_STORAGE_DATA"])
    else:
        # Windows / Linux: a visible, user-friendly location
        base = Path.home() / "Documents"

    projects = base / "ReColor" / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    return projects
