"""Lifecycle hook stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class TriggerAgentsChangedStage(BaseStage):
    """Trigger hooks when agents are added or removed."""

    name = "trigger_agents_changed"
    display_name = "Running agent change hooks"
    order = StageOrder.TRIGGER_AGENTS_CHANGED
    applicable_flows = {FlowType.UPDATE}
    is_critical = False  # Hooks should not block pipeline

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents changed."""
        return context.selections.has_agent_changes

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger on_agents_changed hooks."""
        feature_service = self._get_feature_service(context)

        results = feature_service.trigger_agents_changed_hooks(
            agents_added=list(context.selections.agents_added),
            agents_removed=list(context.selections.agents_removed),
        )

        # Report results
        successful = sum(1 for r in results.values() if r.get("success"))

        # Extract useful information from hook results
        hook_info = []
        for _feature_name, result in results.items():
            if result.get("success") and result.get("result"):
                hook_result = result["result"]
                if hook_result.get("created"):
                    for agent in hook_result["created"]:
                        hook_info.append(f"Created instruction file for {agent}")
                if hook_result.get("updated"):
                    for agent in hook_result["updated"]:
                        hook_info.append(f"Updated instruction file for {agent}")

        return StageOutcome.success(
            f"Ran {successful}/{len(results)} agent change hooks",
            data={"hook_results": results, "hook_info": hook_info},
        )


class TriggerIDEsChangedStage(BaseStage):
    """Trigger hooks when IDEs are added or removed."""

    name = "trigger_ides_changed"
    display_name = "Running IDE change hooks"
    order = StageOrder.TRIGGER_IDES_CHANGED
    applicable_flows = {FlowType.UPDATE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if IDEs changed."""
        return context.selections.has_ide_changes

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger on_ides_changed hooks."""
        feature_service = self._get_feature_service(context)

        results = feature_service.trigger_ides_changed_hooks(
            ides_added=list(context.selections.ides_added),
            ides_removed=list(context.selections.ides_removed),
        )

        successful = sum(1 for r in results.values() if r.get("success"))

        return StageOutcome.success(
            f"Ran {successful}/{len(results)} IDE change hooks",
            data={"hook_results": results},
        )


class TriggerInitCompleteStage(BaseStage):
    """Trigger init complete hooks at the end of initialization."""

    name = "trigger_init_complete"
    display_name = "Running initialization hooks"
    order = StageOrder.TRIGGER_INIT_COMPLETE
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run at end of init/update."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger on_init_complete hooks."""
        feature_service = self._get_feature_service(context)

        results = feature_service.trigger_init_complete_hooks(
            is_fresh_install=context.is_fresh_install or context.is_force_reinit,
            agents=context.selections.agents,
            ides=context.selections.ides,
            features=context.selections.features,
        )

        successful = sum(1 for r in results.values() if r.get("success"))

        return StageOutcome.success(
            f"Ran {successful}/{len(results)} init hooks",
            data={"hook_results": results},
        )


def get_hook_stages() -> list[BaseStage]:
    """Get all hook stages."""
    return [
        TriggerAgentsChangedStage(),
        TriggerIDEsChangedStage(),
        TriggerInitCompleteStage(),
    ]
