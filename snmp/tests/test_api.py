"""
Integration tests for SNMP API endpoints.
Tests all API endpoints with authentication and permissions.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from decimal import Decimal

from snmp.models import (
    Ats as ATS, Branch, HostGroup, Switch, Interface as SwitchPort,
    NeighborLink as SwitchNeighbor, SwitchModel, InterfaceBandwidthSample as BandwidthSample
)
from users.models import UserProfile

User = get_user_model()


class BaseAPITestCase(APITestCase):
    """Base class for API tests with common setup."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        self.normal_user = User.objects.create_user(
            username='user',
            email='user@example.com',
            password='user123'
        )
        
        # Create profiles
        UserProfile.objects.create(user=self.admin_user)
        UserProfile.objects.create(user=self.normal_user)
        
        # Create test data
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
            is_active=True
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
            is_active=True
        )
        
        self.port = SwitchPort.objects.create(
            switch=self.switch,
            port_index=1,
            port_name='GigabitEthernet0/1',
            port_type='access',
            status='up',
            speed=1000
        )
        
        self.client = APIClient()
    
    def authenticate_admin(self):
        """Authenticate as admin user."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return token
    
    def authenticate_user(self):
        """Authenticate as normal user."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'user',
            'password': 'user123'
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return token


class AuthenticationAPITest(BaseAPITestCase):
    """Test authentication endpoints."""
    
    def test_token_obtain(self):
        """Test obtaining JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_token_obtain_invalid_credentials(self):
        """Test token obtain with invalid credentials."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh(self):
        """Test refreshing JWT token."""
        # Get initial token
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'admin',
            'password': 'admin123'
        })
        refresh_token = response.data['refresh']
        
        # Refresh token
        response = self.client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication."""
        response = self.client.get('/api/v1/switches/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_protected_endpoint_with_auth(self):
        """Test accessing protected endpoint with authentication."""
        self.authenticate_admin()
        response = self.client.get('/api/v1/switches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ATSAPITest(BaseAPITestCase):
    """Test ATS API endpoints."""
    
    def test_list_ats(self):
        """Test listing ATS."""
        self.authenticate_user()
        response = self.client.get('/api/v1/ats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_retrieve_ats(self):
        """Test retrieving single ATS."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/ats/{self.ats.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test ATS')
    
    def test_create_ats_as_admin(self):
        """Test creating ATS as admin."""
        self.authenticate_admin()
        data = {
            'name': 'New ATS',
            'code': 'ATS002',
            'subnet': '192.168.2.0/24',
            'description': 'New ATS Description'
        }
        response = self.client.post('/api/v1/ats/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New ATS')
    
    def test_create_ats_as_user(self):
        """Test creating ATS as normal user (should fail)."""
        self.authenticate_user()
        data = {
            'name': 'New ATS',
            'code': 'ATS002',
            'subnet': '192.168.2.0/24'
        }
        response = self.client.post('/api/v1/ats/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_ats(self):
        """Test updating ATS."""
        self.authenticate_admin()
        data = {'description': 'Updated description'}
        response = self.client.patch(f'/api/v1/ats/{self.ats.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated description')
    
    def test_delete_ats(self):
        """Test deleting ATS."""
        self.authenticate_admin()
        ats = ATS.objects.create(name='To Delete', code='DEL001', subnet='10.0.0.0/24')
        response = self.client.delete(f'/api/v1/ats/{ats.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ATS.objects.filter(id=ats.id).exists())


class SwitchAPITest(BaseAPITestCase):
    """Test Switch API endpoints."""
    
    def test_list_switches(self):
        """Test listing switches."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_retrieve_switch(self):
        """Test retrieving single switch."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/switches/{self.switch.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Switch')
        self.assertEqual(response.data['ip_address'], '192.168.1.1')
    
    def test_create_switch(self):
        """Test creating switch."""
        self.authenticate_admin()
        data = {
            'name': 'New Switch',
            'ip_address': '192.168.1.2',
            'mac_address': '00:11:22:33:44:66',
            'ats': self.ats.id,
            'branch': self.branch.id,
            'host_group': self.host_group.id,
            'device_model': self.device_model.id,
            'snmp_community_ro': 'public',
            'snmp_version': '2c',
            'is_active': True
        }
        response = self.client.post('/api/v1/switches/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Switch')
    
    def test_create_switch_duplicate_ip(self):
        """Test creating switch with duplicate IP."""
        self.authenticate_admin()
        data = {
            'name': 'Duplicate Switch',
            'ip_address': '192.168.1.1',  # Duplicate
            'ats': self.ats.id,
            'branch': self.branch.id
        }
        response = self.client.post('/api/v1/switches/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_switch(self):
        """Test updating switch."""
        self.authenticate_admin()
        data = {'description': 'Updated switch description'}
        response = self.client.patch(f'/api/v1/switches/{self.switch.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_switches_by_status(self):
        """Test filtering switches by status."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/?status=online')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for switch in response.data['results']:
            self.assertEqual(switch['status'], 'online')
    
    def test_search_switches(self):
        """Test searching switches."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/?search=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_switch_statistics(self):
        """Test switch statistics endpoint."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total', response.data)
        self.assertIn('online', response.data)
    
    def test_switch_ports_endpoint(self):
        """Test getting switch ports."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/switches/{self.switch.id}/ports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class SwitchPortAPITest(BaseAPITestCase):
    """Test SwitchPort API endpoints."""
    
    def test_list_ports(self):
        """Test listing ports."""
        self.authenticate_user()
        response = self.client.get('/api/v1/ports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_port(self):
        """Test retrieving single port."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/ports/{self.port.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['port_name'], 'GigabitEthernet0/1')
    
    def test_filter_ports_by_switch(self):
        """Test filtering ports by switch."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/ports/?switch={self.switch.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_ports_by_status(self):
        """Test filtering ports by status."""
        self.authenticate_user()
        response = self.client.get('/api/v1/ports/?status=up')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BranchAPITest(BaseAPITestCase):
    """Test Branch API endpoints."""
    
    def test_list_branches(self):
        """Test listing branches."""
        self.authenticate_user()
        response = self.client.get('/api/v1/branches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_branch(self):
        """Test retrieving single branch."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/branches/{self.branch.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Branch')
    
    def test_branch_switches_endpoint(self):
        """Test getting branch switches."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/branches/{self.branch.id}/switches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_branch_map_data(self):
        """Test getting map data."""
        self.authenticate_user()
        response = self.client.get('/api/v1/branches/map_data/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class DashboardAPITest(BaseAPITestCase):
    """Test Dashboard API endpoints."""
    
    def test_dashboard_statistics(self):
        """Test getting dashboard statistics."""
        self.authenticate_user()
        response = self.client.get('/api/v1/dashboard/statistics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_switches', response.data)
        self.assertIn('online_switches', response.data)
        self.assertIn('offline_switches', response.data)


class PaginationTest(BaseAPITestCase):
    """Test API pagination."""
    
    def setUp(self):
        super().setUp()
        # Create multiple switches
        for i in range(15):
            Switch.objects.create(
                name=f'Switch {i}',
                ip_address=f'192.168.1.{i+10}',
                ats=self.ats,
                branch=self.branch
            )
    
    def test_pagination_first_page(self):
        """Test first page of results."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/?page=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
    
    def test_pagination_page_size(self):
        """Test custom page size."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/?page_size=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 5)


class FilteringTest(BaseAPITestCase):
    """Test API filtering capabilities."""
    
    def setUp(self):
        super().setUp()
        # Create switches with different statuses
        Switch.objects.create(
            name='Offline Switch',
            ip_address='192.168.1.10',
            status='offline',
            ats=self.ats,
            branch=self.branch
        )
        Switch.objects.create(
            name='Error Switch',
            ip_address='192.168.1.11',
            status='error',
            ats=self.ats,
            branch=self.branch
        )
    
    def test_filter_by_status(self):
        """Test filtering by status."""
        self.authenticate_user()
        response = self.client.get('/api/v1/switches/?status=offline')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for switch in response.data['results']:
            self.assertEqual(switch['status'], 'offline')
    
    def test_filter_by_branch(self):
        """Test filtering by branch."""
        self.authenticate_user()
        response = self.client.get(f'/api/v1/switches/?branch={self.branch.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_multiple_filters(self):
        """Test using multiple filters."""
        self.authenticate_user()
        response = self.client.get(
            f'/api/v1/switches/?status=online&branch={self.branch.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PermissionsTest(BaseAPITestCase):
    """Test API permissions and access control."""
    
    def test_read_only_access_for_normal_user(self):
        """Test normal users have read-only access."""
        self.authenticate_user()
        
        # Can read
        response = self.client.get('/api/v1/switches/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cannot create
        response = self.client.post('/api/v1/switches/', {
            'name': 'New Switch',
            'ip_address': '192.168.1.100'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_full_access_for_admin(self):
        """Test admin users have full access."""
        self.authenticate_admin()
        
        # Can create
        data = {
            'name': 'Admin Switch',
            'ip_address': '192.168.1.200',
            'ats': self.ats.id,
            'branch': self.branch.id
        }
        response = self.client.post('/api/v1/switches/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
