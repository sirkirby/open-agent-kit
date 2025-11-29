"""State service for managing internal OAK state."""

from pathlib import Path

from open_agent_kit.constants import STATE_FILE
from open_agent_kit.models.state import OakState


class StateService:
    """Service for managing internal OAK state.

    State is stored separately from config.yaml to keep user-facing
    configuration clean. State includes things like applied migrations
    that users should not need to see or edit.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize state service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.state_path = self.project_root / STATE_FILE

    def load_state(self) -> OakState:
        """Load state from file.

        Returns:
            OakState instance
        """
        return OakState.load(self.state_path)

    def save_state(self, state: OakState) -> None:
        """Save state to file.

        Args:
            state: OakState instance to save
        """
        state.save(self.state_path)

    def get_applied_migrations(self) -> list[str]:
        """Get list of applied migration IDs.

        Returns:
            List of migration IDs that have been applied
        """
        state = self.load_state()
        return state.migrations

    def add_applied_migrations(self, migration_ids: list[str]) -> None:
        """Add migration IDs to the applied list.

        Args:
            migration_ids: List of migration IDs to add
        """
        state = self.load_state()
        # Use set to avoid duplicates, then sort for consistency
        all_migrations = list(set(state.migrations + migration_ids))
        all_migrations.sort()
        state.migrations = all_migrations
        self.save_state(state)

    def is_migration_applied(self, migration_id: str) -> bool:
        """Check if a specific migration has been applied.

        Args:
            migration_id: Migration ID to check

        Returns:
            True if migration has been applied
        """
        return migration_id in self.get_applied_migrations()


def get_state_service(project_root: Path | None = None) -> StateService:
    """Get a StateService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        StateService instance
    """
    return StateService(project_root)
