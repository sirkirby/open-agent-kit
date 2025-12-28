"""Remove command for uninstalling open-agent-kit from a project."""

from pathlib import Path

import typer

from open_agent_kit.config.paths import (
    CURSOR_SETTINGS_FILE,
    OAK_DIR,
    VSCODE_SETTINGS_FILE,
)
from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.executor import build_remove_pipeline
from open_agent_kit.services.skill_service import SkillService
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    StepTracker,
    print_error,
    print_header,
    print_info,
    print_panel,
)


def remove_command(
    force: bool = False,
    keep_ide_settings: bool = False,
) -> None:
    """Remove open-agent-kit managed assets from the project.

    Uses state tracking to intelligently remove only what oak created:
    - Files we created (hash matches) -> remove with confirmation
    - Files we modified (existed before) -> inform user to manually clean up
    - Directories we created -> remove if empty after file cleanup

    Preserves:
    - oak/ directory (user-generated content: constitution, RFCs, plans)
    - Files modified by user after oak created them

    Args:
        force: Skip confirmation prompt
        keep_ide_settings: Keep IDE settings files (.vscode/settings.json, etc.)
    """
    project_root = Path.cwd()
    oak_dir = project_root / OAK_DIR

    # Check if oak is initialized
    if not oak_dir.exists():
        print_error("open-agent-kit is not initialized in this project.")
        print_info("Nothing to remove.")
        raise typer.Exit(code=1)

    print_header("Remove open-agent-kit")

    # Gather information for preview (before pipeline runs)
    preview_data = _gather_preview_data(project_root, keep_ide_settings)

    # Display preview of what will be removed
    _display_removal_preview(preview_data, keep_ide_settings, project_root)

    # Confirm removal
    if not force:
        print_info("")
        confirm = typer.confirm("Are you sure you want to remove open-agent-kit?")
        if not confirm:
            print_info("\nRemoval cancelled.")
            raise typer.Exit(code=0)

    # Build pipeline context
    context = PipelineContext(
        project_root=project_root,
        flow_type=FlowType.REMOVE,
    )
    # Store removal options for stages
    context.set_result(
        "removal_options",
        {
            "keep_ide_settings": keep_ide_settings,
        },
    )

    # Build and execute pipeline
    pipeline = build_remove_pipeline().build()
    step_count = pipeline.get_stage_count(context)
    tracker = StepTracker(step_count)

    print_info("")  # Blank line before execution

    result = pipeline.execute(context, tracker)

    # Display results
    if result.success:
        _display_removal_summary(context, preview_data)
    else:
        for stage_name, error in result.stages_failed:
            print_error(f"Stage '{stage_name}' failed: {error}")
        raise typer.Exit(code=1)


def _gather_preview_data(project_root: Path, keep_ide_settings: bool) -> dict:
    """Gather data needed for preview display.

    Args:
        project_root: Project root directory
        keep_ide_settings: Whether to keep IDE settings

    Returns:
        Dictionary with preview data
    """
    state_service = StateService(project_root)
    managed_assets = state_service.get_managed_assets()

    # Categorize files
    files_to_remove: list[tuple[str, str]] = []
    files_modified_by_user: list[tuple[str, str]] = []
    files_to_inform_user: list[tuple[str, str]] = []

    # Process created files
    for created_file in managed_assets.created_files:
        file_path = project_root / created_file.path
        if file_path.exists():
            if state_service.is_file_unchanged(file_path):
                files_to_remove.append((created_file.path, "Created by oak (unchanged)"))
            else:
                files_modified_by_user.append(
                    (created_file.path, "File was modified after oak created it")
                )

    # Process modified files
    for modified_file in managed_assets.modified_files:
        file_path = project_root / modified_file.path
        if file_path.exists():
            files_to_inform_user.append((modified_file.path, modified_file.marker))

    # IDE settings
    ide_settings_to_remove: list[str] = []
    if not keep_ide_settings:
        if (project_root / VSCODE_SETTINGS_FILE).exists():
            ide_settings_to_remove.append(VSCODE_SETTINGS_FILE)
        if (project_root / CURSOR_SETTINGS_FILE).exists():
            ide_settings_to_remove.append(CURSOR_SETTINGS_FILE)

    # User content
    user_content_dir = project_root / "oak"
    has_user_content = user_content_dir.exists() and any(user_content_dir.iterdir())

    # Installed skills
    installed_skills: list[str] = []
    try:
        skill_service = SkillService(project_root)
        installed_skills = skill_service.list_installed_skills()
    except Exception:
        pass

    return {
        "files_to_remove": files_to_remove,
        "files_modified_by_user": files_modified_by_user,
        "files_to_inform_user": files_to_inform_user,
        "ide_settings_to_remove": ide_settings_to_remove,
        "installed_skills": installed_skills,
        "has_user_content": has_user_content,
    }


def _display_removal_preview(
    preview_data: dict,
    keep_ide_settings: bool,
    project_root: Path,
) -> None:
    """Display preview of what will be removed.

    Args:
        preview_data: Data gathered for preview
        keep_ide_settings: Whether to keep IDE settings
        project_root: Project root directory
    """
    files_to_remove = preview_data["files_to_remove"]
    files_modified_by_user = preview_data["files_modified_by_user"]
    files_to_inform_user = preview_data["files_to_inform_user"]
    ide_settings_to_remove = preview_data["ide_settings_to_remove"]
    installed_skills = preview_data["installed_skills"]
    has_user_content = preview_data["has_user_content"]

    # Display files to remove
    if files_to_remove:
        print_info("\n[bold]Files to remove:[/bold]\n")
        for path, description in files_to_remove:
            print_info(f"  [red]-[/red] {path} ({description})")

    # Display files modified by user (won't remove)
    if files_modified_by_user:
        print_info("\n[yellow]Files modified by user (will NOT remove):[/yellow]\n")
        for path, reason in files_modified_by_user:
            print_info(f"  [yellow]![/yellow] {path}")
            print_info(f"      {reason}")

    # Display files user needs to manually clean up
    if files_to_inform_user:
        print_info("\n[cyan]Files with oak modifications (manual cleanup needed):[/cyan]\n")
        for path, marker in files_to_inform_user:
            print_info(f"  [cyan]i[/cyan] {path}")
            print_info(f"      Look for section: '{marker}'")

    # Always remove .oak directory
    print_info("\n[bold]Configuration to remove:[/bold]\n")
    print_info(f"  [red]-[/red] {OAK_DIR}/ (oak configuration)")

    # Display installed skills that will be removed
    if installed_skills:
        print_info("\n[bold]Skills to remove:[/bold]\n")
        for skill_name in installed_skills:
            print_info(f"  [red]-[/red] {skill_name}")

    # Display IDE settings to remove
    if ide_settings_to_remove:
        print_info("\n[bold]IDE settings to remove:[/bold]\n")
        for settings_path in ide_settings_to_remove:
            print_info(f"  [red]-[/red] {settings_path}")

    # Show what will be preserved
    if has_user_content:
        print_info("\n[green]Preserved (user content):[/green]\n")
        print_info("  [green]+[/green] oak/ (constitution, RFCs, plans)")

    if keep_ide_settings:
        print_info("\n[cyan]Preserved (--keep-ide-settings):[/cyan]")
        if (project_root / VSCODE_SETTINGS_FILE).exists():
            print_info(f"  [cyan]+[/cyan] {VSCODE_SETTINGS_FILE}")
        if (project_root / CURSOR_SETTINGS_FILE).exists():
            print_info(f"  [cyan]+[/cyan] {CURSOR_SETTINGS_FILE}")


def _display_removal_summary(context: PipelineContext, preview_data: dict) -> None:
    """Display summary after removal.

    Args:
        context: Pipeline context with results
        preview_data: Original preview data
    """
    files_modified_by_user = preview_data["files_modified_by_user"]
    files_to_inform_user = preview_data["files_to_inform_user"]
    has_user_content = preview_data["has_user_content"]

    # Gather counts from stage results
    files_result = context.get_result("remove_created_files", {})
    files_removed = files_result.get("removed_count", 0)

    skills_result = context.get_result("remove_skills", {})
    skills_removed = skills_result.get("skills_removed", 0)

    ide_result = context.get_result("remove_ide_settings_removal", {})
    ide_removed = len(ide_result.get("removed", []))

    oak_result = context.get_result("remove_oak_dir", {})
    oak_removed = 1 if oak_result.get("removed") else 0

    total_removed = files_removed + skills_removed + ide_removed + oak_removed

    message_parts = [f"[bold green]Removed {total_removed} open-agent-kit asset(s)[/bold green]\n"]

    if has_user_content:
        message_parts.append(
            "\n[cyan]Your user content in oak/ has been preserved:[/cyan]\n"
            "  - Constitution and amendments\n"
            "  - RFCs and documentation\n"
            "  - Plans and research\n"
            "\nYou can safely delete the oak/ directory manually if desired."
        )

    if files_modified_by_user:
        message_parts.append(
            f"\n\n[yellow]Note:[/yellow] {len(files_modified_by_user)} file(s) were not "
            "removed because you modified them after oak created them.\n"
            "Review and delete manually if no longer needed."
        )

    if files_to_inform_user:
        message_parts.append(
            f"\n\n[cyan]Manual cleanup needed:[/cyan] {len(files_to_inform_user)} file(s) "
            "existed before oak and were modified.\n"
            "Look for the '## Project Constitution' section and remove it manually."
        )

    message_parts.append("\n\n[dim]To reinstall, run: oak init[/dim]")

    print_panel(
        "\n".join(message_parts),
        title="Removal Complete",
        style="green",
    )
