import flet as ft
from project_dir import get_projects_dir
import pickle
from pathlib import Path
from utils import load_rgba


class Project:
    def __init__(self, projects_dir: Path):
        self.name = None
        self.im_arr = None
        self.projects_dir = projects_dir

    def create(self, name: str, image_path: str):
        self.name = name
        self.im_arr = load_rgba(image_path)

    def open(self, name: str):
        with open(self.projects_dir / f"{name}.rclr", "rb") as f:
            project = pickle.load(f)
            self.name = project.name
            self.im_arr = project.im_arr

    def save(self):
        with open(self.projects_dir / f"{self.name}.rclr", "wb") as f:
            pickle.dump(self, f)


class ProjectManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.projects_dir: Path = get_projects_dir(self.page)

    def list_project_paths(self):
        return [
            p
            for p in self.projects_dir.iterdir()
            if p.is_file() and p.suffix == ".rclr"
        ]

    def list_projects(self):
        return [p.stem for p in self.list_project_paths()]


class ReColor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.projects_manager = ProjectManager(self.page)
        self.project = Project(self.projects_manager.projects_dir)
        self.file_picker = ft.FilePicker()
