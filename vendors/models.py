from django.db import models
from ipaddress import ip_address, IPv4Network
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from snmp.models import Branch
from django.contrib.auth.models import Group

# @receiver(post_migrate)
# def create_branch_permissions(sender, **kwargs):
#     # This function creates custom permissions for each branch after migration

#     # Get the content type for the Branch model
#     content_type = ContentType.objects.get_for_model(Branch)

#     # Define the branches for which you want to create permissions
#     branches = Branch.objects.all()

#     # Create a permission for each branch
#     for branch in branches:
#         codename = f'view_{branch.name.lower().replace(" ", "_")}'
#         name = f'Can view hosts in {branch.name}'
#         permission, created = Permission.objects.get_or_create(
#             codename=codename,
#             name=name,
#             content_type=content_type,
#         )

#         # Optionally, assign the permission to a specific group
#         # For example, if you have a group named "Branch Managers"
#         # group = Group.objects.get(name='Branch Managers')
#         # group.permissions.add(permission)



# class Branch(models.Model):
#     name = models.CharField(max_length=200, null=True, blank=True)
    
#     class Meta:
#         managed = True
#         db_table = 'branchs'

#     def __str__(self):
#         return self.name


class SubnetAts(models.Model):
    name = models.CharField(max_length=200, default='')
    subnet = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True)

    class Meta:
        managed = True
        db_table = 'ats_list'


    def __str__(self):
        return self.name

    def contains_ip(self, address):
        """
        Check if the given IP address falls within the subnet range of this branch.
        """
        if self.subnet and address:
            try:
                subnet = IPv4Network(self.subnet)
                return ip_address(address) in subnet
            except ValueError:
                # Invalid subnet or IP address
                return False
        return False



class Vendor(models.Model):
    name = models.CharField(max_length=200)
    
    class Meta:
        managed = True
        db_table = 'vendor_list'


    def __str__(self):
        return self.name

class HostModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    model = models.CharField(max_length=200)
    sysHostName = models.CharField(max_length=200, null=True, blank=True)
    sysUpTime = models.CharField(max_length=200, null=True, blank=True)
    sysdescr = models.CharField(max_length=200, null=True, blank=True)
    temperatureStatus = models.CharField(max_length=200, null=True, blank=True)
    slot_oid = models.CharField(max_length=200, null=True, blank=True)
    sysObjectID = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'models'
        unique_together = (('vendor', 'model'),)
    
    
    def __str__(self):
        return self.model
