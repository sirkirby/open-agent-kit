# Constitution

 Oak's engineering constitution feature provides a structured, decision-driven framework to define and enforce project-wide engineering principles. It helps teams establish clear guidelines on architecture, testing, error handling, code reviews, and more.

## `/oak.constitution-create [description]`

**Create an engineering constitution** - AI agent guides you through an interactive decision framework to generate a tailored project constitution.

Example:

```bash
/oak.constitution-create
```

The AI will:

1. **Analyze your project** (greenfield vs brownfield, existing patterns)
2. **Guide you through key decisions**:
   - Architectural pattern (Vertical Slice, Clean, Layered, etc.)
   - Testing strategy (Comprehensive, Balanced, Pragmatic)
   - Error handling approach (Result Pattern, exceptions, mixed)
   - Code review policies, documentation level, CI/CD enforcement
3. **Generate tailored constitution** matching YOUR needs (not prescriptive defaults)
4. **Additively update agent instruction files** with constitution references (never overwrites)

**For brownfield projects**: Detects and incorporates existing conventions from agent instruction files and codebase.

**For existing users**: See [Constitution Upgrade Guide](docs/constitution-upgrade-guide.md) for modernization options.

## `/oak.constitution-validate`

**Validate and modernize** your constitution. The AI will:

- Check structure, metadata, and declarative language
- **Reality alignment checks**: Verify requirements match actual project capabilities
- **Detect old-style constitutions**: Offer modernization to decision-driven framework
- Provide three paths: standard validation, full modernization, or hybrid approach

See [Constitution Upgrade Guide](docs/constitution-upgrade-guide.md) for details on modernization options.

## `/oak.constitution-amend <summary>`

**Add an amendment** to the constitution with proper versioning and ratification tracking. The AI helps you assess impact, choose the right version bump (major/minor/patch), and keeps agent instruction files in sync.
