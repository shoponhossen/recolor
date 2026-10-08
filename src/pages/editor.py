import flet as ft
from app import ReColor
from utils import arr_to_bytes


def editor_view(page: ft.Page, app: ReColor) -> ft.View:
    if app.project.name is None or app.project.im_arr is None:
        # page.navigate("/create")
        app.project.create("Untitled", r"D:\Projects\recolor\shopon_hossen_about.jpeg")


    appbar = ft.AppBar(
        title=ft.Text(f"{app.project.name}", ),
        actions=[
            ft.IconButton(ft.Icons.SAVE, on_click=lambda e: app.project.save()),
        ]
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
