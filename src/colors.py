import flet as ft


class C:
    # 60% - backgrounds
    PRIMARY = "#0B0F17"

    # 30% - cards, nav bar, inputs
    SECONDARY = "#111521"

    # Level 3 - chips, inner boxes on a card
    TERTIARY = "#151A29"

    # 10% - CTA buttons, active tab, links
    ACCENT = "#FF5722"

    WHITE = "#FFFFFF"
    BLACK = "#000000"

    SUCCESS = "#22C55E"
    ERROR = "#EF4444"
    WARNING = "#FFB300"  # money / prize amounts
    INFO = "#22D3EE"  # badges like Squad (4v4)


def soft(color, opacity=0.15):
    """Tinted background for badges/chips, e.g. soft(C.SUCCESS)"""
    return ft.Colors.with_opacity(opacity, color)


MUTED = ft.Colors.with_opacity(0.6, C.WHITE)  # secondary text
BORDER = ft.Colors.with_opacity(0.12, C.WHITE)  # card borders
