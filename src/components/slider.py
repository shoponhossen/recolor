# src\components\slider.py
import flet as ft
from typing import Callable, Optional
import asyncio, inspect

TRACK, FILL = ft.Colors.OUTLINE_VARIANT, ft.Colors.PRIMARY


@ft.control
class CenterSlider(ft.Stack):
    min: float = -100
    max: float = 100
    step: float = 1
    debounce_ms: int = 100
    value: float = 0
    on_change: Optional[Callable] = None
    on_change_start: Optional[Callable] = None
    on_change_end: Optional[Callable] = None

    def init(self):
        self._task = None

        self.height = 40
        self.bar = ft.Row([ft.Container(height=4) for _ in range(3)], spacing=0)
        self.slider = ft.Slider(
            min=self.min,
            max=self.max,
            value=self.value,
            divisions=round((self.max - self.min) / self.step),
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
        pos, mid = (v - self.min) / span, (0 - self.min) / span  # mid = zero point
        parts = [
            (min(pos, mid), TRACK),
            (abs(pos - mid), FILL),
            (1 - max(pos, mid), TRACK),
        ]
        for c, (frac, color) in zip(self.bar.controls, parts):
            c.expand, c.bgcolor = round(frac * 1000) or None, color

    async def _changed(self, e):
        self.value = e.control.value
        self._paint(self.value)  # visual updates instantly
        self.bar.update()
        self._cancel()
        self._task = asyncio.create_task(self._fire(e, self.debounce_ms / 1000))

    async def _ended(self, e):
        self._cancel()
        await self._fire(e, 0)  # release: apply the final value now
        if self.on_change_end:
            r = self.on_change_end(e)
            if inspect.isawaitable(r):
                await r

    async def _fire(self, e, delay):
        await asyncio.sleep(delay)
        if self.on_change:
            r = self.on_change(e)
            if inspect.isawaitable(r):
                await r

    def _cancel(self):
        if self._task:
            self._task.cancel()
            self._task = None

    def set_value(self, v):  # for resetting in code
        self.value = self.slider.value = v
        self._paint(v)
        self.update()
