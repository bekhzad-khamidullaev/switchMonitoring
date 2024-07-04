from django.contrib import admin
from .models import Branch, Vendor, SubnetAts, HostModel


admin.site.register(Branch)
admin.site.register(SubnetAts)
admin.site.register(Vendor)
admin.site.register(HostModel)