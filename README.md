# ReColor - Mobile Color Grading & Layer Masking

**ReColor** is a mobile-first professional photo color grading application built with **Flet** (Python + Flutter) and **OpenCV / NumPy**. Inspired by Adobe Lightroom's selective masking and color grading workflow, ReColor empowers creators to create isolated layers and precision masks where adjustments only affect the selected layer.

---

## Key Features

### 1. Lightroom-Style Layer & Mask Architecture
- **Multi-Layer System**: Add multiple independent adjustment layers stacked sequentially.
- **Layer Isolation**: Any slider adjustment only affects the currently selected layer.
- **Selective Mask Types**:
  - **Global Adjustments**: Affects the entire frame.
  - **Brush Mask**: Freehand paint and erase with customizable brush size and feather.
  - **Radial Gradient**: Soft elliptical falloff with customizable center, radii, and feather.
  - **Linear Gradient**: Directional transitions (Sky / Ground / Horizon).
  - **Color Range Mask**: Tap any pixel on the image to isolate and grade specific colors with tolerance tuning.
- **Mask Operations**:
  - **Rubylith Mask Overlay**: Toggle a red semi-transparent mask preview (just like Lightroom) to see exactly which pixels are affected.
  - **Invert Mask**: Flip mask coverage in one click.
  - **Layer Duplication & Deletion**: Duplicate complex masks and adjustments with ease.
  - **Layer Visibility**: Quickly toggle any layer on/off to compare its impact.

### 2. Comprehensive Color Grading Suite
- **Light Controls**:
  - **Exposure**: Dynamic range brightness with power curve.
  - **Contrast**: Midtone-preserving S-curve contrast.
  - **Highlights**: Selective upper luminance compression/boost.
  - **Shadows**: Selective lower luminance lift/deepen.
  - **Whites**: Extreme highlight point adjustment.
  - **Blacks**: Extreme black point adjustment.
- **Color Controls**:
  - **Temperature**: Warm (Amber) to Cool (Blue) chromatic balance.
  - **Tint**: Green to Magenta balance.
  - **Vibrance**: Saturation boost weighted to preserve skin tones and prevent clipping.
  - **Saturation**: Full HSV saturation scaling.
  - **Hue**: Smooth hue rotation.
- **Effects & Detail**:
  - **Clarity**: Local midtone contrast enhancement.
  - **Vignette**: Center-radial perimeter falloff.
  - **Sharpen / Soften**: Fine edge unsharp masking.

### 3. Real-Time Performance & Workflow
- **Vectorized LUT Processing**: Almost all tone curves run via 8-bit lookup tables (`cv2.LUT`) taking under 5ms per frame.
- **Cached Render Pipeline**: Modifying layer $k$ only re-composites layers from $k$ upwards.
- **Before / After Comparison**: Press the compare button to instantly toggle between original unedited image and graded image.
- **Lossless & High-Res Export**: Save projects (`.rclr`) and export full-resolution JPEG/PNG images.

---

## App Structure

```
recolor/
├── src/
│   ├── app.py                # Project, ProjectManager, and Layer cache pipeline
│   ├── colors.py             # Design system & color constants
│   ├── main.py               # Flet app entry point & route definitions
│   ├── utils.py              # Fast image encoding, EXIF handling & rubylith overlay
│   ├── assets/               # App icons and placeholders
│   ├── backend/
│   │   └── backend.py        # Complete grading engine, adjustments, Mask & Layer
│   ├── components/
│   │   └── slider.py         # CenterSlider & AdjustmentRow components
│   └── pages/
│       ├── home.py           # Project gallery & quick demo launcher
│       ├── editor.py         # Main grading workspace & layer bar
│       ├── selector.py       # Mask Studio (Brush, Radial, Linear, Color Range)
│       └── create.py         # Project creation & photo importer
├── tests/
│   └── test_recolor.py       # Automated test suite
└── pyproject.toml
```

---

## Running the App

### Requirements
- Python `>=3.10`
- `flet>=1.0.3`
- `opencv-python>=5.0.0.93`

### Run as a Desktop App
```bash
uv run flet run
```

### Run as a Mobile-Simulated / Web App
```bash
uv run flet run --web
```

### Run Tests
```bash
uv run pytest -v
```

---

## Building for Mobile

### Android (.apk / .aab)
```bash
flet build apk -v
```

### iOS (.ipa)
```bash
flet build ipa -v
```
