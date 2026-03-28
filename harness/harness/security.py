"""Legacy security helpers.

The Claude SDK hook integration was removed when the harness moved to the
Codex backend. The file remains as a compatibility stub so older imports do
not fail.
"""


async def bash_security_hook(*_args, **_kwargs) -> dict[str, str]:
    """Compatibility stub for the removed Claude hook pipeline."""
    return {"decision": "allow"}
