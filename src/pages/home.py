import flet as ft
from app import ReColor


def home_view(page: ft.Page, app: ReColor) -> ft.View:
    async def create_project(e):
        await page.push_route("/create")

    async def open_project(e):
        p_name = e.control.title.value

        # Loading
        page.overlay.append(ft.ProgressBar())
        lv.disabled = True
        page.update()

        app.project.open(p_name)
        print(f"Opened project '{p_name}'.")
        await page.push_route("/editor")

    lv = ft.ListView(expand=True, spacing=10, auto_scroll=True)

    for project_name in app.projects_manager.list_projects():
        lv.controls.append(
            ft.ListTile(
                title=ft.Text(project_name),
                on_click=open_project,
            )
        )

    main_area = ft.SafeArea(
        content=ft.Column(
            [
                # Create Project Card Container
                ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(icon=ft.Icons.ADD, size=30),
                                    ft.Text("Wanna create a new project?"),
                                    ft.Text(
                                        "Create Project.",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.Padding.all(20),
                        ),
                    ),
                    on_click=create_project,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(height=10),
                ft.Text("Recent Projects", weight=ft.FontWeight.BOLD),
                ft.Column(
                    [lv],
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    return ft.View(
        route="/",
        appbar=ft.AppBar(
            title=ft.Text("ReColor", weight=ft.FontWeight.BOLD),
            actions=[
                ft.IconButton(ft.Icons.SEARCH),
                ft.IconButton(ft.Icons.ADD, on_click=create_project),
            ],
        ),
        controls=[main_area],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )
