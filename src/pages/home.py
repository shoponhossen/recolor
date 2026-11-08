import flet as ft
from app import ReColor
from pathlib import Path
import datetime


def home_view(page: ft.Page, app: ReColor) -> ft.View:
    page.overlay.clear()
    pm = app.projects_manager

    async def create_project(e):
        await page.push_route("/create")

    async def open_project(project_name: str):
        # Loading indicator
        loading_indicator = ft.ProgressBar()
        page.overlay.append(loading_indicator)
        page.update()

        try:
            pm.load_project(project_name)
            await page.push_route("/editor")
        except Exception as ex:
            print(f"Error opening project {project_name}: {ex}")
            if loading_indicator in page.overlay:
                page.overlay.remove(loading_indicator)
                page.update()

            dialog = ft.AlertDialog(
                title=ft.Text("Cannot Open Project"),
                content=ft.Text(f"Failed to load project file:\n{ex}"),
                actions=[ft.TextButton("OK", on_click=lambda ev: page.pop_dialog())],
            )
            page.show_dialog(dialog)

    async def open_demo_project(e):
        default_path = Path(r"D:\Projects\recolor\default.jpg").resolve()
        demo_name = "Portrait_Demo"
        pm.create_project(demo_name, str(default_path))
        await page.push_route("/editor")

    def delete_project_prompt(project_name: str):
        def do_delete(ev):
            page.pop_dialog()
            pm.delete_project(project_name)
            rebuild_projects_list()

        dialog = ft.AlertDialog(
            title=ft.Text("Delete Project?"),
            content=ft.Text(f"Are you sure you want to delete '{project_name}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                ft.TextButton("Delete", on_click=do_delete),
            ],
        )
        page.show_dialog(dialog)

    projects_container = ft.Column(spacing=10)

    def rebuild_projects_list():
        projects_container.controls.clear()
        project_paths = pm.list_project_paths()

        if not project_paths:
            projects_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.PHOTO_LIBRARY_OUTLINED, size=48, color=ft.Colors.WHITE_24),
                            ft.Text("No projects yet", size=15, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE_54),
                            ft.Text("Tap 'New Project' or 'Quick Demo' above to begin", size=12, color=ft.Colors.WHITE_38),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=ft.Padding.symmetric(vertical=30),
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for p in project_paths:
                p_name = p.stem
                mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%b %d, %Y · %H:%M")
                size_kb = round(p.stat().st_size / 1024, 1)

                card = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.IMAGE, size=24, color=ft.Colors.ORANGE_ACCENT_400),
                                width=48,
                                height=48,
                                bgcolor="#1E2536",
                                border_radius=ft.BorderRadius.all(8),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(p_name, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text(f"{mtime} ({size_kb} KB)", size=11, color=ft.Colors.WHITE_54),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                icon_color=ft.Colors.RED_ACCENT_200,
                                tooltip="Delete project",
                                on_click=lambda ev, name=p_name: delete_project_prompt(name),
                            ),
                        ],
                        spacing=12,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor="#141824",
                    padding=ft.Padding.all(12),
                    border_radius=ft.BorderRadius.all(12),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    on_click=lambda ev, name=p_name: page.run_task(open_project, name),
                )
                projects_container.controls.append(card)

        try:
            projects_container.update()
        except Exception:
            pass

    rebuild_projects_list()

    # Top Hero Actions
    hero_banner = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PALETTE, size=32, color=ft.Colors.ORANGE_ACCENT_400),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text("ReColor", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        ft.Container(
                                            content=ft.Text("PRO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                                            bgcolor=ft.Colors.ORANGE_ACCENT_400,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=ft.BorderRadius.all(4),
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text("Mobile Color Grading & Layer Masking", size=12, color=ft.Colors.WHITE_70),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Container(height=10),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE, size=24, color=ft.Colors.WHITE),
                                    ft.Text("New Project", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text("Grade your photo", size=11, color=ft.Colors.WHITE_70),
                                ],
                                spacing=2,
                            ),
                            bgcolor=ft.Colors.ORANGE_ACCENT_700,
                            padding=ft.Padding.all(14),
                            border_radius=ft.BorderRadius.all(12),
                            expand=True,
                            on_click=create_project,
                        ),
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME, size=24, color=ft.Colors.ORANGE_ACCENT_400),
                                    ft.Text("Quick Demo", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text("Sample portrait", size=11, color=ft.Colors.WHITE_70),
                                ],
                                spacing=2,
                            ),
                            bgcolor="#1E2536",
                            padding=ft.Padding.all(14),
                            border_radius=ft.BorderRadius.all(12),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ORANGE_ACCENT_400)),
                            expand=True,
                            on_click=open_demo_project,
                        ),
                    ],
                    spacing=10,
                ),
            ]
        ),
        padding=ft.Padding.all(16),
        bgcolor="#111521",
        border_radius=ft.BorderRadius.all(16),
    )

    return ft.View(
        route="/",
        bgcolor="#0B0F17",
        appbar=ft.AppBar(
            bgcolor="#111521",
            title=ft.Text("ReColor Studio", size=18, weight=ft.FontWeight.BOLD),
            actions=[
                ft.IconButton(ft.Icons.ADD, tooltip="New Project", on_click=create_project),
            ],
        ),
        controls=[
            ft.SafeArea(
                content=ft.Container(
                    padding=ft.Padding.all(16),
                    content=ft.Column(
                        controls=[
                            hero_banner,
                            ft.Container(height=12),
                            ft.Row(
                                controls=[
                                    ft.Text("Recent Projects", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.IconButton(
                                        icon=ft.Icons.REFRESH,
                                        icon_size=16,
                                        icon_color=ft.Colors.WHITE_54,
                                        tooltip="Refresh list",
                                        on_click=lambda e: rebuild_projects_list(),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Column(
                                controls=[projects_container],
                                scroll=ft.ScrollMode.ALWAYS,
                                expand=True,
                            ),
                        ],
                        expand=True,
                        spacing=4,
                    ),
                ),
                expand=True,
            )
        ],
    )
