import flet as ft
from app import ReColor
from utils import arr_to_bytes


def selector_view(page: ft.Page, app: ReColor) -> ft.View:
    ### Cleanup
    page.overlay.clear()

    # Debug
    pm = app.projects_manager
    # pm.load_project("Untitled")
    if pm.project is None:
        pm.load_project("Untitled2")

    # Handlers

    stroke: list[tuple[float, float]] = []

    def to_img(e):
        # widget coords -> image pixel coords (see note below)
        h, w = pm.project.image_array.shape[:2]
        return (e.local_position.x * w / img.width, e.local_position.y * h / img.height)

    def on_start(e):
        stroke.clear()
        stroke.append(to_img(e))
        print("start", stroke[0])

    def on_update(e):
        stroke.append(to_img(e))
        print("move", stroke[-1])

    def on_end(e):
        # end event carries no position, so the last path point is the end
        print("end", stroke[-1], "| points:", len(stroke))
        # hand `stroke` to the active tool here

    img = ft.Image(
        src=arr_to_bytes(pm.project.image_array),
        width=360,
        height=480,
        fit=ft.BoxFit.FILL,  # ft.ImageFit.FILL on older Flet
    )

    canvas = ft.GestureDetector(
        content=img,
        on_pan_start=on_start,
        on_pan_update=on_update,
        on_pan_end=on_end,
        on_tap_down=lambda e: print("tap down", to_img(e)),
        on_tap_up=lambda e: print("tap up", to_img(e)),
        drag_interval=10,  # ms throttle on pan_update
    )

    return ft.View(
        route="/editor/selector",
        appbar=ft.AppBar(
            title=ft.Text(f"{pm.project.name} Selector"),
            actions=[
                ft.IconButton(ft.Icons.SAVE, on_click=lambda e: pm.project.save())
            ],
        ),
        controls=[ft.SafeArea(content=ft.Column([canvas]))],
    )
