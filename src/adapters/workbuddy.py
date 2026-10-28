"""WorkBuddy Adapter Definition.
"""

from .base import AgentDefinition

WORKBUDDY_DEF = AgentDefinition(
    id="workbuddy",
    display_name="WorkBuddy",
    icon_symbol="🤝",
    process_names=["workbuddy.exe"],
    window_title_keywords=["workbuddy"],
    api_domains=[
        "workbuddy.cn",
        "workbuddy.com"
    ],
    log_dirs=[
        r"~/.workbuddy/workspace/sessions",
        r"~/.workbuddy/storage/sessions"
    ],
    approval_patterns=[
        "waiting for user",
        "confirm",
        "等待用户处理",
        "等待确认",
        "请确认操作"
    ],
    completion_patterns=[
        "completed",
        "finished"
    ]
)
