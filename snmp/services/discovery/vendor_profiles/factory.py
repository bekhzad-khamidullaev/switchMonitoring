from __future__ import annotations

from typing import Type

from .base import BaseVendorProfile
from .dlink import DlinkVendorProfile
from .extreme import ExtremeVendorProfile
from .h3c import H3cVendorProfile
from .huawei import HuaweiVendorProfile
from .threecom import ThreeComVendorProfile


class VendorProfileNotFound(LookupError):
    pass


_PROFILES: tuple[Type[BaseVendorProfile], ...] = (
    HuaweiVendorProfile,
    H3cVendorProfile,
    DlinkVendorProfile,
    ExtremeVendorProfile,
    ThreeComVendorProfile,
)


def get_vendor_profile(
    vendor: str,
    model: str,
    firmware: str,
    sys_object_id: str,
    sys_descr: str,
) -> BaseVendorProfile:
    for profile_class in _PROFILES:
        if profile_class.supports(
            vendor=vendor,
            model=model,
            firmware=firmware,
            sys_object_id=sys_object_id,
            sys_descr=sys_descr,
        ):
            return profile_class()
    if BaseVendorProfile.supports(
        vendor=vendor,
        model=model,
        firmware=firmware,
        sys_object_id=sys_object_id,
        sys_descr=sys_descr,
    ):
        return BaseVendorProfile()
    raise VendorProfileNotFound(f'No exact vendor profile for vendor={vendor!r}, model={model!r}')
