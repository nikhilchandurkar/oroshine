"""
Base Test Configuration and Utilities
Provides common setup, fixtures, and helper methods for E2E tests
"""

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from oroshine_webapp.models import (
    UserProfile, Doctor, Service, Appointment,
    Contact, Newsletter, TIME_SLOTS
)


class BaseTestCase(TestCase):
    """Base test case with common fixtures and utilities"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data that won't be modified during tests"""
        
        # Create test users
        cls.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123!@#',
            first_name='Admin',
            last_name='User'
        )
        
        cls.regular_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            first_name='John',
            last_name='Doe'
        )
        
        cls.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='TestPass123!',
            first_name='Jane',
            last_name='Smith'
        )
        
        # Create user profiles or use it 
        cls.regular_profile = UserProfile.objects.get(user=cls.regular_user)

        
        # Create doctors
        cls.doctor1 = Doctor.objects.create(
            email='dr.smith@clinic.com',
            full_name='Smith Johnson',
            specialization='General Dentistry',
            is_active=True,
            display_order=1
        )
        
        cls.doctor2 = Doctor.objects.create(
            email='dr.patel@clinic.com',
            full_name='Amit Patel',
            specialization='Orthodontics',
            is_active=True,
            display_order=2
        )
        
        cls.inactive_doctor = Doctor.objects.create(
            email='dr.inactive@clinic.com',
            full_name='Inactive Doctor',
            specialization='Pediatric Dentistry',
            is_active=False,
            display_order=3
        )
        
        # Create services
        cls.service1 = Service.objects.create(
            name='Teeth Cleaning',
            code='teeth_cleaning',
            description='Professional teeth cleaning service',
            price=Decimal('1500.00'),
            duration_minutes=30,
            is_active=True,
            display_order=1,
            icon='fa-tooth',
            color='#007bff'
        )
        
        cls.service2 = Service.objects.create(
            name='Root Canal Treatment',
            code='root_canal',
            description='Root canal therapy',
            price=Decimal('5000.00'),
            duration_minutes=90,
            is_active=True,
            display_order=2,
            icon='fa-tooth',
            color='#dc3545'
        )
        
        cls.service3 = Service.objects.create(
            name='Teeth Whitening',
            code='teeth_whitening',
            description='Professional teeth whitening',
            price=Decimal('3000.00'),
            duration_minutes=60,
            is_active=True,
            display_order=3,
            icon='fa-smile',
            color='#28a745'
        )
        
        cls.inactive_service = Service.objects.create(
            name='Inactive Service',
            code='inactive_service',
            description='This service is no longer available',
            price=Decimal('1000.00'),
            duration_minutes=30,
            is_active=False,
            display_order=4
        )
    
    def setUp(self):
        """Set up for each test"""
        self.client = Client()
        
        # Clear cache before each test
        from django.core.cache import cache
        cache.clear()
    
    def create_appointment(self, user=None, service=None, doctor=None, 
                          date=None, time='10:00', status='pending', **kwargs):
        """Helper method to create appointments"""
        if user is None:
            user = self.regular_user
        if service is None:
            service = self.service1
        if doctor is None:
            doctor = self.doctor1
        if date is None:
            date = (timezone.now() + timedelta(days=7)).date()
        
        defaults = {
            'user': user,
            'service': service,
            'doctor': doctor,
            'name': kwargs.get('name', user.get_full_name() or user.username),
            'email': kwargs.get('email', user.email),
            'phone': kwargs.get('phone', '+919876543210'),
            'date': date,
            'time': time,
            'status': status,
            'message': kwargs.get('message', 'Test appointment')
        }
        defaults.update(kwargs)
        
        return Appointment.objects.create(**defaults)
    
    def create_contact(self, user=None, **kwargs):
        """Helper method to create contact submissions"""
        if user is None:
            user = self.regular_user
        
        defaults = {
            'user': user,
            'name': kwargs.get('name', user.get_full_name()),
            'email': kwargs.get('email', user.email),
            'subject': kwargs.get('subject', 'Test Subject'),
            'message': kwargs.get('message', 'Test message'),
            'is_resolved': kwargs.get('is_resolved', False)
        }
        
        return Contact.objects.create(**defaults)
    
    def login_user(self, username='testuser', password='TestPass123!'):
        """Helper method to log in a user"""
        return self.client.login(username=username, password=password)
    
    def login_admin(self):
        """Helper method to log in as admin"""
        return self.client.login(username='admin', password='admin123!@#')
    
    def assertResponseOK(self, response, status_code=200):
        """Assert response has expected status code"""
        self.assertEqual(
            response.status_code, 
            status_code,
            f"Expected {status_code} but got {response.status_code}. "
            f"Content: {response.content.decode()[:500]}"
        )
    
    def assertJSONResponse(self, response, expected_status='success'):
        """Assert JSON response has expected status"""
        self.assertEqual(response['Content-Type'], 'application/json')
        data = json.loads(response.content)
        self.assertEqual(data.get('status'), expected_status)
        return data
    
    def get_future_date(self, days=7):
        """Get a future date for appointments"""
        return (timezone.now() + timedelta(days=days)).date()
    
    def get_valid_time_slot(self):
        """Get a valid time slot"""
        return TIME_SLOTS[0][0]  # Returns first available slot


class BaseTransactionTestCase(TransactionTestCase):
    """
    Base test case for tests that require database transactions
    Use this for tests involving Celery tasks or complex transactions
    """
    
    def setUp(self):
        """Set up for each test"""
        self.client = Client()
        
        # Create basic test data
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123!@#'
        )
        
        self.regular_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            first_name='John',
            last_name='Doe'
        )
        
        self.doctor = Doctor.objects.create(
            email='dr.test@clinic.com',
            full_name='Test Doctor',
            specialization='General',
            is_active=True
        )
        
        self.service = Service.objects.create(
            name='Test Service',
            code='test_service',
            price=Decimal('1000.00'),
            duration_minutes=30,
            is_active=True
        )
        
        # Clear cache
        from django.core.cache import cache
        cache.clear()
    
    def login_user(self, username='testuser', password='TestPass123!'):
        """Helper method to log in a user"""
        return self.client.login(username=username, password=password)
    
    def login_admin(self):
        """Helper method to log in as admin"""
        return self.client.login(username='admin', password='admin123!@#')


# API Test Mixins
class APITestMixin:
    """Mixin for API endpoint testing"""
    
    def post_json(self, url, data, **kwargs):
        """POST JSON data to endpoint"""
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **kwargs
        )
    
    def get_json(self, url, data=None, **kwargs):
        """GET request expecting JSON response"""
        return self.client.get(url, data=data, **kwargs)
    
    def assert_json_error(self, response, status_code=400):
        """Assert JSON error response"""
        self.assertEqual(response.status_code, status_code)
        data = json.loads(response.content)
        self.assertEqual(data.get('status'), 'error')
        return data
    
    def assert_json_success(self, response):
        """Assert JSON success response"""
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data.get('status'), 'success')
        return data


# Form Test Mixin
class FormTestMixin:
    """Mixin for form testing utilities"""
    
    def get_valid_appointment_data(self, **overrides):
        """Get valid appointment form data"""
        data = {
            'service': self.service1.ulid,
            'doctor': self.doctor1.id,
            'name': 'Test Patient',
            'email': 'patient@test.com',
            'phone': '+919876543210',
            'date': self.get_future_date().isoformat(),
            'time': '10:00',
            'message': 'Test appointment message'
        }
        data.update(overrides)
        return data
    
    def get_valid_contact_data(self, **overrides):
        """Get valid contact form data"""
        data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'subject': 'Test Subject',
            'message': 'Test message content'
        }
        data.update(overrides)
        return data