DEFAULT_SKILL_ROOTS: list[str] = [
    # Cross-tool / Codex / Cursor / Antigravity (new default) / Copilot / OpenCode
    ".agents/skills",
    # Antigravity legacy (still supported per Google docs)
    ".agent/skills",
    # Cursor
    ".cursor/skills",
    # Claude Code
    ".claude/skills",
    # Codex (also uses .agents/skills as primary)
    ".codex/skills",
    # GitHub Copilot (project skills)
    ".github/skills",
    # OpenCode
    ".opencode/skills",
    # Marketplace / gitops convention (Port docs, npx skills add)
    "skills",
]

SKILL_MD_FILENAME = "SKILL.md"
