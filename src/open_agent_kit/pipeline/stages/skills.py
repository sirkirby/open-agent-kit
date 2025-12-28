"""Skill installation and cleanup stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class CleanupAgentSkillsStage(BaseStage):
    """Remove skills for agents that were deselected.

    When an agent is removed from the configuration, this stage cleans up
    the skills that were installed in that agent's skills directory.
    """

    name = "cleanup_agent_skills"
    display_name = "Removing skills for deselected agents"
    order = StageOrder.REMOVE_AGENT_COMMANDS - 1  # Run before command removal
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "refresh_skills"  # Pairs with RefreshSkillsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were removed."""
        return bool(context.selections.agents_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Clean up skills for removed agents."""
        skill_service = self._get_skill_service(context)

        result = skill_service.cleanup_skills_for_removed_agents(
            list(context.selections.agents_removed)
        )

        agents_cleaned = result.get("agents_cleaned", [])
        skills_removed = result.get("skills_removed", [])
        errors = result.get("errors", [])

        if errors:
            return StageOutcome.success(
                f"Cleaned up skills for {len(agents_cleaned)} agent(s) with warnings",
                data=result,
            )

        if skills_removed:
            return StageOutcome.success(
                f"Removed {len(skills_removed)} skill(s) for {len(agents_cleaned)} agent(s)",
                data=result,
            )

        return StageOutcome.success(
            "No skills to clean up",
            data=result,
        )


class InstallSkillsStage(BaseStage):
    """Install skills for features during fresh install.

    Note: Skills are primarily installed via feature_service.install_feature(),
    which calls skill_service.install_skills_for_feature() when was_disabled=True.

    This stage handles edge cases like when features are already installed
    but skills need to be installed for a newly added skills-capable agent.
    """

    name = "install_skills"
    display_name = "Installing skills"
    order = StageOrder.INSTALL_SKILLS
    applicable_flows = {FlowType.FRESH_INIT, FlowType.FORCE_REINIT}
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    # Cleanup happens via oak remove command, not a pipeline stage
    counterpart_stage = None  # Explicitly documented as handled by oak remove

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are features and potentially skills-capable agents."""
        # The main skill installation happens in install_feature()
        # This stage is for any cleanup/edge cases
        return bool(context.selections.features)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Skills are installed by install_feature(), this is a verification step."""
        skill_service = self._get_skill_service(context)

        # Check if any skills-capable agent is configured
        if not skill_service._has_skills_capable_agent():
            return StageOutcome.skipped("No skills-capable agents configured")

        # Get installed skills
        installed_skills = skill_service.list_installed_skills()

        return StageOutcome.success(
            f"Skills ready ({len(installed_skills)} installed)",
            data={"installed_skills": installed_skills},
        )


class RefreshSkillsStage(BaseStage):
    """Refresh skills when agents are added that support skills.

    When a new agent is added that supports skills (e.g., adding Codex
    to a project that already has Claude), this stage ensures skills
    are installed for the new agent.
    """

    name = "refresh_skills"
    display_name = "Installing skills for new agents"
    order = StageOrder.REFRESH_SKILLS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = "cleanup_agent_skills"  # Pairs with CleanupAgentSkillsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were added."""
        return bool(context.selections.agents_added)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Refresh skills to ensure they're installed for all skills-capable agents."""
        skill_service = self._get_skill_service(context)

        # Check if any configured agent supports skills
        if not skill_service._has_skills_capable_agent():
            return StageOutcome.skipped("No skills-capable agents configured")

        # Refresh skills - this copies existing skills to newly added agents
        result = skill_service.refresh_skills()
        skills_refreshed = result.get("skills_refreshed", [])

        if skills_refreshed:
            return StageOutcome.success(
                f"Installed {len(skills_refreshed)} skill(s) for new agent(s)",
                data={"skills_refreshed": skills_refreshed, "agents": result.get("agents", [])},
            )
        else:
            return StageOutcome.success("No skills to refresh")


def get_skill_stages() -> list[BaseStage]:
    """Get all skill stages."""
    return [
        CleanupAgentSkillsStage(),
        InstallSkillsStage(),
        RefreshSkillsStage(),
    ]
