"""Feature installation stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class ResolveDependenciesStage(BaseStage):
    """Resolve feature dependencies before installation."""

    name = "resolve_dependencies"
    display_name = "Resolving feature dependencies"
    order = StageOrder.RESOLVE_FEATURE_DEPENDENCIES
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are features to install."""
        if context.is_fresh_install or context.is_force_reinit:
            return bool(context.selections.features)
        return bool(context.selections.features_added)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Resolve dependencies for selected features."""
        feature_service = self._get_feature_service(context)

        features_to_resolve = (
            context.selections.features
            if context.is_fresh_install or context.is_force_reinit
            else list(context.selections.features_added)
        )

        resolved = feature_service.resolve_dependencies(features_to_resolve)

        return StageOutcome.success(
            f"Resolved {len(resolved)} features",
            data={"resolved_features": resolved},
        )


class RemoveFeaturesStage(BaseStage):
    """Remove features that were deselected."""

    name = "remove_features"
    display_name = "Removing deselected features"
    order = StageOrder.REMOVE_FEATURES
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_features"  # Pairs with InstallFeaturesStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if features were removed."""
        return bool(context.selections.features_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove deselected features."""
        feature_service = self._get_feature_service(context)

        removed = []
        blocked = []

        for feature_name in context.selections.features_removed:
            can_remove, blockers = feature_service.can_remove_feature(feature_name)
            if can_remove:
                feature_service.remove_feature(
                    feature_name,
                    context.selections.agents,
                )
                removed.append(feature_name)
            else:
                blocked.append((feature_name, blockers))
                context.add_warning(
                    self.name,
                    f"Cannot remove '{feature_name}' - required by: {', '.join(blockers)}",
                )

        return StageOutcome.success(
            f"Removed {len(removed)} feature(s)",
            data={"removed": removed, "blocked": blocked},
        )


class InstallFeaturesStage(BaseStage):
    """Install selected features."""

    name = "install_features"
    display_name = "Installing features"
    order = StageOrder.INSTALL_FEATURES
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = "remove_features"  # Pairs with RemoveFeaturesStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are features to install."""
        if context.is_fresh_install or context.is_force_reinit:
            return bool(context.selections.features)
        return bool(context.selections.features_added)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install features for configured agents."""
        feature_service = self._get_feature_service(context)

        # Get resolved features from previous stage, or use selections
        resolve_result = context.get_result("resolve_dependencies", {})
        resolved = resolve_result.get("resolved_features") if resolve_result else None

        if resolved is None:
            resolved = (
                context.selections.features
                if context.is_fresh_install or context.is_force_reinit
                else list(context.selections.features_added)
            )

        installed = []
        for feature_name in resolved:
            # Skip if already installed (for update flows)
            if not context.is_fresh_install and not context.is_force_reinit:
                if feature_name in context.selections.previous_features:
                    continue

            feature_service.install_feature(
                feature_name,
                context.selections.agents,
            )
            installed.append(feature_name)

        message = (
            f"Installed {len(installed)} feature(s): {', '.join(installed)}"
            if installed
            else "No new features to install"
        )

        return StageOutcome.success(
            message,
            data={"installed": installed},
        )


def get_feature_stages() -> list[BaseStage]:
    """Get all feature stages."""
    return [
        ResolveDependenciesStage(),
        RemoveFeaturesStage(),
        InstallFeaturesStage(),
    ]
