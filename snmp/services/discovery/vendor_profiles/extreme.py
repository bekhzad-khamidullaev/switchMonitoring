from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseVendorProfile


class ExtremeVendorProfile(BaseVendorProfile):
    name = "extreme"

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
            "extreme" in vendor
            or sys_object_id.startswith("1.3.6.1.4.1.1916.")
            or sys_object_id.startswith("1.3.6.1.4.1.2272.")
            or "extreme" in sys_descr
            or "xos" in sys_descr
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
                    or "10g" in if_name
                    or "40g" in if_name
                    or "100g" in if_name
                    or "fiber" in if_name
                )
            enriched.append(current)
        return enriched
