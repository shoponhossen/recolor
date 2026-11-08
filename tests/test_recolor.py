import pytest
import numpy as np
from pathlib import Path
import tempfile
import cv2
from unittest.mock import MagicMock

from backend.backend import (
    Mask,
    Layer,
    ADJUSTMENTS_LIST,
    ADJUSTMENTS_MAP,
    ADJUSTMENTS_BY_CATEGORY,
    Exposure,
    Contrast,
    Temperature,
    Saturation,
    Clarity,
)
from app import Project, ProjectManager, ReColor
from utils import arr_to_jpeg_bytes, create_mask_overlay, load_rgba, save_rgba
from pages.home import home_view
from pages.editor import editor_view
from pages.selector import selector_view
from pages.create import create_view


def test_adjustments_basic():
    arr = np.random.randint(20, 220, (100, 100, 4), dtype=np.uint8)

    # Test all registered adjustments
    for adj in ADJUSTMENTS_LIST:
        out_pos = adj.apply(arr, 30.0)
        out_neg = adj.apply(arr, -30.0)
        out_zero = adj.apply(arr, 0.0)

        assert out_pos.shape == arr.shape
        assert out_pos.dtype == np.uint8
        assert out_neg.shape == arr.shape
        assert np.array_equal(out_zero, arr)


def test_mask_operations():
    shape = (120, 100)
    mask = Mask(size=shape)
    assert mask.data.shape == shape
    assert np.allclose(mask.data, 1.0)

    # Invert
    mask.invert()
    assert np.allclose(mask.data, 0.0)

    # Fill
    mask.fill()
    assert np.allclose(mask.data, 1.0)

    # Clear
    mask.clear()
    assert np.allclose(mask.data, 0.0)

    # Brush stroke
    pts = [(20.0, 20.0), (40.0, 40.0), (60.0, 60.0)]
    mask.add_brush_stroke(pts, radius=10.0, erase=False)
    assert mask.data.max() > 0.0

    # Radial gradient
    mask.set_radial_gradient(center=(50, 60), radius_x=30, radius_y=30, feather=0.5)
    assert 0.0 <= mask.data.min() <= mask.data.max() <= 1.0

    # Linear gradient
    mask.set_linear_gradient(start_pt=(50, 0), end_pt=(50, 100))
    assert 0.0 <= mask.data.min() <= mask.data.max() <= 1.0

    # Resizing
    resized = mask.at((60, 50))
    assert resized.shape == (60, 50)


def test_layer_pipeline():
    arr = np.full((100, 100, 4), 100, dtype=np.uint8)
    mask = Mask(size=(100, 100))

    layer = Layer(name="Exposure Boost", mask=mask, mask_type="global")
    layer.values["exposure"] = 50.0

    out = layer.apply(arr)
    # Brightness should increase
    assert out[..., :3].mean() > arr[..., :3].mean()

    # Opacity test
    layer.opacity = 0.5
    out_half = layer.apply(arr)
    assert out_half[..., :3].mean() < out[..., :3].mean()


def test_project_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        im = np.random.randint(50, 200, (200, 150, 4), dtype=np.uint8)

        p = Project(name="TestProj", im_arr=im, pd=tmp_path)
        assert p.preview_image_array.shape[0] <= 800

        # Add layers
        l1 = p.add_layer("Global", "global")
        l1.values["exposure"] = 25.0

        l2 = p.add_layer("Radial Focus", "radial")
        l2.values["contrast"] = 30.0

        # Render preview
        prev = p.render_preview()
        assert prev.shape[:2] == p.preview_image_array.shape[:2]

        # Duplicate layer
        dup = p.duplicate_layer(l2)
        assert len(p.layers) == 3

        # Remove layer
        p.remove_layer(dup)
        assert len(p.layers) == 2

        # Save and reload
        p.save()
        proj_file = tmp_path / "TestProj.rclr"
        assert proj_file.exists()

        pm = ProjectManager()
        pm.projects_directory = tmp_path
        loaded = pm.load_project("TestProj")
        assert loaded.name == "TestProj"
        assert len(loaded.layers) == 2
        assert loaded.selected_layer is not None

        # Full resolution export
        export_file = tmp_path / "exported.jpg"
        loaded.export_full_image(export_file)
        assert export_file.exists()
        assert export_file.stat().st_size > 0


def test_utils_jpeg_and_overlay():
    arr = np.random.randint(0, 255, (80, 80, 4), dtype=np.uint8)
    jpeg_bytes = arr_to_jpeg_bytes(arr)
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0

    mask = np.ones((80, 80), dtype=np.float32)
    overlay = create_mask_overlay(arr, mask)
    assert overlay.shape == arr.shape
    assert overlay.dtype == np.uint8


def test_views_initialization():
    page = MagicMock()
    page.platform = None
    app = ReColor(page)

    hv = home_view(page, app)
    assert hv.route == "/"

    ev = editor_view(page, app)
    assert ev.route == "/editor"

    sv = selector_view(page, app)
    assert sv.route == "/editor/selector"

    cv = create_view(page, app)
    assert cv.route == "/create"
