import flet as ft
from app import ReColor


def home_view(page: ft.Page, app: ReColor) -> ft.View:
    async def open_editor(e):
        await page.push_route("/editor")

    async def create_project(e):
        await page.push_route("/create")

    loading = ft.ProgressRing(visible=True, width=20, height=20)

    async def open_project(e):
        p_name = e.control.title.value

        # Loading
        loading.visible = True
        lv.disabled = True
        page.update()

        app.project.open(p_name)
        print(f"Opened project '{p_name}'.")
        await page.push_route("/editor")

    lv = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)

    for project_name in app.projects_manager.list_projects():
        lv.controls.append(
            ft.ListTile(
                title=ft.Text(project_name),
                on_click=open_project,
            )
        )

    return ft.View(
        route="/",
        appbar=ft.AppBar(
            title=ft.Row(
                [
                    ft.Text("ReColor", weight=ft.FontWeight.BOLD),
                    loading,
                ]
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            actions=[
                ft.IconButton(ft.Icons.SEARCH),
                ft.IconButton(ft.Icons.ADD, on_click=create_project),
            ],
        ),
        controls=[ft.SafeArea(content=ft.Column(controls=[lv]))],
    )
