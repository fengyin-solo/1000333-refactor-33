"""运维承包商业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "contractor"
REQUIRED_FIELDS = ["承包商编码", "承包商名称", "资质等级"]
STATUS_ORDER = ["待审核", "合作中", "已暂停", "已终止"]
ACTION_RULES = {"审核承包商": "合作中", "暂停合作": "已暂停", "终止合作": "已终止"}
NEGATIVE_ACTIONS = []


def qualification_expired(entry: dict[str, Any], *, today: date | None = None) -> bool:
    """资质到期统一口径：审核承包商、暂停合作、终止合作都走这一份判断。

    以合同到期日为准：可识别的到期日（YYYY-MM-DD）当天及以前视为已到期；
    合同到期日缺失或不是可识别日期（如示例占位文本）时按未到期处理，
    不误伤在途档案。后续调整口径（例如上线新资质等级）只改这里一处。
    """
    raw = str(entry.get("合同到期日") or "").strip()
    if not raw:
        return False
    try:
        due = date.fromisoformat(raw)
    except ValueError:
        return False
    return due <= (today or date.today())


class ContractorService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("承包商编码", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"承包商档案 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于运维承包商可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        message = f"承包商档案已{action}"
        if qualification_expired(entry):
            message += "；资质已到期，请尽快复核合同到期日"
        return entry, message
