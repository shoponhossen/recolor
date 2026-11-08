import flet as ft
from typing import Callable, Optional
import asyncio
import inspect


@ft.control
class CenterSlider(ft.Stack):
    min: float = -100.0
    max: float = 100.0
    step: float = 1.0
    debounce_ms: int = 50
    value: float = 0.0
    on_change: Optional[Callable] = None
    on_change_start: Optional[Callable] = None
    on_change_end: Optional[Callable] = None

    def init(self):
        self._task = None
        self.height = 36

        # Active fill colors
        self.track_color = ft.Colors.with_opacity(0.18, ft.Colors.WHITE)
        self.fill_color = ft.Colors.ORANGE_ACCENT_700

        self.bar = ft.Row(
            [
                ft.Container(height=4, border_radius=ft.BorderRadius.all(2))
                for _ in range(3)
            ],
            spacing=0,
        )
        self.slider = ft.Slider(
            min=self.min,
            max=self.max,
            value=self.value,
            divisions=int(round((self.max - self.min) / self.step)),
            active_color=ft.Colors.TRANSPARENT,
            inactive_color=ft.Colors.TRANSPARENT,
            on_change=self._changed,
            on_change_start=self.on_change_start,
            on_change_end=self._ended,
        )
        self.controls = [
            ft.Container(
                self.bar,
                padding=ft.Padding.symmetric(horizontal=12),
                alignment=ft.Alignment.CENTER,
            ),
            self.slider,
        ]
        self._paint(self.value)

    def _paint(self, v):
        span = self.max - self.min
        if span <= 0:
            return
        pos = (v - self.min) / span
        mid = (0.0 - self.min) / span

        p1 = max(0.0, min(pos, mid))
        p2 = max(0.0, abs(pos - mid))
        p3 = max(0.0, 1.0 - max(pos, mid))

        parts = [
            (p1, self.track_color),
            (p2, self.fill_color if p2 > 0.005 else self.track_color),
            (p3, self.track_color),
        ]
        for c, (frac, color) in zip(self.bar.controls, parts):
            exp = int(round(frac * 1000))
            c.expand = exp if exp > 0 else 1
            c.bgcolor = color

    async def _changed(self, e):
        self.value = float(e.control.value)
        self._paint(self.value)
        try:
            self.bar.update()
        except Exception:
            pass

        self._cancel()
        self._task = asyncio.create_task(
            self._fire(self.value, self.debounce_ms / 1000.0)
        )

    async def _ended(self, e):
        self._cancel()
        val = float(e.control.value)
        await self._fire(val, 0)
        if self.on_change_end:
            r = self.on_change_end(val)
            if inspect.isawaitable(r):
                await r

    async def _fire(self, val: float, delay: float):
        if delay > 0:
            await asyncio.sleep(delay)
        if self.on_change:
            r = self.on_change(val)
            if inspect.isawaitable(r):
                await r

    def _cancel(self):
        if self._task:
            self._task.cancel()
            self._task = None

    def set_value(self, v: float):
        self.value = float(v)
        self.slider.value = float(v)
        self._paint(float(v))
        try:
            self.update()
        except Exception:
            pass


class AdjustmentRow(ft.Container):
    """
    Complete row for an adjustment:
    [Title Label] -------- [Reset Button] [Value Pill]
    [CenterSlider]
    """

    def __init__(
        self,
        name: str,
        key: str,
        min_val: float = -100.0,
        max_val: float = 100.0,
        initial_value: float = 0.0,
        on_change: Optional[Callable[[str, float], None]] = None,
    ):
        super().__init__()
        self.key = key
        self.adj_name = name
        self.current_value = initial_value
        self.external_on_change = on_change

        self.val_text = ft.Text(
            self._format_value(initial_value),
            size=12,
            weight=ft.FontWeight.W_600,
            color=(
                ft.Colors.ORANGE_ACCENT_400
                if initial_value != 0
                else ft.Colors.WHITE_70
            ),
        )

        self.reset_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=16,
            icon_color=ft.Colors.WHITE_38,
            tooltip="Reset to 0",
            on_click=self._on_reset,
            width=28,
            height=28,
            padding=0,
        )

        self.slider = CenterSlider(
            min=min_val,
            max=max_val,
            value=initial_value,
            on_change=self._slider_changed,
        )

        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            name,
                            size=13,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.WHITE,
                        ),
                        ft.Row(
                            controls=[
                                self.reset_btn,
                                ft.Container(
                                    content=self.val_text,
                                    padding=ft.Padding.symmetric(
                                        horizontal=8, vertical=2
                                    ),
                                    bgcolor=ft.Colors.with_opacity(
                                        0.12, ft.Colors.WHITE
                                    ),
                                    border_radius=ft.BorderRadius.all(10),
                                    on_click=self._on_reset,
                                ),
                            ],
                            spacing=4,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.slider,
            ],
            spacing=2,
        )
        self.padding = ft.Padding.symmetric(horizontal=12, vertical=4)

    def _format_value(self, v: float) -> str:
        iv = int(round(v))
        if iv > 0:
            return f"+{iv}"
        return str(iv)

    def _slider_changed(self, val: float):
        self.current_value = val
        self.val_text.value = self._format_value(val)
        self.val_text.color = (
            ft.Colors.ORANGE_ACCENT_400 if int(round(val)) != 0 else ft.Colors.WHITE_70
        )
        try:
            self.val_text.update()
        except Exception:
            pass

        if self.external_on_change:
            self.external_on_change(self.key, val)

    def _on_reset(self, e):
        self.set_value(0.0)
        if self.external_on_change:
            self.external_on_change(self.key, 0.0)

    def set_value(self, val: float):
        self.current_value = val
        self.slider.set_value(val)
        self.val_text.value = self._format_value(val)
        self.val_text.color = (
            ft.Colors.ORANGE_ACCENT_400 if int(round(val)) != 0 else ft.Colors.WHITE_70
        )
        try:
            self.val_text.update()
        except Exception:
            pass
