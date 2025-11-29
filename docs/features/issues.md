# Issues

Oak's issue management features help you systematically plan, implement, and validate work on issues from supported providers. The process is designed to ensure clarity, thoroughness, and and integration with your existing SDLC.

## Issue Provider Configuration

Configure the tracker that feeds issue workflows. Use these commands to set up Azure DevOps or GitHub Issues integration:

### `oak config issue-provider set`

Set the active provider and its required settings:

```bash
# Azure DevOps
oak config issue-provider set \
  --provider ado \
  --organization contoso \
  --project web \
  --pat-env AZURE_DEVOPS_PAT

# GitHub Issues
oak config issue-provider set \
  --provider github \
  --owner sirkirby \
  --repo open-agent-kit \
  --token-env GITHUB_TOKEN
```

### `oak config issue-provider check`

Validates the active provider to ensure configuration and environment variables are in place:

```bash
oak config issue-provider check
```

### `oak config issue-provider show`

Displays the stored configuration (minus secrets) for auditing:

```bash
oak config issue-provider show
```

## Agent Commands

### `/oak.issue-plan <provider> <issue>`

Creates the implementation plan (context JSON + `plan.md`) and prepares the issue branch. The agent will:

1. Confirm provider + issue id with you.
2. Run `/oak.issue-plan <provider> <issue>` (which calls `oak issue plan <id> [--provider <key>]` under the hood) after `oak config issue-provider check` succeeds.
3. Capture objectives, constraints, risks, dependencies, and definition of done via the CLI prompts.
4. Review the generated artifacts in `oak/issue/<provider>/<issue>/` (including `codebase.md`, which snapshots the `src/` and `tests/` tree so the agent knows where to start exploring).

### `/oak.issue-implement <provider> <issue>`

Consumes the stored plan plus any extra context you supply. The agent will:

1. Ensure `/oak.issue-plan` and `/oak.issue-validate` have already run.
2. Execute `/oak.issue-implement <provider> <issue> [notes...]` (invokes `oak issue implement …`).
3. The CLI re-checkouts the branch, echoes the plan/notes/codebase snapshot paths, and logs the additional context to `notes.md`.
4. You open `plan.md`, `notes.md`, and `codebase.md`, then study existing code before implementing.

> If you omit the issue id, the agent command infers it from the current branch or the most recent `/oak.issue-plan` entry and prints which one it chose so you can confirm.

### `/oak.issue-validate <provider> <issue>`

Validates the artifacts created by `/oak.issue-implement`. The agent will:

1. Confirm the provider + issue id.
2. Run `/oak.issue-validate <provider> <issue>` (calls `oak issue validate …`).
3. Review the CLI summary for pending sections (objectives, risks, dependencies, definition of done) or missing acceptance criteria.
4. Report findings and help fill in any gaps so the implementation is truly review-ready.

> Validation can also infer the issue from your current branch or most recent plan if you omit the id; the agent command echoes what it selected.
