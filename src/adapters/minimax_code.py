"""MiniMax Code Adapter Definition.
"""

from .base import AgentDefinition

MINIMAX_CODE_DEF = AgentDefinition(
    id="minimax_code",
    display_name="MiniMax Code",
    icon_symbol="🤖",
    process_names=["minimax code.exe", "minimax.exe"],
    window_title_keywords=["minimax code", "minimax"],
    api_domains=[
        "minimax.chat",
        "minimaxi.com",
        "api.minimax.chat"
    ],
    log_dirs=[
        r"~/.minimax/v2/sessions"
    ],
    approval_patterns=[
        "waiting for user",
        "confirm command",
        "need approval",
        "等待确认",
        "是否执行"
    ],
    completion_patterns=[
        "finished",
        "response completed"
    ]
)
