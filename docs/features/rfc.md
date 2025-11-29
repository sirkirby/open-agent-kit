# RFC Management

Oak's RFC management features streamline the process of creating, listing, and validating RFCs through an intelligent agent that collaborates with you. Below are the key commands available:

## `/oak.rfc-create <description>`

- Drive the RFC workflow through your agent. The prompt now guides you to confirm requirements, investigate existing context (brownfield and greenfield), choose the correct template, and synthesize a full draft before relying on any CLI scaffolding.
- Expect the agent to pause for clarification, surface related RFCs that may conflict or align, and request approval before running support commands (e.g., `oak rfc create`).
- After drafting, you will review the generated markdown, integrate additional evidence, and decide whether to run validation.

Example:

```bash
/oak.rfc-create Add OAuth2 authentication for API endpoints
```

The agent will collaborate with you to:

1. Gather additional context (stakeholders, constraints, related work)
2. Investigate the repository for patterns, dependencies, or prior RFCs
3. Select the best-fit template and outline section-by-section content
4. Scaffold the RFC file using the CLI and replace all placeholders with actionable content
5. Summarize open questions and next steps for manual review

## `/oak.rfc-list [filter]`

- Produce analytical views of the RFC portfolio. The agent can call `oak rfc list --json` to compute status breakdowns, stale drafts, top contributors, or filtered subsets, then explain what requires attention.
- Natural language filters such as "draft RFCs older than 60 days" or "show approved RFCs tagged observability" are supported.

## `/oak.rfc-validate <rfc-number>`

- Perform an interactive quality review. The agent combines manual evaluation with optional CLI validation (`oak rfc validate RFC-###`) after asking for consent.
- Findings are grouped by severity (critical/major/minor), and you can opt-in for assistance applying fixes in place.

> Tip: If no RFC number is provided, the agent will automatically target the most recent RFC.
