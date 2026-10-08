import flet as ft
from datetime import datetime

from app import ReColor


def create_view(page: ft.Page, app: ReColor) -> ft.View:
    async def go_back(e):
        await page.push_route("/")

    appbar = ft.AppBar(
        title=ft.Text("Create New Project", weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back),
    )

    async def on_project_named_field_change(e):
        v = e.control.value.strip()

        if v in app.projects_manager.list_projects():
            print(f"Project name '{v}' already exists.")
            e.control.helper = "Project name already exists."

        else:
            e.control.helper = f"{v}.rclr" if v else ""
            if v:
                create_project_btn.disabled = False

            else:
                create_project_btn.disabled = True

    async def on_choose_photo_click(e):
        files = await ft.FilePicker().pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.IMAGE,
        )

        print("Selected files:", files)
        if files:
            file = files[0]
            if file.name.lower().endswith((".png", ".jpg", ".jpeg")):
                project_name = project_name_field.value.strip()

                if project_name:
                    app.project.create(project_name, file.path)
                    app.project.save()
                    print(f"Project '{project_name}' created and saved.")
                    print(f"Current project set to '{app.project.name}'.")
                    await page.push_route("/editor")
                else:
                    print("Project name is empty.")
            else:
                print("Invalid file type. Please select a PNG or JPG image.")
        else:
            print("No file selected.")

    return ft.View(
        route="/create",
        appbar=appbar,
        controls=[
            ft.SafeArea(
                content=ft.Column(
                    controls=[
                        ft.Text("Create a new project here."),
                        project_name_field := ft.TextField(
                            label="Project Name",
                            on_change=on_project_named_field_change,
                            max_length=20,
                            filled=True,
                            border=ft.UnderlineInputBorder(),
                            suffix=".rclr",
                        ),
                        create_project_btn := ft.Button(
                            "Create Project",
                            icon=ft.Icons.ADD,
                            on_click=on_choose_photo_click,
                            disabled=True,
                        ),
                    ]
                )
            )
        ],
    )
