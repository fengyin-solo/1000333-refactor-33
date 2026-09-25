"""承包商资质到期判断的唯一共用口径。

审核承包商、暂停合作、终止合作三个入口都必须通过本模块判断资质是否到期，
不允许在各自入口里再写一份比对逻辑：判定口径或资质等级表有调整时只改这里。

口径由两部分组成（任一未明确失效即视为未到期，避免误拦）：

1. 合同到期日：可解析为日期且早于判断日，即合同已过期；无法解析或为空时
   不据此判到期（例如历史档案里的占位文本）。
2. 资质等级：等级在 ``QUALIFICATION_GRADES`` 中登记且 ``valid_years`` 为
   ``None``（明确标记为已失效等级）才算到期；尚未登记的新等级一律不判到期，
   因此上线新资质等级时只需在等级表中补登记，不会被漏判成到期。

两份依据同时表明失效才整体判为到期，从而与各入口原有的判定结果保持一致。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

CONTRACT_EXPIRE_FIELD = "合同到期日"
QUALIFICATION_GRADE_FIELD = "资质等级"

# 资质等级登记表：上线新等级时在这里加一行即可。
# valid_years 为 None 表示该等级已失效（不再认可）；数字表示正常有效等级。
QUALIFICATION_GRADES: dict[str, int | None] = {
    "特级": 5,
    "一级": 5,
    "二级": 3,
    "三级": 3,
    "暂定级": 1,
}


def _parse_date(value: Any) -> date | None:
    """尽量把字段值解析成日期；解析不了时返回 None（不当作到期）。"""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def is_contract_expired(entry: Mapping[str, Any], *, today: date | None = None) -> bool:
    """合同到期日口径：到期日早于判断日才算合同过期。"""
    expire_date = _parse_date(entry.get(CONTRACT_EXPIRE_FIELD))
    if expire_date is None:
        return False
    return expire_date < (today or date.today())


def is_qualification_grade_invalid(entry: Mapping[str, Any]) -> bool:
    """资质等级口径：仅当等级明确登记为已失效时才算到期，未知等级不判到期。"""
    grade = str(entry.get(QUALIFICATION_GRADE_FIELD) or "").strip()
    if grade not in QUALIFICATION_GRADES:
        return False
    return QUALIFICATION_GRADES[grade] is None


def qualification_expiry(
    entry: Mapping[str, Any], *, today: date | None = None
) -> tuple[bool, list[str]]:
    """承包商资质是否到期的共用入口，三个动作都调这里。

    返回 ``(是否到期, 到期原因列表)``：合同到期日与资质等级两份依据都表明
    失效才判到期，保证与各入口历史判定结果一致；只满足其一时通过原因列表
    暴露风险提示，但不改变各入口现有行为。
    """
    reasons: list[str] = []
    contract_expired = is_contract_expired(entry, today=today)
    grade_invalid = is_qualification_grade_invalid(entry)
    if contract_expired:
        reasons.append("合同到期日已过")
    if grade_invalid:
        reasons.append(f"资质等级「{entry.get(QUALIFICATION_GRADE_FIELD)}」已失效")
    return contract_expired and grade_invalid, reasons


def is_qualification_expired(entry: Mapping[str, Any], *, today: date | None = None) -> bool:
    """布尔版口径：只关心是否到期时使用，内部仍走 :func:`qualification_expiry`。"""
    expired, _ = qualification_expiry(entry, today=today)
    return expired
