"""Qoder (Qcode / 千帆代码助手) Adapter Definition.
"""

from .base import AgentDefinition

QODER_DEF = AgentDefinition(
    id="qoder",
    display_name="Qoder (Qcode)",
    icon_symbol="⚡",
    process_names=["qoder.exe"],
    window_title_keywords=["qoder"],
    api_domains=[
        "baidubce.com",
        "baidu.com",
        "qianfan.baidubce.com",
        "aip.baidubce.com"
    ],
    log_dirs=[
        r"~/.qoder/projects"
    ],
    approval_patterns=[
        "waiting for user confirmation",
        "confirm_command",
        "need_confirm",
        "等待用户确认",
        "是否允许执行"
    ],
    completion_patterns=[
        "generation complete",
        "stream end",
        "finished"
    ]
)
