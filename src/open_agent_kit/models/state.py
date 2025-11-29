"""Internal state models for open-agent-kit.

This module contains models for internal state that should not be
user-facing or editable. State is stored separately from config.yaml.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class OakState(BaseModel):
    """Internal state for OAK installation.

    This tracks internal state like applied migrations that users
    should not need to see or edit. Stored in .oak/state.yaml.
    """

    migrations: list[str] = Field(
        default_factory=list,
        description="Completed migration IDs",
    )

    @classmethod
    def load(cls, state_path: Path) -> "OakState":
        """Load state from file.

        Args:
            state_path: Path to state.yaml file

        Returns:
            OakState instance (empty if file doesn't exist)
        """
        if not state_path.exists():
            return cls()

        with open(state_path) as f:
            data = yaml.safe_load(f)
            if not data:
                return cls()
            return cls(**data)

    def save(self, state_path: Path) -> None:
        """Save state to file.

        Args:
            state_path: Path to state.yaml file
        """
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
