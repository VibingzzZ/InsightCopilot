"""时间归一化测试。

必须覆盖文档点名的「3 个工作日 ≠ 72 小时」—— 两者在跨周末时结果不同。
"""

from datetime import datetime

import pytest

from app.agent.time import normalize_due

# 2026-09-24 是星期四，往后数 3 个工作日会跨过周末，正好用来说明问题
THURSDAY = datetime(2026, 9, 24, 10, 0)


def test_tomorrow_morning():
    due_at, needs_confirmation = normalize_due("明天上午", now=THURSDAY)

    assert due_at == "2026-09-25T12:00:00+08:00"
    assert needs_confirmation is False


def test_tomorrow_defaults_to_end_of_business():
    due_at, _ = normalize_due("明天", now=THURSDAY)

    assert due_at == "2026-09-25T18:00:00+08:00"


def test_workdays_skip_weekend():
    # 周五、周一、周二 → 9/29
    due_at, needs_confirmation = normalize_due("3 个工作日", now=THURSDAY)

    assert due_at == "2026-09-29T18:00:00+08:00"
    assert needs_confirmation is False


def test_workdays_skip_holidays():
    due_at, _ = normalize_due("3个工作日", now=THURSDAY, holidays={"2026-09-25"})

    # 周五被假期跳过 → 周一、周二、周三
    assert due_at == "2026-09-30T18:00:00+08:00"


def test_workdays_differ_from_hours():
    """同样是「三天」，按工作日和按小时算出来必须不是同一个时间。"""
    workdays, _ = normalize_due("3个工作日", now=THURSDAY)
    hours, _ = normalize_due("72小时", now=THURSDAY)

    assert workdays != hours
    assert hours == "2026-09-27T10:00:00+08:00"


def test_hours():
    due_at, needs_confirmation = normalize_due("48小时内", now=THURSDAY)

    assert due_at == "2026-09-26T10:00:00+08:00"
    assert needs_confirmation is False


def test_natural_days_land_on_end_of_business():
    due_at, _ = normalize_due("2天", now=THURSDAY)

    assert due_at == "2026-09-26T18:00:00+08:00"


def test_today_clock():
    due_at, _ = normalize_due("今天18:00前", now=THURSDAY)

    assert due_at == "2026-09-24T18:00:00+08:00"


def test_today_afternoon_clock():
    due_at, _ = normalize_due("今天下午3点", now=THURSDAY)

    assert due_at == "2026-09-24T15:00:00+08:00"


def test_today_end_of_business():
    due_at, _ = normalize_due("今天下班前", now=THURSDAY)

    assert due_at == "2026-09-24T18:00:00+08:00"


@pytest.mark.parametrize("expression", ["尽快", "稍后", "有空再说", "", None])
def test_vague_expression_needs_confirmation(expression):
    """模糊表达一律不编造截止时间，交人工确认。"""
    assert normalize_due(expression, now=THURSDAY) == (None, True)


def test_already_passed_time_needs_confirmation():
    """20 点说「今天 18:00 前」不能悄悄改成明天，只标记待确认。"""
    late = datetime(2026, 9, 24, 20, 0)
    due_at, needs_confirmation = normalize_due("今天18:00前", now=late)

    assert due_at == "2026-09-24T18:00:00+08:00"
    assert needs_confirmation is True
