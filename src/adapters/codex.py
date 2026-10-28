"""OpenAI Codex Adapter Definition.
"""

from .base import AgentDefinition

CODEX_DEF = AgentDefinition(
    id="codex",
    display_name="OpenAI Codex",
    icon_symbol="💬",
    process_names=[
        "chatgpt.exe",
        "codex.exe",
        "codex-code-mode-host.exe",
        "codex-computer-use-swift.exe"
    ],
    window_title_keywords=["chatgpt", "codex"],
    api_domains=[
        "openai.com",
        "chatgpt.com",
        "api.openai.com",
        "cloudflare.com"
    ],
    log_dirs=[
        r"~/.codex/sessions"
    ],
    approval_patterns=[
        "requires user approval",
        "waiting for user",
        "approval_required",
        "confirm tool call",
        "needs approval"
    ],
    completion_patterns=[
        "completed",
        "finished",
        "stop_turn"
    ]
)
