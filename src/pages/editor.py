import flet as ft
from app import ReColor
from utils import arr_to_bytes


def editor_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()

    if app.project.name is None or app.project.im_arr is None:
        # DEBUG
        # page.navigate("/create")
        app.project.create("Untitled", r"D:\Projects\recolor\default.jpg")

    def menu_selected(e: ft.Event[ft.PopupMenuItem]):
        e.control.checked = not e.control.checked

    appbar = ft.AppBar(
        title=ft.Text(
            f"{app.project.name}",
        ),
        actions=[
            ft.IconButton(ft.Icons.SAVE, on_click=lambda e: app.project.save()),
            ft.PopupMenuButton(
                key="popup",
                items=[
                    ft.PopupMenuItem(),
                    ft.PopupMenuItem(
                        content="Checked item",
                        checked=False,
                        on_click=menu_selected,
                    ),
                ],
            ),
        ],
    )

    return ft.View(
        route="/editor",
        appbar=appbar,
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=arr_to_bytes(app.project.im_arr),
                        ),
                    ]
                )
            )
        ],
    )
