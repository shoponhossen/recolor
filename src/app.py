import flet as ft
from utils import get_projects_dir
import pickle
from pathlib import Path
from utils import load_rgba
import numpy as np
import cv2
from backend.backend import Layer, Exposure, Mask


class Project:
    def __init__(self, name, im_arr, pd):
        self.name = name

        self.image_array: np.ndarray = im_arr
        self.edited_image_array = None
        self.preview_image_array = self.generate_preview_image()

        self.projects_directory = pd

        self.layers: list[Layer] = []
        self._cache: list = []

        self.selected_layer: Layer | None = None

    def render_preview(self, dirty=0):
        """Recompute only from layer `dirty` upward."""
        for i in range(dirty, len(self.layers)):
            src = self._cache[i - 1] if i else self.preview_image_array
            self._cache[i] = self.layers[i].apply(src)
        return self._cache[-1] if self.layers else self.preview_image_array

    def render_full(self):
        arr = self.image_array
        for l in self.layers:
            arr = l.apply(arr)
        return arr

    def generate_preview_image(self, max_side=800):
        """
        create a image that under 800px
        """
        h, w = self.image_array.shape[:2]
        s = max_side / max(h, w)

        if s < 1:
            return self.image_array.copy()

        return cv2.resize(
            self.image_array, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA
        )

    def save(self):
        with open(self.projects_directory / f"{self.name}.rclr", "wb") as f:
            pickle.dump(self, f)


class ProjectManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.projects_directory: Path = get_projects_dir(self.page)

        # Current Project
        self.project: Project | None = None

    def create_project(self, project_name: str, im_full_path: str):
        im_arr = load_rgba(im_full_path)
        self.project: Project = Project(
            name=project_name, im_arr=im_arr, pd=self.projects_directory
        )

        # Global Default Layer
        self.project.layers = [
            Layer(
                [Exposure()],
                mask=Mask(size=self.project.image_array.shape[:2]),
            )
        ]

        self.project.selected_layer = self.project.layers[0]
        print("Layer Created with default mask")

    def load_project(self, project_name: str):
        dir = self.projects_directory

        with open(dir / f"{project_name}.rclr", "rb") as f:
            self.project: Project = pickle.load(f)

    def list_project_paths(self):
        return [
            p
            for p in self.projects_directory.iterdir()
            if p.is_file() and p.suffix == ".rclr"
        ]

    def list_projects(self):
        return [p.stem for p in self.list_project_paths()]


class ReColor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.projects_manager = ProjectManager(self.page)

        self.file_picker = ft.FilePicker()
