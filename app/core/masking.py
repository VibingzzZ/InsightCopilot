# 脱敏工具：API 不返回支付宝账号、手机号、详细地址、物流号原值
#
# 原则：运行库只保存掩码值；本模块负责导入阶段的掩码计算与引用文本的安全处理。

import hashlib
import re

# 物流号掩码：保留前 3 后 4
_TRACKING_RE = re.compile(r"^([A-Za-z0-9]{3})[A-Za-z0-9]+([A-Za-z0-9]{4})$")
# 手机号：11 位中国大陆号码
_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# 邮箱
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

HIDDEN = "已隐藏"


def hash_nickname(nickname: str) -> str:
    """规范化昵称哈希，用于跨会话归并，不可反推原值。"""
    normalized = (nickname or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def mask_display_name(name: str) -> str:
    """展示名掩码：保留首字符，如“魏h**”仅由官方脱敏源直接提供。

    对于新数据：保留首字符并补齐两位掩码。
    """
    if not name:
        return "用户**"
    head = name[0]
    return f"{head}**"


def mask_tracking_no(value: str | None) -> str:
    if not value:
        return HIDDEN
    compact = value.strip()
    match = _TRACKING_RE.match(compact)
    if match:
        return f"{match.group(1)}****{match.group(2)}"
    if len(compact) <= 4:
        return compact[0] + "*" * max(len(compact) - 1, 1)
    return compact[:2] + "*" * 4 + compact[-2:]


def mask_phone(value: str | None) -> str:
    if not value:
        return HIDDEN
    compact = value.strip()
    if len(compact) >= 11:
        return compact[:3] + "****" + compact[-4:]
    return compact[:2] + "****"


def mask_alipay_account(value: str | None) -> str:
    if not value:
        return HIDDEN
    compact = value.strip()
    if len(compact) <= 4:
        return compact[0] + "***"
    return compact[:2] + "***" + compact[-2:]


def redact_sensitive_text(text: str | None) -> str | None:
    """兜底清洗：引用文本中如混入手机号或邮箱，替换为掩码。"""
    if not text:
        return text
    cleaned = _PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], text)
    cleaned = _EMAIL_RE.sub("***@***", cleaned)
    return cleaned


def mask_quote(text: str | None, max_len: int = 40) -> str | None:
    """证据短引文：压缩空白、截断并做兜底脱敏。"""
    if not text:
        return None
    compact = re.sub(r"\s+", " ", text).strip()
    redacted = redact_sensitive_text(compact) or compact
    if len(redacted) > max_len:
        return redacted[: max_len - 1] + "…"
    return redacted
