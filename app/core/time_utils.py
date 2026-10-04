# 时间服务：统一 UTC 存储 / RFC3339 输出 / 工作日计算 / 中文时间表达归一化
#
# 约定：
# - 数据库统一保存带时区的 UTC ISO 字符串（与 app/models/models.py 的 utc_now 一致）。
# - API 按 RFC3339 返回，序列化时转换为 Asia/Shanghai（+08:00），与接口文档示例一致。
# - “N 个工作日”与“N 小时”语义不同：前者跳过周末与配置节假日，后者为自然小时。

import re
from datetime import UTC, datetime, time, timedelta, timezone

from app.core import config

# 中国无夏令时，使用固定 +08:00 偏移即可，避免 Windows 缺少 tzdata 的兼容问题。
CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    """存储格式：带时区的 UTC ISO 字符串。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    """解析数据库/请求中的 ISO 时间字符串，失败返回 None。"""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def to_api_time(value: str | datetime | None) -> str | None:
    """API 输出：RFC3339（Asia/Shanghai）。"""
    if value is None:
        return None
    dt = parse_iso(value) if isinstance(value, str) else value
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CHINA_TZ).isoformat()


def seconds_until(due_at: str | datetime | None, now: datetime | None = None) -> int | None:
    """剩余秒数：负数表示已超时。"""
    due = parse_iso(due_at) if isinstance(due_at, str) else due_at
    if due is None:
        return None
    base = now or utc_now()
    return int((due - base).total_seconds())


def add_business_days(start: datetime, days: int) -> datetime:
    """自然日叠加后跳过周六、周日与配置节假日，时间点保持不变。"""
    current = start
    remaining = max(days, 0)
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5 and current.strftime("%Y-%m-%d") not in config.HOLIDAYS:
            remaining -= 1
    return current


def _chinese_number_to_int(text: str) -> int | None:
    """支持 一到十九、二十、三十等 Demo 常见表达。"""
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if text.startswith("十") and len(text) == 2 and text[1] in mapping:
        return 10 + mapping[text[1]]
    if len(text) == 2 and text[0] in ("二", "三") and text[1] == "十":
        return mapping[text[0]] * 10
    if len(text) == 3 and text[0] in ("二", "三") and text[1] == "十" and text[2] in mapping:
        return mapping[text[0]] * 10 + mapping[text[2]]
    if len(text) == 1 and text in mapping:
        return mapping[text]
    return None


_NUM = r"(\d{1,2}|[一二两三四五六七八九十]{1,3})"

# 模糊表达：必须转人工确认，不得虚构截止时间
_VAGUE_WORDS = ("尽快", "稍后", "晚点", "有空", "抽空", "第一时间", "尽早", "回头", "今天之内尽快")

# 关键时间表达模式（按优先级匹配）
_PATTERNS: list[tuple[str, str]] = [
    ("business_days", rf"{_NUM}\s*个?\s*工作日(之?内)?"),
    ("business_days", rf"{_NUM}\s*个?\s*工作日内"),
    ("days", rf"{_NUM}\s*天(之?内)?"),
    ("hours", rf"{_NUM}\s*个?\s*小时(之?内)?"),
    ("tomorrow_morning", r"明天(上午|早上|一早)"),
    ("tomorrow_afternoon", r"明天(下午|中午)"),
    ("tomorrow_evening", r"明天(晚上|夜里)"),
    ("tomorrow", r"明天"),
    ("day_after_tomorrow", r"后天"),
    ("today_offwork", r"(今天|今日)(下班前|下班之前)"),
    ("tonight", r"(今天|今日)?(晚上|今晚)"),
    ("today", r"(今天|今日)(内|之内|之内回复)?"),
]


def parse_time_expression(text: str, now: datetime | None = None) -> tuple[datetime | None, str]:
    """解析中文时间表达。

    返回 (due_at, kind)：
    - kind = "exact"  明确时间，可直接计算截止时间
    - kind = "vague"  模糊表达（尽快/稍后等），due_at 为 None，需人工确认
    - kind = "none"   未发现时间表达，due_at 为 None
    """
    if not text:
        return None, "none"

    base = (now or utc_now()).astimezone(CHINA_TZ)
    today = base.replace(hour=0, minute=0, second=0, microsecond=0)

    if any(word in text for word in _VAGUE_WORDS):
        # 模糊词优先，避免“尽快”被误当作确定性承诺
        return None, "vague"

    for kind, pattern in _PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == "business_days":
            amount = _chinese_number_to_int(match.group(1))
            if amount is None:
                return None, "vague"
            due = add_business_days(base, amount)
            return _clamp_end_of_day(due), "exact"
        if kind == "days":
            amount = _chinese_number_to_int(match.group(1))
            if amount is None:
                return None, "vague"
            return _clamp_end_of_day(base + timedelta(days=amount)), "exact"
        if kind == "hours":
            amount = _chinese_number_to_int(match.group(1))
            if amount is None:
                return None, "vague"
            return base + timedelta(hours=amount), "exact"
        if kind == "tomorrow_morning":
            return datetime.combine(today + timedelta(days=1), time(12, 0), CHINA_TZ), "exact"
        if kind == "tomorrow_afternoon":
            return datetime.combine(today + timedelta(days=1), time(15, 0), CHINA_TZ), "exact"
        if kind == "tomorrow_evening":
            return datetime.combine(today + timedelta(days=1), time(20, 0), CHINA_TZ), "exact"
        if kind == "tomorrow":
            return datetime.combine(today + timedelta(days=1), time(18, 0), CHINA_TZ), "exact"
        if kind == "day_after_tomorrow":
            return datetime.combine(today + timedelta(days=2), time(18, 0), CHINA_TZ), "exact"
        if kind == "today_offwork":
            target = today.replace(hour=18, minute=0)
            if target <= base:
                target = base + timedelta(hours=2)
            return target, "exact"
        if kind == "tonight":
            target = today.replace(hour=20, minute=0)
            if target <= base:
                target = base + timedelta(hours=2)
            return target, "exact"
        if kind == "today":
            target = today.replace(hour=23, minute=59)
            if target <= base:
                target = base + timedelta(hours=2)
            return target, "exact"

    return None, "none"


def _clamp_end_of_day(dt: datetime) -> datetime:
    """“N 天/工作日”类表达统一取当日 23:59 为最晚截止。"""
    return dt.replace(hour=23, minute=59, second=0, microsecond=0)
