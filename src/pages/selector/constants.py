import flet as ft

# Colour constants for sub-mask modes
ERASE_COLOR = (60, 100, 255)  # blue tint for erase sub-masks
PAINT_COLOR = (50, 200, 100)  # green tint for paint sub-masks
MAIN_COLOR = (255, 45, 45)  # red rubylith for main/effective

# Preset colors for Color Range mask picker
PRESET_COLORS = [
    ("Red", (235, 50, 50)),
    ("Orange", (255, 140, 0)),
    ("Yellow", (250, 210, 20)),
    ("Green", (46, 204, 113)),
    ("Cyan", (0, 188, 212)),
    ("Blue", (41, 128, 185)),
    ("Purple", (155, 89, 182)),
    ("Magenta", (233, 30, 99)),
    ("Skin", (245, 205, 175)),
    ("Tan", (185, 120, 75)),
    ("White", (250, 250, 250)),
    ("Gray", (128, 128, 128)),
    ("Black", (25, 25, 25)),
]

# Available Mask Studio tools
TOOLS = [
    ("brush", ft.Icons.BRUSH, "Brush"),
    ("radial", ft.Icons.RADIO_BUTTON_CHECKED, "Radial"),
    ("linear", ft.Icons.GRADIENT, "Linear"),
    ("color", ft.Icons.COLORIZE, "Color"),
]


def get_mask_icon(mask_type: str):
    """Return corresponding Flutter icon for a layer's mask type."""
    return {
        "global": ft.Icons.PUBLIC,
        "brush": ft.Icons.BRUSH,
        "radial": ft.Icons.RADIO_BUTTON_CHECKED,
        "linear": ft.Icons.GRADIENT,
        "color": ft.Icons.COLORIZE,
        "luminance": ft.Icons.BRIGHTNESS_6,
    }.get(mask_type, ft.Icons.LAYERS)
