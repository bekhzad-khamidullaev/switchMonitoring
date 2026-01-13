from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from pysnmp.hlapi import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd,
    nextCmd,
)
from pysnmp.smi import builder, view


MibRef = Union[str, Tuple[str, str], Tuple[str, str, int], Tuple[str, str, int, int]]


@dataclass(frozen=True)
class SnmpTarget:
    host: str
    community: str
    port: int = 161
    timeout: int = 2
    retries: int = 1
    mp_model: int = 1  # SNMPv2c


def _parse_mib_ref(ref: MibRef) -> Tuple[ObjectIdentity, bool]:
    """Return (ObjectIdentity, is_scalar).

    Supported formats:
      - 'IF-MIB::ifSpeed.1' (instance suffix optional)
      - 'SNMPv2-MIB::sysName.0'
      - ('IF-MIB', 'ifSpeed', 1)
      - ('IF-MIB', 'ifSpeed')

    If instance suffix is present and ends with '.0' we treat as scalar.
    """
    if isinstance(ref, tuple):
        if len(ref) == 2:
            mod, sym = ref
            return ObjectIdentity(mod, sym), True
        mod, sym, *idx = ref
        return ObjectIdentity(mod, sym, *idx), False

    if '::' in ref:
        mod, rest = ref.split('::', 1)
        # instance suffix is after last '.' if numeric
        parts = rest.split('.')
        sym = parts[0]
        idx = [int(p) for p in parts[1:] if p.isdigit()]
        if idx:
            return ObjectIdentity(mod, sym, *idx), False
        return ObjectIdentity(mod, sym), True

    # numeric OID string fallback
    return ObjectIdentity(ref), False


@lru_cache(maxsize=1)
def _mib_view_controller() -> view.MibViewController:
    mib_builder = builder.MibBuilder()

    # Allow external MIBs to be placed in custom dirs.
    # MIB_DIRS may contain ':' separated list of directories.
    mib_dirs = os.getenv('MIB_DIRS', '')
    if mib_dirs:
        sources = [builder.DirMibSource(p) for p in mib_dirs.split(':') if p]
        if sources:
            mib_builder.setMibSources(*(mib_builder.getMibSources() + tuple(sources)))

    return view.MibViewController(mib_builder)


class SnmpClient:
    def __init__(self, target: SnmpTarget):
        self.target = target
        self.engine = SnmpEngine()
        self._mib_view = _mib_view_controller()

    def _transport(self):
        return UdpTransportTarget(
            (self.target.host, self.target.port),
            timeout=self.target.timeout,
            retries=self.target.retries,
        )

    def get_one(self, ref: MibRef) -> Optional[Any]:
        ident, _ = _parse_mib_ref(ref)
        try:
            ident.resolveWithMib(self._mib_view)
        except Exception:
            pass

        iterator = getCmd(
            self.engine,
            CommunityData(self.target.community, mpModel=self.target.mp_model),
            self._transport(),
            ContextData(),
            ObjectType(ident),
        )
        error_indication, error_status, error_index, var_binds = next(iterator)
        if error_indication or error_status:
            return None
        return var_binds[0][1]

    def get_many(self, refs: Sequence[MibRef]) -> Dict[str, Any]:
        obj_types = []
        keys = []
        for ref in refs:
            ident, _ = _parse_mib_ref(ref)
            try:
                ident.resolveWithMib(self._mib_view)
            except Exception:
                pass
            obj_types.append(ObjectType(ident))
            keys.append(str(ident))

        iterator = getCmd(
            self.engine,
            CommunityData(self.target.community, mpModel=self.target.mp_model),
            self._transport(),
            ContextData(),
            *obj_types,
        )
        error_indication, error_status, error_index, var_binds = next(iterator)
        if error_indication or error_status:
            return {}

        result = {}
        for name, val in var_binds:
            result[str(name)] = val
        return result

    def walk(self, base: MibRef, max_rows: int = 10000) -> Dict[str, Any]:
        """SNMP walk starting at base OID."""
        ident, _ = _parse_mib_ref(base)
        try:
            ident.resolveWithMib(self._mib_view)
        except Exception:
            pass
        base_obj = ObjectType(ident)

        out: Dict[str, Any] = {}
        for (error_indication, error_status, error_index, var_binds) in nextCmd(
            self.engine,
            CommunityData(self.target.community, mpModel=self.target.mp_model),
            self._transport(),
            ContextData(),
            base_obj,
            lexicographicMode=False,
        ):
            if error_indication or error_status:
                break
            for name, val in var_binds:
                out[str(name)] = val
            if len(out) >= max_rows:
                break
        return out
