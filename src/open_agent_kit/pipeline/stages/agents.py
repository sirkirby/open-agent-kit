"""Agent setup stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class RemoveAgentCommandsStage(BaseStage):
    """Remove commands for deselected agents."""

    name = "remove_agent_commands"
    display_name = "Removing deselected agent commands"
    order = StageOrder.REMOVE_AGENT_COMMANDS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_agent_commands"  # Pairs with InstallAgentCommandsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were removed."""
        return bool(context.selections.agents_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove commands for removed agents."""
        agent_service = self._get_agent_service(context)

        removed_count = 0
        for agent_type in context.selections.agents_removed:
            count = agent_service.remove_agent_commands(agent_type)
            removed_count += count

        return StageOutcome.success(
            f"Removed {removed_count} command(s) for {len(context.selections.agents_removed)} agent(s)",
            data={"removed_count": removed_count},
        )


class InstallAgentCommandsStage(BaseStage):
    """Install feature commands for newly added agents."""

    name = "install_agent_commands"
    display_name = "Installing agent commands"
    order = StageOrder.INSTALL_AGENT_COMMANDS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = "remove_agent_commands"  # Pairs with RemoveAgentCommandsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were added."""
        return bool(context.selections.agents_added)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install feature commands for new agents."""
        config_service = self._get_config_service(context)
        feature_service = self._get_feature_service(context)

        # Get installed features
        installed_features = config_service.get_features()

        # Install each feature for the new agents
        for feature_name in installed_features:
            feature_service.install_feature(feature_name, list(context.selections.agents_added))

        return StageOutcome.success(
            f"Installed commands for {len(context.selections.agents_added)} new agent(s)",
            data={
                "agents_added": list(context.selections.agents_added),
                "features_installed": installed_features,
            },
        )


def get_agent_stages() -> list[BaseStage]:
    """Get all agent stages."""
    return [
        RemoveAgentCommandsStage(),
        InstallAgentCommandsStage(),
    ]
