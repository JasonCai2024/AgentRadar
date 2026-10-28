"""Google AntiGravity Adapter Definition.
"""

from .base import AgentDefinition

ANTIGRAVITY_DEF = AgentDefinition(
    id="antigravity",
    display_name="Google AntiGravity",
    icon_symbol="🪐",
    process_names=["antigravity.exe"],
    window_title_keywords=["antigravity", "clone t3 code"],
    api_domains=[
        "googleapis.com",
        "google.com",
        "generativelanguage.googleapis.com"
    ],
    log_dirs=[
        r"~/.gemini/antigravity/brain"
    ],
    approval_patterns=[
        "approval_required",
        "confirm_command",
        "allow_execute",
        "waiting for user",
        "needs approval",
        "permission request"
    ],
    completion_patterns=[
        "done",
        "finished",
        "task completed"
    ]
)
