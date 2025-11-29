"""Feature models for open-agent-kit."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class FeatureManifest(BaseModel):
    """Feature manifest model representing a feature's metadata and configuration."""

    name: str = Field(..., description="Feature identifier (e.g., 'rfc', 'constitution')")
    display_name: str = Field(..., description="Human-readable feature name")
    description: str = Field(..., description="Feature description")
    version: str = Field(default="1.0.0", description="Feature version")
    default_enabled: bool = Field(default=True, description="Whether enabled by default")
    is_core: bool = Field(
        default=False, description="Whether this is a core (non-selectable) feature"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Required feature dependencies"
    )
    commands: list[str] = Field(
        default_factory=list, description="Command names provided by this feature"
    )
    templates: list[str] = Field(
        default_factory=list, description="Template files provided by this feature"
    )
    config_defaults: dict[str, Any] = Field(
        default_factory=dict, description="Default configuration values"
    )

    @classmethod
    def load(cls, manifest_path: Path) -> "FeatureManifest":
        """Load feature manifest from YAML file.

        Args:
            manifest_path: Path to manifest.yaml file

        Returns:
            FeatureManifest instance

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty manifest: {manifest_path}")

        return cls(**data)

    def get_all_dependencies(self, all_features: dict[str, "FeatureManifest"]) -> list[str]:
        """Get all transitive dependencies for this feature.

        Args:
            all_features: Dictionary of all available features

        Returns:
            List of all dependency feature names (including transitive)
        """
        all_deps: set[str] = set()
        to_process = list(self.dependencies)

        while to_process:
            dep_name = to_process.pop(0)
            if dep_name in all_deps:
                continue
            all_deps.add(dep_name)

            if dep_name in all_features:
                dep_feature = all_features[dep_name]
                for sub_dep in dep_feature.dependencies:
                    if sub_dep not in all_deps:
                        to_process.append(sub_dep)

        return sorted(all_deps)
