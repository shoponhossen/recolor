import flet as ft
from utils import get_projects_dir, load_rgba, save_rgba, create_mask_overlay
import pickle
from pathlib import Path
import numpy as np
import cv2
import copy
from backend.backend import (
    Layer,
    Mask,
    ADJUSTMENTS_LIST,
    ADJUSTMENTS_MAP,
    Exposure,
)


class Project:
    def __init__(self, name: str, im_arr: np.ndarray, pd: Path):
        self.name = name
        self.image_array: np.ndarray = im_arr
        self.preview_image_array: np.ndarray = self.generate_preview_image()

        self.projects_directory: Path = pd
        self.layers: list[Layer] = []
        self._cache: list[np.ndarray | None] = []
        self.selected_layer: Layer | None = None

    def __setstate__(self, state):
        """Ensure backward compatibility when loading serialized projects."""
        self.__dict__.update(state)
        if not hasattr(self, "_cache") or self._cache is None:
            self._cache = []
        if not hasattr(self, "selected_layer") or self.selected_layer is None:
            self.selected_layer = self.layers[0] if self.layers else None
        if not hasattr(self, "preview_image_array") or self.preview_image_array is None:
            self.preview_image_array = self.generate_preview_image()

        # Ensure all layers have valid attributes
        for idx, layer in enumerate(self.layers):
            if not hasattr(layer, "id"):
                layer.id = f"l_{idx}"
            if not hasattr(layer, "name"):
                layer.name = f"Layer {idx + 1}"
            if not hasattr(layer, "mask_type"):
                layer.mask_type = "global" if idx == 0 else "brush"
            if not hasattr(layer, "visible"):
                layer.visible = True
            if not hasattr(layer, "opacity"):
                layer.opacity = 1.0
            if not hasattr(layer, "inverted"):
                layer.inverted = False
            if not hasattr(layer, "values"):
                layer.values = {}
            # Ensure all adjustments are present in values
            for adj in ADJUSTMENTS_LIST:
                if adj.key not in layer.values:
                    layer.values[adj.key] = adj.default_val
            # Ensure mask has sub_masks list (backward compat)
            if hasattr(layer, "mask") and layer.mask is not None:
                if not hasattr(layer.mask, "sub_masks"):
                    layer.mask.sub_masks = []

    def generate_preview_image(self, max_side: int = 800) -> np.ndarray:
        """Create a scaled down preview image under max_side px for snappy interactive performance."""
        h, w = self.image_array.shape[:2]
        s = max_side / float(max(h, w))

        if s >= 1.0:
            return self.image_array.copy()

        new_w = max(1, int(round(w * s)))
        new_h = max(1, int(round(h * s)))
        return cv2.resize(self.image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def invalidate_cache(self, dirty: int = 0):
        """Resize and invalidate cache starting from layer `dirty`."""
        while len(self._cache) < len(self.layers):
            self._cache.append(None)
        if len(self._cache) > len(self.layers):
            self._cache = self._cache[: len(self.layers)]

        for i in range(max(0, dirty), len(self._cache)):
            self._cache[i] = None

    def render_preview(
        self,
        dirty: int = 0,
        show_overlay_for_layer: Layer | None = None,
    ) -> np.ndarray:
        """
        Recomputes preview layers only from layer `dirty` upward.
        If show_overlay_for_layer is specified, composites the red rubylith mask overlay.
        """
        while len(self._cache) < len(self.layers):
            self._cache.append(None)
        if len(self._cache) > len(self.layers):
            self._cache = self._cache[: len(self.layers)]

        for i in range(max(0, dirty), len(self.layers)):
            src = (
                self._cache[i - 1]
                if (i > 0 and self._cache[i - 1] is not None)
                else self.preview_image_array
            )
            self._cache[i] = self.layers[i].apply(src)

        final_composite = (
            self._cache[-1]
            if (self.layers and self._cache and self._cache[-1] is not None)
            else self.preview_image_array
        )

        if show_overlay_for_layer is not None and show_overlay_for_layer.mask is not None:
            mask_arr = show_overlay_for_layer.get_effective_mask(final_composite.shape[:2])
            return create_mask_overlay(final_composite, mask_arr)

        return final_composite

    def render_full(self) -> np.ndarray:
        """Render all layers at full original resolution."""
        arr = self.image_array
        for layer in self.layers:
            arr = layer.apply(arr)
        return arr

    def add_layer(
        self,
        name: str | None = None,
        mask_type: str = "brush",
    ) -> Layer:
        """Create and add a new layer with the specified mask type."""
        shape = self.image_array.shape[:2]
        layer_num = len(self.layers) + 1

        mask_count = sum(1 for l in self.layers if l.mask_type != "global") + 1

        if mask_type == "global":
            mask = Mask(size=shape)
            default_name = "Global"
        else:
            default_name = f"M{mask_count}"
            if mask_type == "brush":
                mask = Mask(size=shape).clear()
            elif mask_type == "radial":
                mask = Mask(size=shape).clear()
            elif mask_type == "linear":
                mask = Mask(size=shape).clear()
            elif mask_type == "color":
                mask = Mask(size=shape)
                h, w = shape
                sample_rgb = tuple(int(c) for c in self.image_array[h // 2, w // 2][:3])
                mask.set_color_range(self.image_array, sample_rgb, tolerance=0.3)
            else:
                mask = Mask(size=shape).clear()

        new_layer = Layer(
            name=name or default_name,
            mask=mask,
            mask_type=mask_type,
            visible=True,
            opacity=1.0,
        )

        self.layers.append(new_layer)
        self.selected_layer = new_layer
        self.invalidate_cache(len(self.layers) - 1)
        return new_layer

    def duplicate_layer(self, layer: Layer) -> Layer:
        """Duplicate an existing layer including its mask and adjustments."""
        new_mask = layer.mask.copy() if layer.mask is not None else None
        dup = Layer(
            name=f"{layer.name} (Copy)",
            mask=new_mask,
            mask_type=layer.mask_type,
            visible=layer.visible,
            opacity=layer.opacity,
            inverted=layer.inverted,
        )
        dup.values = copy.deepcopy(layer.values)

        idx = self.layers.index(layer) if layer in self.layers else len(self.layers) - 1
        self.layers.insert(idx + 1, dup)
        self.selected_layer = dup
        self.invalidate_cache(idx + 1)
        return dup

    def remove_layer(self, layer: Layer) -> bool:
        """Remove a layer. Keeps at least one global layer if list becomes empty."""
        if layer not in self.layers:
            return False

        idx = self.layers.index(layer)
        self.layers.remove(layer)

        if not self.layers:
            # Recreate base global layer
            self.add_layer(name="Global", mask_type="global")
        else:
            new_idx = max(0, min(idx, len(self.layers) - 1))
            self.selected_layer = self.layers[new_idx]

        self.invalidate_cache(max(0, idx - 1))
        return True

    def export_full_image(self, target_path: str | Path, quality: int = 95) -> None:
        """Render full-resolution graded image and save to disk."""
        rendered = self.render_full()
        save_rgba(rendered, target_path, quality=quality)

    def save(self):
        """Save project state to .rclr pickle file."""
        if not self.projects_directory.exists():
            self.projects_directory.mkdir(parents=True, exist_ok=True)
        path = self.projects_directory / f"{self.name}.rclr"
        with open(path, "wb") as f:
            pickle.dump(self, f)


class ProjectManager:
    def __init__(self, page: ft.Page | None = None):
        self.page = page
        self.projects_directory: Path = get_projects_dir(self.page)
        self.project: Project | None = None

    def create_project(self, project_name: str, im_full_path: str | Path) -> Project:
        im_arr = load_rgba(im_full_path)
        self.project = Project(
            name=project_name, im_arr=im_arr, pd=self.projects_directory
        )

        # Create initial default Global layer
        self.project.add_layer(name="Global", mask_type="global")
        self.project.save()
        return self.project

    def load_project(self, project_name: str) -> Project:
        file_path = self.projects_directory / f"{project_name}.rclr"
        with open(file_path, "rb") as f:
            self.project = pickle.load(f)
        return self.project

    def delete_project(self, project_name: str) -> bool:
        file_path = self.projects_directory / f"{project_name}.rclr"
        if file_path.exists():
            file_path.unlink()
            if self.project and self.project.name == project_name:
                self.project = None
            return True
        return False

    def list_project_paths(self) -> list[Path]:
        if not self.projects_directory.exists():
            return []
        return sorted(
            [
                p
                for p in self.projects_directory.iterdir()
                if p.is_file() and p.suffix == ".rclr"
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def list_projects(self) -> list[str]:
        return [p.stem for p in self.list_project_paths()]


class ReColor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.projects_manager = ProjectManager(self.page)
        self.active_mask_layer: Layer | None = None
        self.file_picker = ft.FilePicker()
        if hasattr(page, "services") and hasattr(page.services, "append"):
            if self.file_picker not in page.services:
                page.services.append(self.file_picker)
