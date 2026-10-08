import flet as ft
from app import ReColor

from pages.home import home_view
from pages.editor import editor_view
from pages.create import create_view


def main(page: ft.Page):
    page.title = "ReColor"

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
