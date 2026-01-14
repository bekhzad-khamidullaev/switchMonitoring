"""
Unit tests for API serializers.
Tests serialization and validation logic.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from snmp.models import (
    ATS, Branch, HostGroup, Switch, SwitchPort, SwitchModel
)
from snmp.api.serializers import (
    ATSSerializer, BranchSerializer, HostGroupSerializer,
    SwitchListSerializer, SwitchDetailSerializer,
    SwitchCreateUpdateSerializer, SwitchPortSerializer,
    SwitchModelSerializer
)

User = get_user_model()


class ATSSerializerTest(TestCase):
    """Test ATS serializer."""
    
    def setUp(self):
        self.ats = ATS.objects.create(
            name='Test ATS',
            code='ATS001',
            subnet='192.168.1.0/24'
        )
    
    def test_serialization(self):
        """Test serializing ATS."""
        serializer = ATSSerializer(self.ats)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test ATS')
        self.assertEqual(data['code'], 'ATS001')
        self.assertEqual(data['subnet'], '192.168.1.0/24')
    
    def test_deserialization(self):
        """Test deserializing ATS."""
        data = {
            'name': 'New ATS',
            'code': 'ATS002',
            'subnet': '192.168.2.0/24',
            'description': 'New ATS'
        }
        serializer = ATSSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        ats = serializer.save()
        self.assertEqual(ats.name, 'New ATS')


class SwitchSerializerTest(TestCase):
    """Test Switch serializers."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.host_group = HostGroup.objects.create(name='Test Group', level=0)
        self.device_model = SwitchModel.objects.create(
            vendor='Cisco',
            model='Catalyst 2960',
            max_ports=48
        )
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch,
            host_group=self.host_group,
            device_model=self.device_model,
            status='online'
        )
    
    def test_list_serialization(self):
        """Test list serializer."""
        serializer = SwitchListSerializer(self.switch)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Switch')
        self.assertEqual(data['ip_address'], '192.168.1.1')
        self.assertIn('ats_name', data)
        self.assertIn('branch_name', data)
    
    def test_detail_serialization(self):
        """Test detail serializer with nested data."""
        serializer = SwitchDetailSerializer(self.switch)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Test Switch')
        self.assertIsInstance(data['ats'], dict)
        self.assertIsInstance(data['branch'], dict)
        self.assertIn('ports', data)
    
    def test_create_serialization(self):
        """Test create/update serializer."""
        data = {
            'name': 'New Switch',
            'ip_address': '192.168.1.2',
            'ats': self.ats.id,
            'branch': self.branch.id,
            'host_group': self.host_group.id,
            'device_model': self.device_model.id,
            'snmp_community_ro': 'public',
            'snmp_version': '2c'
        }
        serializer = SwitchCreateUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        switch = serializer.save()
        self.assertEqual(switch.name, 'New Switch')
    
    def test_ip_validation(self):
        """Test IP address validation."""
        data = {
            'name': 'Invalid Switch',
            'ip_address': 'invalid-ip',
            'ats': self.ats.id,
            'branch': self.branch.id
        }
        serializer = SwitchCreateUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip_address', serializer.errors)
    
    def test_duplicate_ip_validation(self):
        """Test duplicate IP validation."""
        data = {
            'name': 'Duplicate Switch',
            'ip_address': '192.168.1.1',  # Duplicate
            'ats': self.ats.id,
            'branch': self.branch.id
        }
        serializer = SwitchCreateUpdateSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class SwitchPortSerializerTest(TestCase):
    """Test SwitchPort serializer."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch
        )
        self.port = SwitchPort.objects.create(
            switch=self.switch,
            port_index=1,
            port_name='GigabitEthernet0/1',
            port_type='access',
            status='up',
            speed=1000
        )
    
    def test_serialization(self):
        """Test port serialization."""
        serializer = SwitchPortSerializer(self.port)
        data = serializer.data
        
        self.assertEqual(data['port_name'], 'GigabitEthernet0/1')
        self.assertEqual(data['status'], 'up')
        self.assertIn('switch_name', data)


class NestedSerializerTest(TestCase):
    """Test nested serialization."""
    
    def setUp(self):
        self.ats = ATS.objects.create(name='Test ATS', code='ATS001', subnet='192.168.1.0/24')
        self.branch = Branch.objects.create(name='Test Branch', code='BR001', ats=self.ats)
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            ats=self.ats,
            branch=self.branch
        )
        # Create ports
        for i in range(3):
            SwitchPort.objects.create(
                switch=self.switch,
                port_index=i+1,
                port_name=f'Port{i+1}',
                status='up'
            )
    
    def test_switch_with_ports(self):
        """Test switch serialization with nested ports."""
        serializer = SwitchDetailSerializer(self.switch)
        data = serializer.data
        
        self.assertIn('ports', data)
        self.assertEqual(len(data['ports']), 3)
        self.assertIsInstance(data['ports'][0], dict)
