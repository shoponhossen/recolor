import flet as ft
from app import ReColor
from colors import C, BORDER

from pages.home import home_view
from pages.editor import editor_view
from pages.selector import selector_view
from pages.create import create_view


def main(page: ft.Page):
    # App Configuration & Theme
    page.title = "ReColor - Mobile Color Grading"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0F17"

    # Define App State
    app = ReColor(page)

    def route_change(e=None):
        page.views.clear()

        # Root view is always Home
        page.views.append(home_view(page, app))

        if page.route == "/editor":
            page.views.append(editor_view(page, app))
        elif page.route in ("/editor/selector", "/create/selector"):
            page.views.append(selector_view(page, app))
        elif page.route == "/create":
            page.views.append(create_view(page, app))

        page.update()

    async def view_pop(e):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            await page.push_route(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
