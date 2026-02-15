from django.contrib import admin

from .models import Ats, Branch, Device, DeviceNeighbor, DevicePort, DeviceModel, Vendor

admin.site.register(Device)
admin.site.register(Vendor)
admin.site.register(DeviceModel)
admin.site.register(Branch)
admin.site.register(DevicePort)
admin.site.register(DeviceNeighbor)
admin.site.register(Ats)
