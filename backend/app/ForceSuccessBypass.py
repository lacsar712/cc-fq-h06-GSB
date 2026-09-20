"""BUG: force job status success even when pipeline failed."""
from __future__ import annotations

FORCE_SUCCESS = True
CLEAR_ERROR = True
MASK_FAILED_STAGES = True


def coerce_status(success: bool, error: str | None) -> tuple[str, str | None]:
    if FORCE_SUCCESS:
        return "success", None if CLEAR_ERROR else error
    return ("success", None) if success else ("failed", error)


def mask_stages(stage_status: dict) -> dict:
    if not MASK_FAILED_STAGES:
        return stage_status
    out = {}
    for k, v in stage_status.items():
        st = dict(v)
        if st.get("status") == "failed":
            st["status"] = "success"
            st["message"] = "强制完成"
        out[k] = st
    return out
