# Feature Development Playbook

This guide covers the features system in open-agent-kit and how to develop new features.

## Features Overview

Open Agent Kit uses a modular feature system where each feature is a self-contained package with:
- `manifest.yaml` - Feature metadata, dependencies, and file listings
- `commands/` - Agent command templates (`.md` files)
- `templates/` - Document templates (Jinja2 `.j2` files)

### Available Features

| Feature | Description | Dependencies |
|---------|-------------|--------------|
| **constitution** | Engineering standards, architectural patterns, team conventions | None |
| **rfc** | RFC workflow for documenting technical decisions | constitution |
| **issues** | Issue workflow integration with Azure DevOps/GitHub Issues | constitution |

### Core Assets

The `features/core/` directory contains non-feature assets:
- IDE settings (VSCode, Cursor auto-approval configurations)
- Utility scripts (future)

Core assets are always installed and are not user-selectable.

## Feature Architecture

```
features/
├── core/                       # Core assets (not a feature)
│   ├── manifest.yaml
│   └── ide/
│       ├── vscode-settings.json
│       └── cursor-settings.json
├── constitution/               # Constitution feature
│   ├── manifest.yaml
│   ├── commands/
│   │   ├── oak.constitution-create.md
│   │   ├── oak.constitution-validate.md
│   │   └── oak.constitution-amend.md
│   └── templates/
│       ├── constitution.md.j2
│       └── decision_points.yaml
├── rfc/                        # RFC feature
│   ├── manifest.yaml
│   ├── commands/
│   │   ├── oak.rfc-create.md
│   │   ├── oak.rfc-list.md
│   │   └── oak.rfc-validate.md
│   └── templates/
│       └── rfc/
│           └── engineering.md.j2
└── issues/                     # Issues feature
    ├── manifest.yaml
    └── commands/
        ├── oak.issue-plan.md
        ├── oak.issue-validate.md
        └── oak.issue-implement.md
```

## Feature Manifest

Each feature has a `manifest.yaml` that defines:

```yaml
# Required fields
name: my-feature               # Internal name (lowercase, hyphens)
display_name: "My Feature"     # User-facing name
description: "What this feature does"
version: "1.0.0"

# Optional fields
default_enabled: true          # Install by default during init
is_core: false                 # Core assets are not user-selectable
dependencies: []               # List of required features
commands: []                   # List of command names (without extension)
templates: []                  # List of template paths
config_defaults: {}            # Default config values for this feature
```

### Dependency Resolution

Features can depend on other features. When a user selects a feature, all its dependencies are automatically included.

Example: If `rfc` depends on `constitution`, selecting `rfc` will also install `constitution`.

The `FeatureService.resolve_dependencies()` method handles:
1. Topological sorting for installation order
2. Circular dependency detection
3. Missing dependency detection

## Creating a New Feature

### Step 1: Create Feature Directory

```bash
mkdir -p features/my-feature/{commands,templates}
```

### Step 2: Create Manifest

Create `features/my-feature/manifest.yaml`:

```yaml
name: my-feature
display_name: "My Feature"
description: "What this feature does for users"
version: "1.0.0"
default_enabled: false
dependencies:
  - constitution  # If needed
commands:
  - my-command-1
  - my-command-2
templates:
  - my-template.md.j2
```

### Step 3: Create Command Templates

Create agent command templates in `features/my-feature/commands/`:

```markdown
---
description: Short description for command listing
---

# My Command

You are helping the user with [task].

## Instructions

1. Step one
2. Step two
3. Run `oak my-feature action` if needed

$ARGUMENTS
```

### Step 4: Create Document Templates (Optional)

Create Jinja2 templates in `features/my-feature/templates/`:

```jinja
# {{ title }}

Created: {{ created_date }}
Author: {{ author }}

## Content

{{ content }}
```

### Step 5: Update Constants

Add the feature to `src/open_agent_kit/constants.py`:

```python
SUPPORTED_FEATURES = ["constitution", "rfc", "issues", "my-feature"]

FEATURE_CONFIG = {
    # ... existing features ...
    "my-feature": {
        "dependencies": ["constitution"],
        "commands": ["my-command-1", "my-command-2"],
        "templates": ["my-template.md.j2"],
    },
}
```

### Step 6: Write Tests

Create tests in `tests/test_my_feature.py`:

```python
import pytest
from open_agent_kit.services.feature_service import FeatureService

class TestMyFeature:
    def test_manifest_loads(self, tmp_path):
        service = FeatureService(tmp_path)
        manifest = service.get_feature_manifest("my-feature")
        assert manifest is not None
        assert manifest.name == "my-feature"

    def test_dependencies_resolve(self, tmp_path):
        service = FeatureService(tmp_path)
        resolved = service.resolve_dependencies(["my-feature"])
        assert "constitution" in resolved
        assert "my-feature" in resolved
```

### Step 7: Update Documentation

Update:
- `README.md` - Features table
- `QUICKSTART.md` - If affects onboarding
- `docs/architecture.md` - Directory structure

## Critical Integration Points

When a feature introduces new agent commands, update both services:

1. `AgentService.create_default_commands()` - Controls which commands `oak init` installs
2. `UpgradeService._get_upgradeable_commands()` - Ensures `oak upgrade` delivers commands to existing projects

Both services use `FeatureService.get_feature_commands()` to get commands for installed features.

## Feature Configuration

Features can define config defaults in their manifest:

```yaml
config_defaults:
  my_setting: default_value
  nested:
    key: value
```

These are merged into `.oak/config.yaml` under a feature-specific key:

```yaml
my-feature:
  my_setting: default_value
  nested:
    key: value
```

## Feature CLI Commands

Users interact with features via:

```bash
# Interactive feature management
oak feature

# List installed and available features
oak feature list

# Add a feature (with dependency resolution)
oak feature add my-feature

# Remove a feature (with dependency checking)
oak feature remove my-feature
```

## Testing Features

### Unit Tests

Test the feature in isolation:

```python
def test_feature_install(self, tmp_path, mock_config):
    service = FeatureService(tmp_path)
    result = service.install_feature("my-feature", agents=["claude"])
    assert result["success"]
    assert "commands_installed" in result
```

### Integration Tests

Test with full init flow:

```python
def test_init_with_feature(self, tmp_path):
    # Run oak init with the feature
    result = runner.invoke(app, ["init", "--agent", "claude", "--feature", "my-feature"])
    assert result.exit_code == 0

    # Verify commands installed
    assert (tmp_path / ".claude/commands/oak.my-command-1.md").exists()
```

### End-to-End Tests

Test the full workflow from command execution to expected outcome.

## Common Pitfalls

- **Forgetting service command lists** → New commands never reach users
- **Missing manifest fields** → Feature fails to load
- **Circular dependencies** → Installation fails
- **Magic strings** → Always import from `open_agent_kit.constants`
- **Missing exports** → Add new models/services to `__init__.py`

## Validation Checklist

Before submitting a new feature:

1. [ ] `manifest.yaml` has all required fields
2. [ ] Dependencies are valid and resolve correctly
3. [ ] Commands are listed in manifest
4. [ ] Constants updated with feature config
5. [ ] Unit tests pass
6. [ ] `oak init` installs commands correctly
7. [ ] `oak upgrade` updates commands correctly
8. [ ] `oak feature add/remove` works
9. [ ] Documentation updated
