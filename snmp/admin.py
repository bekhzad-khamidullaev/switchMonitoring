from django.contrib import admin
from .models import Node, ATS, Switch, SwitchPort, SwitchPortStats


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(ATS)
class ATSAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'node')
    search_fields = ('name', 'node__name')
    list_filter = ('node',)


@admin.register(Switch)
class SwitchAdmin(admin.ModelAdmin):
    list_display = ('id', 'hostname', 'ip', 'ats', 'status')
    search_fields = ('hostname', 'ip', 'ats__name', 'ats__node__name')
    list_filter = ('status', 'ats__node')


@admin.register(SwitchPort)
class SwitchPortAdmin(admin.ModelAdmin):
    list_display = ('id', 'switch', 'port_index', 'description', 'speed', 'admin_state', 'oper_state')
    search_fields = ('switch__hostname', 'description')
    list_filter = ('admin_state', 'oper_state')


@admin.register(SwitchPortStats)
class SwitchPortStatsAdmin(admin.ModelAdmin):
    list_display = ('id', 'port', 'timestamp', 'octets_in', 'octets_out')
    list_filter = ('timestamp', 'port__switch')
    readonly_fields = ('timestamp',)
