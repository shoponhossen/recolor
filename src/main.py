import flet as ft
from app import ReColor
from colors import *

from pages.home import home_view
from pages.editor import editor_view
from pages.create import create_view


def main(page: ft.Page):
    # App Theme
    page.title = "ReColor"

    # page.theme_mode = ft.ThemeMode.DARK
    # page.bgcolor = C.PRIMARY

    # page.dark_theme = ft.Theme(
    #     color_scheme=ft.ColorScheme(
    #         primary=C.ACCENT,
    #         on_primary=C.WHITE,
    #         secondary=C.ACCENT,
    #         on_secondary=C.WHITE,
    #         error=C.ERROR,
    #         on_error=C.WHITE,
    #         outline=BORDER,
    #         outline_variant=BORDER,
    #     ),
    #     page_transitions=ft.PageTransitionsTheme(android=ft.PageTransitionTheme.ZOOM),
    #     card_theme=ft.CardTheme(
    #         color=C.SECONDARY,
    #         shape=ft.RoundedRectangleBorder(
    #             radius=12,
    #             side=ft.BorderSide(width=1, color=BORDER),
    #         ),
    #     ),
    #     scaffold_bgcolor=C.PRIMARY,
    #     dialog_theme=ft.DialogTheme(
    #         bgcolor=C.TERTIARY,
    #     ),
    # )

    # Define the App
    app = ReColor(page)
    print("Projects directory:", app.projects_manager.projects_dir)

    print("Initial route:", page.route)

    def route_change():
        print("Route change:", page.route)
        page.views.clear()

        page.views.append(home_view(page, app))

        if page.route == "/editor":
            page.views.append(editor_view(page, app))

        if page.route == "/create":
            page.views.append(create_view(page, app))

        page.update()

    async def view_pop(e):
        if e.view is not None:
            print("View pop:", e.view)
            page.views.remove(e.view)
            top_view = page.views[-1]
            await page.push_route(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
