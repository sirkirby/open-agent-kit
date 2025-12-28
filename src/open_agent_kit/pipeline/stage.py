"""Stage abstraction for pipeline execution."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from open_agent_kit.pipeline.context import FlowType, PipelineContext

if TYPE_CHECKING:
    from open_agent_kit.services.agent_service import AgentService
    from open_agent_kit.services.config_service import ConfigService
    from open_agent_kit.services.feature_service import FeatureService
    from open_agent_kit.services.ide_settings_service import IDESettingsService
    from open_agent_kit.services.skill_service import SkillService


class StageLifecycle(str, Enum):
    """Lifecycle category for a stage.

    Stages that install/add resources should have INSTALL lifecycle.
    Stages that remove/cleanup resources should have CLEANUP lifecycle.
    Stages that don't manage resources have NEUTRAL lifecycle.
    """

    INSTALL = "install"  # Adds/installs resources
    CLEANUP = "cleanup"  # Removes/cleans up resources
    NEUTRAL = "neutral"  # Doesn't manage resources (hooks, validation, etc.)


class StageResult(str, Enum):
    """Result of stage execution."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StageOutcome:
    """Outcome of a stage execution.

    Attributes:
        result: Whether stage succeeded, was skipped, or failed
        message: Human-readable message for UI display
        error: Error message if failed (for logging/debugging)
        data: Optional data to pass to subsequent stages
    """

    result: StageResult
    message: str
    error: str | None = None
    data: dict[str, Any] | None = None

    @classmethod
    def success(cls, message: str, data: dict[str, Any] | None = None) -> "StageOutcome":
        """Create a successful outcome."""
        return cls(StageResult.SUCCESS, message, data=data)

    @classmethod
    def skipped(cls, message: str) -> "StageOutcome":
        """Create a skipped outcome."""
        return cls(StageResult.SKIPPED, message)

    @classmethod
    def failed(cls, message: str, error: str | None = None) -> "StageOutcome":
        """Create a failed outcome."""
        return cls(StageResult.FAILED, message, error=error)


@runtime_checkable
class Stage(Protocol):
    """Protocol defining the stage interface.

    Stages are the building blocks of the pipeline. Each stage handles
    one specific concern (e.g., config creation, agent setup).
    """

    @property
    def name(self) -> str:
        """Unique identifier for this stage."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable name for progress display."""
        ...

    @property
    def order(self) -> int:
        """Execution order (lower runs first)."""
        ...

    def should_run(self, context: PipelineContext) -> bool:
        """Determine if this stage should execute.

        Args:
            context: Pipeline context with selections and flow type

        Returns:
            True if stage should run, False to skip
        """
        ...

    def execute(self, context: PipelineContext) -> StageOutcome:
        """Execute the stage.

        Args:
            context: Pipeline context to read from and write to

        Returns:
            StageOutcome indicating success, skip, or failure
        """
        ...


class BaseStage(ABC):
    """Base class for pipeline stages with common functionality.

    Provides:
    - Default order based on class definition order
    - Flow type filtering via `applicable_flows`
    - Service instantiation helpers
    - Error handling wrapper

    Example:
        >>> class MyStage(BaseStage):
        ...     name = "my_stage"
        ...     display_name = "My Stage"
        ...     order = 100
        ...     applicable_flows = {FlowType.FRESH_INIT, FlowType.UPDATE}
        ...
        ...     def _should_run(self, context: PipelineContext) -> bool:
        ...         return context.selections.has_agent_changes
        ...
        ...     def _execute(self, context: PipelineContext) -> StageOutcome:
        ...         # Do work
        ...         return StageOutcome.success("Completed my stage")
    """

    # Subclasses must define these
    name: str
    display_name: str
    order: int

    # Flow types this stage applies to (all by default)
    applicable_flows: set[FlowType] = {
        FlowType.FRESH_INIT,
        FlowType.UPDATE,
        FlowType.UPGRADE,
        FlowType.FORCE_REINIT,
    }

    # Whether this stage is critical (pipeline stops on failure)
    is_critical: bool = True

    # Lifecycle classification - INSTALL stages should have a CLEANUP counterpart
    lifecycle: StageLifecycle = StageLifecycle.NEUTRAL

    # Name of the counterpart stage (e.g., install stage specifies cleanup stage)
    # Used for validation to ensure install/cleanup pairs are complete
    counterpart_stage: str | None = None

    def should_run(self, context: PipelineContext) -> bool:
        """Check if stage should run based on flow type and custom logic.

        First checks flow type applicability, then delegates to _should_run.
        If applicable_flows is None, the stage applies to all flow types.
        """
        if self.applicable_flows is not None:
            if context.flow_type not in self.applicable_flows:
                return False
        return self._should_run(context)

    @abstractmethod
    def _should_run(self, context: PipelineContext) -> bool:
        """Custom logic to determine if stage should run.

        Override this in subclasses for stage-specific conditions.
        """
        ...

    def execute(self, context: PipelineContext) -> StageOutcome:
        """Execute with error handling wrapper.

        Catches exceptions and converts to StageOutcome.failed.
        """
        try:
            return self._execute(context)
        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            context.add_error(self.name, error_msg)
            return StageOutcome.failed(
                f"Permission denied: {self.display_name}",
                error=error_msg,
            )
        except FileNotFoundError as e:
            error_msg = f"File not found: {e}"
            context.add_error(self.name, error_msg)
            return StageOutcome.failed(
                f"File not found: {self.display_name}",
                error=error_msg,
            )
        except ValueError as e:
            error_msg = f"Invalid value: {e}"
            context.add_error(self.name, error_msg)
            return StageOutcome.failed(
                f"Invalid value: {self.display_name}",
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            context.add_error(self.name, error_msg)
            return StageOutcome.failed(
                f"Failed: {self.display_name}",
                error=error_msg,
            )

    @abstractmethod
    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Perform the actual stage work.

        Override this in subclasses with stage-specific logic.
        """
        ...

    # Service helpers - lazily imported to avoid circular dependencies
    def _get_config_service(self, context: PipelineContext) -> "ConfigService":
        """Get ConfigService instance."""
        from open_agent_kit.services.config_service import ConfigService

        return ConfigService(context.project_root)

    def _get_agent_service(self, context: PipelineContext) -> "AgentService":
        """Get AgentService instance."""
        from open_agent_kit.services.agent_service import AgentService

        return AgentService(context.project_root)

    def _get_feature_service(self, context: PipelineContext) -> "FeatureService":
        """Get FeatureService instance."""
        from open_agent_kit.services.feature_service import FeatureService

        return FeatureService(context.project_root)

    def _get_ide_settings_service(self, context: PipelineContext) -> "IDESettingsService":
        """Get IDESettingsService instance."""
        from open_agent_kit.services.ide_settings_service import IDESettingsService

        return IDESettingsService(context.project_root)

    def _get_skill_service(self, context: PipelineContext) -> "SkillService":
        """Get SkillService instance."""
        from open_agent_kit.services.skill_service import SkillService

        return SkillService(context.project_root)
