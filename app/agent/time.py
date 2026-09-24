"""承诺时间归一化（纯函数，不依赖模型）。

模型只负责读懂「明天上午」这个表达，真正的截止时间一律由这里算出来 ——
这样「3 个工作日」和「72 小时」不会算成同一个时间，也不会出现模型凭空编造截止时间。
"""

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
VAGUE_WORDS = ("尽快", "稍后", "晚点", "抽空", "第一时间", "有空", "回头")
END_OF_BUSINESS_HOUR = 18
_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_WORKDAY_LIMIT = 5  # weekday(): 周一=0 … 周五=4，小于 5 即为工作日

_NUM = r"(\d+|[一二两三四五六七八九十]+)"
_HOURS_RE = re.compile(_NUM + r"\s*个?\s*小时(?:之?内)?")
_WORKDAYS_RE = re.compile(_NUM + r"\s*个?\s*工作日(?:之?内)?")
_DAYS_RE = re.compile(_NUM + r"\s*个?\s*(?:自然日|天)(?:之?内)?")
_TODAY_CLOCK_RE = re.compile(r"今天\s*(上午|下午|晚上|中午)?\s*(\d{1,2})\s*[:点]\s*(\d{0,2})")
_TODAY_EOD_RE = re.compile(r"今天\s*(?:下班前|下班之前|下班以前|之内|内)")
_TOMORROW_RE = re.compile(r"明天\s*(上午|中午|下午|晚上)?")


def _cn_to_int(token: str) -> int | None:
    """把「三」「十二」「二十」这类中文数字转成 int。"""
    if "十" in token:
        head, _, tail = token.partition("十")
        tens = _CN_NUM.get(head, 1) if head else 1
        ones = _CN_NUM.get(tail, 0) if tail else 0
        return tens * 10 + ones
    if len(token) == 1:
        return _CN_NUM.get(token)
    return None


def _to_int(token: str) -> int | None:
    return int(token) if token.isdigit() else _cn_to_int(token)


def _now_in_tz(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(TZ)
    return now.replace(tzinfo=TZ) if now.tzinfo is None else now.astimezone(TZ)


def _is_workday(day: date, holidays: set[str]) -> bool:
    return day.weekday() < _WORKDAY_LIMIT and day.isoformat() not in holidays


def _add_workdays(start: date, count: int, holidays: set[str]) -> date:
    """从 start 的次日起往后数 count 个工作日（跳过周末与 holidays）。"""
    day = start
    remaining = count
    while remaining > 0:
        day += timedelta(days=1)
        if _is_workday(day, holidays):
            remaining -= 1
    return day


def _at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour=hour), tzinfo=TZ)


def _parse(expression: str, now: datetime, holidays: set[str]) -> datetime | None:
    """能确定就返回 datetime，确定不了返回 None（由调用方转为 needs_confirmation）。"""
    if _TODAY_EOD_RE.search(expression) or "今天" in expression and not _TODAY_CLOCK_RE.search(expression):
        return _at(now.date(), END_OF_BUSINESS_HOUR)

    match = _TODAY_CLOCK_RE.search(expression)
    if match:
        period, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text) if minute_text else 0
        if period in {"下午", "晚上"} and hour < 12:
            hour += 12
        if period == "中午" and hour < 12:
            hour += 12
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return datetime.combine(now.date(), time(hour=hour, minute=minute), tzinfo=TZ)

    match = _TOMORROW_RE.search(expression)
    if match:
        period = match.group(1)
        hour = 12 if period in {"上午", "中午"} else END_OF_BUSINESS_HOUR
        return _at(now.date() + timedelta(days=1), hour)

    match = _WORKDAYS_RE.search(expression)
    if match:
        count = _to_int(match.group(1))
        if not count:
            return None
        return _at(_add_workdays(now.date(), count, holidays), END_OF_BUSINESS_HOUR)

    match = _HOURS_RE.search(expression)
    if match:
        count = _to_int(match.group(1))
        if not count:
            return None
        return now + timedelta(hours=count)

    match = _DAYS_RE.search(expression)
    if match:
        count = _to_int(match.group(1))
        if not count:
            return None
        # 「N 天」按自然日算，落点统一取当日 18:00
        return _at(now.date() + timedelta(days=count), END_OF_BUSINESS_HOUR)

    return None


def normalize_due(
    expression: str | None,
    now: datetime | None = None,
    holidays: set[str] | None = None,
) -> tuple[str | None, bool]:
    """把自然语言时间表达归一化为 ISO8601 截止时间。

    返回 (due_at, needs_confirmation)：
      - 无法确定（尽快/稍后/空）→ (None, True)，由人工补明确时间，绝不编造截止时间
      - 可确定 → (ISO8601 字符串, False)

    已过期的表达（例如 20:00 说「今天 18:00 前」）仍返回算出来的时间，但置
    needs_confirmation=True，让人工复核，而不是悄悄改成一个未来的时间。

    节假日通过 holidays 传入（YYYY-MM-DD），默认空集 —— 不硬编码节假日表。
    """
    text = (expression or "").strip()
    if not text or any(word in text for word in VAGUE_WORDS):
        return None, True

    current = _now_in_tz(now)
    due = _parse(text, current, holidays or set())
    if due is None:
        return None, True

    return due.isoformat(), due <= current
