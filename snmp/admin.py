from django.contrib import admin
from .models import (
    Ats,
    Branch,
    Interface,
    InterfaceL2,
    InterfaceOptics,
    MacEntry,
    NeighborLink,
    HostGroup,
    Switch,
    SwitchModel,
    SwitchStatus,
    Vendor,
)
admin.site.register(HostGroup)
admin.site.register(Switch)
admin.site.register(Vendor)
admin.site.register(SwitchModel)
admin.site.register(Branch)
admin.site.register(Interface)
admin.site.register(InterfaceOptics)
admin.site.register(InterfaceL2)
admin.site.register(MacEntry)
admin.site.register(NeighborLink)
admin.site.register(SwitchStatus)
admin.site.register(Ats)