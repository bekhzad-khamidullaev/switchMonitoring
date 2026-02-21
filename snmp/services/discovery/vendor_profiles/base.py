from __future__ import annotations

from typing import Any, Dict, List


class BaseVendorProfile:
    name = "generic"

    @classmethod
    def supports(
        cls,
        vendor: str,
        model: str,
        firmware: str,
        sys_object_id: str,
        sys_descr: str,
    ) -> bool:
        del model, firmware, sys_object_id, sys_descr
        return vendor.lower() == "generic"

    def enrich_interfaces(self, interfaces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return interfaces

