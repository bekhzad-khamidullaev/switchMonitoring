"""
Unit tests for SNMP models.
Tests model creation, validation, and relationships.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

from snmp.models import (
    ATS, Branch, HostGroup, Switch, SwitchPort,
    SwitchNeighbor, SwitchModel, BandwidthSample
)
from users.models import UserProfile

User = get_user_model()


class ATSModelTest(TestCase):
    """Test ATS model."""
    
    def setUp(self):
        self.ats = ATS.objects.create(
            name='Test ATS',
            code='ATS001',
            subnet='192.168.1.0/24',
            description='Test ATS Description'
        )
    
    def test_ats_creation(self):
        """Test ATS is created correctly."""
        self.assertEqual(self.ats.name, 'Test ATS')
        self.assertEqual(self.ats.code, 'ATS001')
        self.assertIsNotNone(self.ats.created_at)
    
    def test_ats_string_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.ats), 'Test ATS')
    
    def test_ats_unique_code(self):
        """Test that ATS code must be unique."""
        with self.assertRaises(Exception):
            ATS.objects.create(
                name='Another ATS',
                code='ATS001',  # Duplicate code
                subnet='192.168.2.0/24'
            )


class BranchModelTest(TestCase):
    """Test Branch model."""
    
    def setUp(self):
        self.ats = ATS.objects.create(
            name='Test ATS',
            code='ATS001',
            subnet='192.168.1.0/24'
        )
        self.branch = Branch.objects.create(
            name='Test Branch',
            code='BR001',
            ats=self.ats,
            address='Test Address',
            latitude=Decimal('41.2995'),
            longitude=Decimal('69.2401'),
            is_active=True
        )
    
    def test_branch_creation(self):
        """Test Branch is created correctly."""
        self.assertEqual(self.branch.name, 'Test Branch')
        self.assertEqual(self.branch.ats, self.ats)
        self.assertTrue(self.branch.is_active)
    
    def test_branch_ats_relationship(self):
        """Test Branch-ATS relationship."""
        self.assertEqual(self.branch.ats.name, 'Test ATS')
        self.assertIn(self.branch, self.ats.branch_set.all())


class HostGroupModelTest(TestCase):
    """Test HostGroup model."""
    
    def setUp(self):
        self.root_group = HostGroup.objects.create(
            name='Root Group',
            level=0
        )
        self.child_group = HostGroup.objects.create(
            name='Child Group',
            parent=self.root_group,
            level=1
        )
    
    def test_hostgroup_hierarchy(self):
        """Test hierarchical structure."""
        self.assertIsNone(self.root_group.parent)
        self.assertEqual(self.child_group.parent, self.root_group)
        self.assertIn(self.child_group, self.root_group.children.all())
    
    def test_hostgroup_levels(self):
        """Test group levels."""
        self.assertEqual(self.root_group.level, 0)
        self.assertEqual(self.child_group.level, 1)


class SwitchModelModelTest(TestCase):
    """Test SwitchModel model."""
    
    def setUp(self):
        self.switch_model = SwitchModel.objects.create(
            vendor='Cisco',
            model='Catalyst 2960',
            max_ports=48,
            description='Test switch model'
        )
    
    def test_switch_model_creation(self):
        """Test SwitchModel creation."""
        self.assertEqual(self.switch_model.vendor, 'Cisco')
        self.assertEqual(self.switch_model.model, 'Catalyst 2960')
        self.assertEqual(self.switch_model.max_ports, 48)
    
    def test_switch_model_string(self):
        """Test string representation."""
        expected = 'Cisco Catalyst 2960'
        self.assertEqual(str(self.switch_model), expected)


class SwitchModelTest(TestCase):
    """Test Switch model."""
    
    def setUp(self):
        self.ats = ATS.objects.create(
            name='Test ATS',
            code='ATS001',
            subnet='192.168.1.0/24'
        )
        self.branch = Branch.objects.create(
            name='Test Branch',
            code='BR001',
            ats=self.ats
        )
        self.host_group = HostGroup.objects.create(
            name='Test Group',
            level=0
        )
        self.device_model = SwitchModel.objects.create(
            vendor='Cisco',
            model='Catalyst 2960',
            max_ports=48
        )
        self.switch = Switch.objects.create(
            name='Test Switch',
            ip_address='192.168.1.1',
            mac_address='00:11:22:33:44:55',
            ats=self.ats,
            branch=self.branch,
            host_group=self.host_group,
            device_model=self.device_model,
            status='online',
            snmp_community_ro='public',
            snmp_version='2c',
            is_active=True,
            is_monitored=True
        )
    
    def test_switch_creation(self):
        """Test Switch creation."""
        self.assertEqual(self.switch.name, 'Test Switch')
        self.assertEqual(self.switch.ip_address, '192.168.1.1')
        self.assertEqual(self.switch.status, 'online')
    
    def test_switch_relationships(self):
        """Test Switch relationships."""
        self.assertEqual(self.switch.ats, self.ats)
        self.assertEqual(self.switch.branch, self.branch)
        self.assertEqual(self.switch.host_group, self.host_group)
        self.assertEqual(self.switch.device_model, self.device_model)
    
    def test_switch_unique_ip(self):
        """Test IP address uniqueness."""
        with self.assertRaises(Exception):
            Switch.objects.create(
                name='Another Switch',
                ip_address='192.168.1.1',  # Duplicate IP
                ats=self.ats,
                branch=self.branch
            )
    
    def test_switch_status_choices(self):
        """Test status field choices."""
        valid_statuses = ['online', 'offline', 'error', 'unknown']
        for status in valid_statuses:
            self.switch.status = status
            self.switch.save()
            self.assertEqual(self.switch.status, status)


class SwitchPortModelTest(TestCase):
    """Test SwitchPort model."""
    
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
            speed=1000,
            vlan=100
        )
    
    def test_port_creation(self):
        """Test port creation."""
        self.assertEqual(self.port.port_name, 'GigabitEthernet0/1')
        self.assertEqual(self.port.switch, self.switch)
        self.assertEqual(self.port.status, 'up')
    
    def test_port_types(self):
        """Test port type choices."""
        valid_types = ['access', 'trunk', 'uplink', 'downlink', 'sfp']
        for port_type in valid_types:
            self.port.port_type = port_type
            self.port.save()
            self.assertEqual(self.port.port_type, port_type)
    
    def test_port_switch_relationship(self):
        """Test port-switch relationship."""
        self.assertIn(self.port, self.switch.switchport_set.all())


class SwitchNeighborModelTest(TestCase):
    """Test SwitchNeighbor model."""
    
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
            port_name='GigabitEthernet0/1'
        )
        self.neighbor = SwitchNeighbor.objects.create(
            switch=self.switch,
            port=self.port,
            neighbor_device_id='Switch2',
            neighbor_system_name='Test Switch 2',
            protocol='lldp'
        )
    
    def test_neighbor_creation(self):
        """Test neighbor creation."""
        self.assertEqual(self.neighbor.neighbor_system_name, 'Test Switch 2')
        self.assertEqual(self.neighbor.protocol, 'lldp')
    
    def test_neighbor_relationships(self):
        """Test neighbor relationships."""
        self.assertEqual(self.neighbor.switch, self.switch)
        self.assertEqual(self.neighbor.port, self.port)


class BandwidthSampleModelTest(TestCase):
    """Test BandwidthSample model."""
    
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
            speed=1000
        )
        self.sample = BandwidthSample.objects.create(
            switch=self.switch,
            port=self.port,
            in_octets=1000000,
            out_octets=2000000,
            in_bps=8000000,
            out_bps=16000000,
            in_utilization=0.8,
            out_utilization=1.6
        )
    
    def test_bandwidth_sample_creation(self):
        """Test bandwidth sample creation."""
        self.assertEqual(self.sample.in_octets, 1000000)
        self.assertEqual(self.sample.out_octets, 2000000)
        self.assertIsNotNone(self.sample.timestamp)
    
    def test_bandwidth_utilization(self):
        """Test utilization calculation."""
        self.assertEqual(self.sample.in_utilization, 0.8)
        self.assertEqual(self.sample.out_utilization, 1.6)


class UserProfileModelTest(TestCase):
    """Test UserProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            phone='+998901234567',
            position='Network Engineer',
            department='IT'
        )
    
    def test_profile_creation(self):
        """Test profile creation."""
        self.assertEqual(self.profile.user, self.user)
        self.assertEqual(self.profile.position, 'Network Engineer')
    
    def test_profile_user_relationship(self):
        """Test profile-user relationship."""
        self.assertEqual(self.user.userprofile, self.profile)
