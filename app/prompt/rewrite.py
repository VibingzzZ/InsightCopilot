"""草稿润色 / 改写 Prompt（轻量、低 token，Task 02）。

与 reply.py 的「完整副驾生成」不同：这里只做「在已有草稿上做局部改写」，
目标明确（语气调整 / 表达优化），prompt 尽量短，降低 token 开销，也避免模型
在改写时引入新的业务事实。
"""

# 各指令的改写目标说明（直接拼进 prompt，保持精炼）
REWRITE_GOALS: dict[str, str] = {
    "adjust_tone": "调整语气：保持原意与事实不变，仅按指定语气风格改写，使表达更贴合服务场景。",
    "optimize_expression": "优化表达：在不改变事实与承诺的前提下，精简冗余、理顺语句、提升可读性。",
}

# adjust_tone 的语气风格说明
TONE_GUIDE: dict[str, str] = {
    "polite": "礼貌：用「您 / 请」等敬语，措辞周全。",
    "empathetic": "共情：先认可对方感受，再给方案。",
    "concise": "简洁：去掉客套，直奔结论。",
    "warm": "亲切：口语化、带温度，像熟络的客服。",
}

# 单一模板，靠 goal / extra 两个插槽区分指令，避免多套 prompt 膨胀
REWRITE_PROMPT = """你是客服回复润色助手。请仅在已有草稿上做局部改写，不得新增订单状态、退款时间等事实。
目标：{goal}
{extra}
原草稿：
{draft}
要求：只输出改写后的草稿全文，不要解释。严格按 json 输出：{{"rewritten": "..."}}。
"""
