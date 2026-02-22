from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseVendorProfile


class ThreeComVendorProfile(BaseVendorProfile):
    name = "3com"

    @classmethod
    def supports(
        cls,
        vendor: str,
        model: str,
        firmware: str,
        sys_object_id: str,
        sys_descr: str,
    ) -> bool:
        del model, firmware
        vendor = (vendor or "").lower()
        sys_object_id = (sys_object_id or "").strip()
        sys_descr = (sys_descr or "").lower()
        return (
            vendor == "3com"
            or sys_object_id.startswith("1.3.6.1.4.1.43.")
            or "3com" in sys_descr
        )

    def enrich_interfaces(self, interfaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for item in interfaces:
            current = dict(item)
            if_name = (current.get("if_name") or "").lower()
            if_type = str(current.get("if_type") or "")
            if current.get("is_optical") is False:
                current["is_optical"] = (
                    if_type in {"117"}
                    or "xgigabit" in if_name
                    or "ten-gigabit" in if_name
                )
            enriched.append(current)
        return enriched
