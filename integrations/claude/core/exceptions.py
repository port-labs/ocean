class ClaudeSkillUsageResyncError(Exception):
    """Raised when one or more skill-usage days could not be fetched.

    Raising after yielding successful days (rather than finishing silently) makes
    Ocean skip its delete phase, so entities for the failed days are preserved
    until the next resync.
    """
