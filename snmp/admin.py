from django.contrib import admin

from .models import Ats, Branch, ManagedDevice, ManagedDevicePort, ManagedDeviceType, Vendor

admin.site.register(ManagedDevice)
admin.site.register(Vendor)
admin.site.register(ManagedDeviceType)
admin.site.register(Branch)
admin.site.register(ManagedDevicePort)
admin.site.register(Ats)
