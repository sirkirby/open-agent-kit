"""Initialize command for setting up open-agent-kit in a project."""

from pathlib import Path
from typing import cast

import typer

from open_agent_kit.config.messages import (
    ERROR_MESSAGES,
    FEATURE_MESSAGES,
    INFO_MESSAGES,
    INIT_HELP_TEXT,
    NEXT_STEPS_INIT,
    PROJECT_URL,
    USAGE_EXAMPLES,
)
from open_agent_kit.config.paths import OAK_DIR, TEMPLATES_DIR
from open_agent_kit.constants import (
    DEFAULT_FEATURES,
    FEATURE_CONFIG,
    FEATURE_DISPLAY_NAMES,
    IDE_DISPLAY_NAMES,
    SUPPORTED_FEATURES,
    SUPPORTED_IDES,
)
from open_agent_kit.models.config import AgentCapabilitiesConfig
from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState
from open_agent_kit.pipeline.executor import build_init_pipeline
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import (
    SelectOption,
    StepTracker,
    dir_exists,
    multi_select,
    print_error,
    print_header,
    print_info,
    print_panel,
    print_warning,
)


def _build_agent_capabilities(
    agents: list[str], agent_service: AgentService
) -> dict[str, AgentCapabilitiesConfig]:
    """Build agent_capabilities config from agent manifests.

    Populates config with manifest defaults so users can see and override them.

    Args:
        agents: List of agent type names
        agent_service: AgentService instance for loading manifests

    Returns:
        Dictionary mapping agent names to AgentCapabilitiesConfig
    """
    capabilities: dict[str, AgentCapabilitiesConfig] = {}
    for agent_type in agents:
        try:
            caps_dict = agent_service.get_capabilities_config(agent_type)
            capabilities[agent_type] = AgentCapabilitiesConfig(**caps_dict)
        except ValueError:
            # Unknown agent, skip
            pass
    return capabilities


def init_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-initialization even if .oak directory exists",
    ),
    agent: list[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Agent(s) to use (can specify multiple times). Options: claude, copilot, codex, cursor, gemini, windsurf",
    ),
    ide: list[str] = typer.Option(
        None,
        "--ide",
        help="IDE(s) to configure (can specify multiple times). Options: vscode, cursor, none",
    ),
    feature: list[str] = typer.Option(
        None,
        "--feature",
        help="Feature(s) to install (can specify multiple times). Options: constitution, rfc, issues, none",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Skip interactive prompts and use defaults",
    ),
) -> None:
    """Initialize open-agent-kit in the current project.

    Creates the .oak directory structure with templates, configuration,
    agent-specific command directories, and IDE settings.
    """
    project_root = Path.cwd()
    oak_dir = project_root / OAK_DIR

    # Detect if already initialized
    is_existing = dir_exists(oak_dir)

    # Determine flow type
    if force:
        flow_type = FlowType.FORCE_REINIT
    elif is_existing:
        flow_type = FlowType.UPDATE
    else:
        flow_type = FlowType.FRESH_INIT

    # Display appropriate header based on flow type
    if flow_type == FlowType.UPDATE:
        if agent:
            print_header("Update open-agent-kit Configuration")
            print_info(f"{INFO_MESSAGES['adding_agents']}\n")
        elif no_interactive:
            # Can't proceed without input in non-interactive mode
            examples = INIT_HELP_TEXT["examples"].format(
                init_agent=USAGE_EXAMPLES["init_agent"],
                init_multi_agent=USAGE_EXAMPLES["init_multi_agent"],
                init_force=USAGE_EXAMPLES["init_force"],
            )
            print_error(
                f"{ERROR_MESSAGES['oak_dir_exists'].format(oak_dir=oak_dir)}\n"
                f"{INIT_HELP_TEXT['no_interactive']}\n\n"
                f"{examples}"
            )
            raise typer.Exit(code=1)
        else:
            print_header("Update open-agent-kit Configuration")
            print_info(f"{INFO_MESSAGES['add_more_agents']}\n")
    elif flow_type == FlowType.FRESH_INIT:
        print_header("Initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['setting_up']}\n")
    else:  # FORCE_REINIT
        print_header("Re-initialize open-agent-kit")
        print_info(f"{INFO_MESSAGES['force_reinit']}\n")

    # Load existing configuration if applicable
    config_service = ConfigService(project_root)
    existing_agents: list[str] = []
    existing_ides: list[str] = []
    existing_features: list[str] = []

    if is_existing:
        existing_agents = config_service.get_agents()
        existing_ides = config_service.get_ides()
        config = config_service.load_config()
        existing_features = config.features.enabled

    # Gather selections (CLI args or interactive)
    selected_agents = _gather_agent_selection(
        agent, no_interactive, existing_agents if is_existing else None
    )
    selected_ides = _gather_ide_selection(
        ide, no_interactive, existing_ides if is_existing else None
    )
    selected_features = _gather_feature_selection(
        feature, no_interactive, is_existing, existing_features
    )

    # Check for no changes in update flow
    if flow_type == FlowType.UPDATE:
        agents_changed = set(selected_agents) != set(existing_agents)
        ides_changed = set(selected_ides) != set(existing_ides)
        features_changed = set(selected_features) != set(existing_features)

        if not agents_changed and not ides_changed and not features_changed:
            print_info("\nNo changes to configuration. Current setup:")
            if existing_agents:
                print_info(f"  Agents: {', '.join(existing_agents)}")
            if existing_ides:
                print_info(f"  IDEs: {', '.join(existing_ides)}")
            if existing_features:
                print_info(f"  Features: {', '.join(existing_features)}")
            return

    # Build pipeline context
    context = PipelineContext(
        project_root=project_root,
        flow_type=flow_type,
        force=force,
        interactive=not no_interactive,
        selections=SelectionState(
            agents=selected_agents,
            ides=selected_ides,
            features=selected_features,
            previous_agents=existing_agents,
            previous_ides=existing_ides,
            previous_features=existing_features,
        ),
    )

    # Build and execute pipeline
    pipeline = build_init_pipeline().build()
    step_count = pipeline.get_stage_count(context)
    tracker = StepTracker(step_count)

    result = pipeline.execute(context, tracker)

    # Handle result
    if result.success:
        if flow_type == FlowType.UPDATE:
            tracker.finish("open-agent-kit configuration updated successfully!")
            _display_update_message(existing_agents, selected_agents, existing_ides, selected_ides)
        else:
            tracker.finish("open-agent-kit initialized successfully!")
            _display_next_steps(selected_agents, selected_ides)

        # Display any hook information
        _display_hook_results(context)
    else:
        # Pipeline failed on critical stage
        for stage_name, error in result.stages_failed:
            print_error(f"Stage '{stage_name}' failed: {error}")
        raise typer.Exit(code=1)


def _gather_agent_selection(
    agent: list[str] | None,
    no_interactive: bool,
    existing_agents: list[str] | None,
) -> list[str]:
    """Gather agent selection from CLI args or interactive prompt.

    Args:
        agent: CLI-provided agents
        no_interactive: Whether to skip interactive prompts
        existing_agents: Previously configured agents (for pre-selection)

    Returns:
        List of selected agent names
    """
    if agent:
        # Validate provided agents using manifests
        agent_service = AgentService()
        available_agents = agent_service.list_available_agents()

        for a in agent:
            if a.lower() not in available_agents:
                print_error(ERROR_MESSAGES["invalid_agent"].format(agent=a))
                print_info(
                    INFO_MESSAGES["supported_agents_list"].format(
                        agents=", ".join(sorted(available_agents))
                    )
                )
                raise typer.Exit(code=1)

        return [a.lower() for a in agent]
    elif not no_interactive:
        return _interactive_agent_selection(existing_agents)
    else:
        return []


def _gather_ide_selection(
    ide: list[str] | None,
    no_interactive: bool,
    existing_ides: list[str] | None,
) -> list[str]:
    """Gather IDE selection from CLI args or interactive prompt.

    Args:
        ide: CLI-provided IDEs
        no_interactive: Whether to skip interactive prompts
        existing_ides: Previously configured IDEs (for pre-selection)

    Returns:
        List of selected IDE names
    """
    if ide and isinstance(ide, list) and len(ide) > 0:
        # Validate provided IDEs
        for i in ide:
            if i.lower() not in SUPPORTED_IDES:
                print_error(f"Invalid IDE: {i}")
                print_info(f"Supported IDEs: {', '.join(SUPPORTED_IDES)}")
                raise typer.Exit(code=1)

        # Convert to lowercase and filter out 'none'
        selected_ides = [i.lower() for i in ide if i.lower() != "none"]

        # Validate: 'none' cannot be combined with other IDEs
        if len(ide) != len(selected_ides) and len(selected_ides) > 0:
            print_error("Cannot specify 'none' with other IDEs")
            raise typer.Exit(code=1)

        return selected_ides
    elif not no_interactive:
        return _interactive_ide_selection(existing_ides)
    else:
        return []


def _gather_feature_selection(
    feature: list[str] | None,
    no_interactive: bool,
    is_existing: bool,
    existing_features: list[str],
) -> list[str]:
    """Gather feature selection from CLI args or interactive prompt.

    Args:
        feature: CLI-provided features
        no_interactive: Whether to skip interactive prompts
        is_existing: Whether this is an existing installation
        existing_features: Previously installed features

    Returns:
        List of selected feature names
    """
    if feature and isinstance(feature, list) and len(feature) > 0:
        # Validate provided features
        for f in feature:
            if f.lower() not in SUPPORTED_FEATURES and f.lower() != "none":
                print_error(f"Invalid feature: {f}")
                print_info(f"Supported features: {', '.join(SUPPORTED_FEATURES)}")
                raise typer.Exit(code=1)

        # Convert to lowercase and filter out 'none'
        selected_features = [f.lower() for f in feature if f.lower() != "none"]

        # Handle 'none' with others
        if (
            isinstance(feature, list)
            and len(feature) != len(selected_features)
            and len(selected_features) > 0
        ):
            print_error("Cannot specify 'none' with other features")
            raise typer.Exit(code=1)

        return selected_features
    elif not no_interactive:
        return _interactive_feature_selection(existing_features if is_existing else None)
    else:
        # Non-interactive mode - use defaults for new installs, preserve existing for updates
        if is_existing:
            return existing_features
        else:
            return list(DEFAULT_FEATURES)


def _display_hook_results(context: PipelineContext) -> None:
    """Display useful information from hook stage results.

    Args:
        context: Pipeline context with stage results
    """
    # Check for agent hook results
    hook_result = context.get_result("trigger_agents_changed")
    if hook_result:
        hook_info = hook_result.get("hook_info", [])
        for info in hook_info:
            print_info(f"  {info}")


def _interactive_agent_selection(existing_agents: list[str] | None = None) -> list[str]:
    """Interactive agent selection with checkboxes (multi-select).

    Args:
        existing_agents: List of currently configured agents (will be pre-selected)

    Returns:
        List of selected agent names
    """
    if existing_agents:
        print_header("Update AI Agents")
        print_info("Current agents are pre-selected. Check/uncheck to modify configuration.\n")
    else:
        print_header("Select AI Agents")
        print_info(f"{INFO_MESSAGES['select_agents_prompt']}\n")

    existing_agents = existing_agents or []

    # Normalize existing agents to lowercase for comparison
    existing_agents_lower = [a.lower() for a in existing_agents]

    options = []
    default_selections = []

    # Use AgentService to get available agents and their display names
    agent_service = AgentService()
    available_agents = agent_service.list_available_agents()

    # Add available agents from manifests
    for agent_name in available_agents:
        try:
            manifest = agent_service.get_agent_manifest(agent_name)
            display_name = manifest.display_name
            options.append(
                SelectOption(
                    value=agent_name,
                    label=display_name,
                    description=f"Use {display_name} for AI assistance",
                )
            )
            # Pre-select if this agent is already configured
            if agent_name.lower() in existing_agents_lower:
                default_selections.append(agent_name)
        except ValueError:
            continue

    selected = multi_select(
        options,
        "Which agents would you like to use? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=1,  # At least one agent is required
    )

    return selected


def _interactive_ide_selection(existing_ides: list[str] | None = None) -> list[str]:
    """Interactive IDE selection with checkboxes (multi-select).

    Args:
        existing_ides: List of currently configured IDEs (will be pre-selected)

    Returns:
        List of selected IDE names (empty if "none" selected)
    """
    if existing_ides:
        print_header("Update IDEs")
        print_info("Current IDEs are pre-selected. Check/uncheck to modify configuration.\n")
    else:
        print_header("Select IDEs")
        print_info("Choose which IDEs you'd like to configure with auto-approval settings.\n")

    existing_ides = existing_ides or []

    # Normalize existing IDEs to lowercase for comparison
    existing_ides_lower = [i.lower() for i in existing_ides]

    options = []
    default_selections = []

    for ide_name in SUPPORTED_IDES:
        if ide_name == "none":
            options.append(
                SelectOption(
                    value="none",
                    label="None (Skip IDE configuration)",
                    description="Don't install IDE settings",
                )
            )
            # Don't auto-select "none"
        else:
            display_name = IDE_DISPLAY_NAMES.get(ide_name, ide_name.capitalize())
            options.append(
                SelectOption(
                    value=ide_name,
                    label=display_name,
                    description=f"Configure {display_name} with auto-approval settings",
                )
            )
            # Pre-select if this IDE is already configured
            if ide_name.lower() in existing_ides_lower:
                default_selections.append(ide_name)

    selected = multi_select(
        options,
        "Which IDEs would you like to configure? (Space to select, Enter to confirm)",
        defaults=default_selections,
        min_selections=0,
    )

    # Filter out 'none' - if 'none' is selected with others, remove 'none'
    if "none" in selected and len(selected) > 1:
        selected = [s for s in selected if s != "none"]
    elif "none" in selected:
        return []

    return selected


def _display_next_steps(agents: list[str], ides: list[str]) -> None:
    """Display next steps after initialization.

    Args:
        agents: List of selected agent names
        ides: List of selected IDE names
    """
    from open_agent_kit.config.paths import CONFIG_FILE

    next_steps_text = NEXT_STEPS_INIT.format(
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
    )
    print_panel(
        next_steps_text,
        title="Getting Started",
        style="green",
    )

    # Display Agent Commands panel if agents were selected
    if agents:
        agent_service = AgentService()
        agent_info_lines = []
        for agent in agents:
            try:
                manifest = agent_service.get_agent_manifest(agent.lower())
                folder = manifest.installation.folder
                commands_subfolder = manifest.installation.commands_subfolder
                display_name = manifest.display_name
                agent_info_lines.append(
                    f"  • [cyan]{display_name}[/cyan]: {folder}{commands_subfolder}/"
                )
            except ValueError:
                agent_info_lines.append(f"  • [cyan]{agent.capitalize()}[/cyan]")

        agent_list = "\n".join(agent_info_lines)

        print_panel(
            f"[bold green]Agent Commands Installed[/bold green]\n\n"
            f"Commands have been installed for {len(agents)} agent(s):\n\n"
            f"{agent_list}\n\n"
            f"All commands start with [cyan]/oak.[/cyan] in your AI assistant.\n"
            f"Examples: [dim]/oak.rfc-create, /oak.constitution-create[/dim]\n\n"
            f"Type [cyan]/oak[/cyan] in your AI assistant to discover available commands!",
            title="Ready to Use",
            style="green",
        )

    # Display IDE Settings panel if IDEs were selected
    if ides:
        ide_info_lines = []
        for ide in ides:
            ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
            settings_file = f".{ide}/settings.json"
            ide_info_lines.append(f"  • [cyan]{ide_name}[/cyan]: {settings_file}")

        ide_list = "\n".join(ide_info_lines)

        print_panel(
            f"[bold green]IDE Settings Configured[/bold green]\n\n"
            f"Auto-approval settings have been installed for {len(ides)} IDE(s):\n\n"
            f"{ide_list}\n\n"
            f"Your IDE will now auto-approve [cyan]oak[/cyan] commands.\n"
            f"Prompt files are also recommended automatically in chat!",
            title="Ready to Use",
            style="green",
        )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _display_additions_message(agents: list[str], ides: list[str]) -> None:
    """Display message after adding agents/IDEs to existing installation.

    Args:
        agents: List of agent names that were added
        ides: List of IDE names that were added
    """
    if not agents and not ides:
        print_info(f"\n{INFO_MESSAGES['no_agents_added']}")
        print_info("No IDEs added either.")
        return

    agent_service = AgentService()
    message_parts = ["[bold green]Configuration Updated Successfully[/bold green]\n"]

    # Add agents info if any
    if agents:
        agent_info_lines = []
        for agent in agents:
            try:
                manifest = agent_service.get_agent_manifest(agent.lower())
                folder = manifest.installation.folder
                commands_subfolder = manifest.installation.commands_subfolder
                display_name = manifest.display_name
                agent_info_lines.append(
                    f"  • [cyan]{display_name}[/cyan]: {folder}{commands_subfolder}/"
                )
            except ValueError:
                agent_info_lines.append(f"  • [cyan]{agent.capitalize()}[/cyan]")

        agent_list = "\n".join(agent_info_lines)
        message_parts.append(
            f"\n**Agents Added ({len(agents)}):**\n{agent_list}\n"
            f"You can now use open-agent-kit commands in these AI assistants!"
        )

    # Add IDEs info if any
    if ides:
        ide_info_lines = []
        for ide in ides:
            ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
            settings_file = f".{ide}/settings.json"
            ide_info_lines.append(f"  • [cyan]{ide_name}[/cyan]: {settings_file}")

        ide_list = "\n".join(ide_info_lines)
        message_parts.append(
            f"\n**IDEs Configured ({len(ides)}):**\n{ide_list}\n"
            f"Auto-approval settings have been installed!"
        )

    print_panel(
        "\n".join(message_parts),
        title="Update Complete",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _get_agent_display_name(agent_service: AgentService, agent: str) -> str:
    """Get display name for an agent from manifest.

    Args:
        agent_service: AgentService instance
        agent: Agent name

    Returns:
        Display name (falls back to capitalized name if manifest not found)
    """
    try:
        manifest = agent_service.get_agent_manifest(agent.lower())
        return manifest.display_name
    except ValueError:
        return agent.capitalize()


def _display_update_message(
    old_agents: list[str],
    new_agents: list[str],
    old_ides: list[str],
    new_ides: list[str],
) -> None:
    """Display message showing what changed in configuration.

    Args:
        old_agents: Previously configured agents
        new_agents: Newly configured agents
        old_ides: Previously configured IDEs
        new_ides: Newly configured IDEs
    """
    agent_service = AgentService()
    message_parts = ["[bold green]Configuration Updated Successfully[/bold green]\n"]

    # Show agent changes
    old_agents_set = set(old_agents)
    new_agents_set = set(new_agents)
    agents_added = new_agents_set - old_agents_set
    agents_removed = old_agents_set - new_agents_set
    agents_kept = old_agents_set & new_agents_set

    if agents_added or agents_removed or agents_kept:
        agent_lines = []

        if agents_kept:
            agent_lines.append("[dim]Keeping:[/dim]")
            for agent in sorted(agents_kept):
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [cyan]{agent_name}[/cyan]")

        if agents_added:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[green]Added:[/green]")
            for agent in sorted(agents_added):
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [green]{agent_name}[/green]")

        if agents_removed:
            if agent_lines:
                agent_lines.append("")
            agent_lines.append("[red]Removed:[/red]")
            for agent in sorted(agents_removed):
                agent_name = _get_agent_display_name(agent_service, agent)
                agent_lines.append(f"  • [red]{agent_name}[/red]")

        message_parts.append("\n**Agent Configuration:**\n" + "\n".join(agent_lines))

    # Show IDE changes
    old_ides_set = set(old_ides)
    new_ides_set = set(new_ides)
    ides_added = new_ides_set - old_ides_set
    ides_removed = old_ides_set - new_ides_set
    ides_kept = old_ides_set & new_ides_set

    if ides_added or ides_removed or ides_kept:
        ide_lines = []

        if ides_kept:
            ide_lines.append("[dim]Keeping:[/dim]")
            for ide in sorted(ides_kept):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [cyan]{ide_name}[/cyan]")

        if ides_added:
            if ide_lines:
                ide_lines.append("")
            ide_lines.append("[green]Added:[/green]")
            for ide in sorted(ides_added):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [green]{ide_name}[/green]")

        if ides_removed:
            if ide_lines:
                ide_lines.append("")
            ide_lines.append("[red]Removed:[/red]")
            for ide in sorted(ides_removed):
                ide_name = IDE_DISPLAY_NAMES.get(ide, ide.capitalize())
                ide_lines.append(f"  • [red]{ide_name}[/red]")

        message_parts.append("\n**IDE Configuration:**\n" + "\n".join(ide_lines))

    print_panel(
        "\n".join(message_parts),
        title="Update Complete",
        style="green",
    )

    print_info(f"\n{INFO_MESSAGES['more_info'].format(url=PROJECT_URL)}")


def _display_agent_added_message(agents: list[str]) -> None:
    """Display message after adding agents to existing installation.

    DEPRECATED: Use _display_additions_message instead.

    Args:
        agents: List of agent names that were added
    """
    _display_additions_message(agents, [])


def _interactive_feature_selection(existing_features: list[str] | None = None) -> list[str]:
    """Interactive feature selection with checkboxes.

    Args:
        existing_features: List of currently installed features (will be pre-selected)

    Returns:
        List of selected feature names
    """
    if existing_features:
        print_header("Update Features")
        print_info("Current features are pre-selected. Check/uncheck to modify.\n")
    else:
        print_header("Select Features")
        print_info(FEATURE_MESSAGES["select_features_prompt"] + "\n")

    existing_features = existing_features or []
    existing_features_lower = [f.lower() for f in existing_features]

    options = []
    default_selections = []

    for feature_name in SUPPORTED_FEATURES:
        config = FEATURE_CONFIG.get(feature_name, {})
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        deps = cast(list[str], config.get("dependencies", []))
        deps_str = f" (requires: {', '.join(deps)})" if deps else ""

        options.append(
            SelectOption(
                value=feature_name,
                label=display_name,
                description=str(config.get("description", "")) + deps_str,
            )
        )

        # Pre-select if already installed or if it's default for new installs
        if feature_name.lower() in existing_features_lower:
            default_selections.append(feature_name)
        elif not existing_features and config.get("default_enabled", False):
            default_selections.append(feature_name)

    # Loop until we have a valid selection (dependencies satisfied or user confirms removal)
    while True:
        selected = multi_select(
            options,
            "Which features would you like to enable? (Space to select, Enter to confirm)",
            defaults=default_selections,
            min_selections=0,
        )

        # Check for dependency violations
        features_to_remove = _get_features_with_unmet_dependencies(selected)

        if not features_to_remove:
            # All dependencies satisfied
            return selected

        # Show what would be removed and ask for confirmation
        display_names = [FEATURE_DISPLAY_NAMES.get(f, f) for f in features_to_remove]
        print_warning(
            f"\nThe following features will be removed (missing dependencies):\n"
            f"  {', '.join(display_names)}\n"
        )

        confirm = typer.confirm("Continue with these features removed?", default=True)

        if confirm:
            # Remove features with unmet dependencies
            return [f for f in selected if f not in features_to_remove]
        else:
            # Let user re-select - use their last selection as the new defaults
            print_info("\nReturning to feature selection...\n")
            default_selections = selected


def _get_features_with_unmet_dependencies(selected_features: list[str]) -> list[str]:
    """Find features whose dependencies are not selected.

    Args:
        selected_features: List of selected feature names

    Returns:
        List of features that would need to be removed
    """
    selected_set = set(selected_features)
    features_to_remove: list[str] = []

    # Keep iterating until no more changes (handles transitive dependencies)
    changed = True
    while changed:
        changed = False
        for feature_name in list(selected_set):
            config = FEATURE_CONFIG.get(feature_name, {})
            deps = cast(list[str], config.get("dependencies", []))

            # Check if all dependencies are selected
            if deps and not all(dep in selected_set for dep in deps):
                selected_set.remove(feature_name)
                features_to_remove.append(feature_name)
                changed = True

    return features_to_remove
