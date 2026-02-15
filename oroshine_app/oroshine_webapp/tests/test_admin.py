"""
End-to-End Tests for Django Admin Panel
Tests admin functionality for appointments, services, doctors, and contacts
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.utils import timezone
from decimal import Decimal

from oroshine_webapp.models import Appointment, Service, Doctor, Contact, UserProfile, Newsletter
from oroshine_webapp.admin import (
    AppointmentAdmin, ServiceAdmin, DoctorAdmin,
    ContactAdmin, UserProfileAdmin, NewsletterAdmin
)
from .test_base import BaseTestCase


class AdminAuthenticationE2ETests(BaseTestCase):
    """Tests for admin authentication and access control"""
    
    def test_admin_login_page_loads(self):
        """Test that admin login page loads"""
        url = reverse('admin:login')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django administration')
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        url = reverse('admin:login')
        
        login_data = {
            'username': 'admin',
            'password': 'admin123!@#',
            'next': '/admin/'
        }
        
        response = self.client.post(url, login_data)
        
        # Should redirect to admin index
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('/admin/'))
    
    def test_regular_user_cannot_access_admin(self):
        """Test that regular users cannot access admin panel"""
        # Login as regular user
        self.login_user()
        
        url = reverse('admin:index')
        response = self.client.get(url)
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_admin_index_page_loads(self):
        """Test that admin index page loads for admin user"""
        self.login_admin()
        
        url = reverse('admin:index')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site administration')


class AdminAppointmentManagementE2ETests(BaseTestCase):
    """Tests for managing appointments in admin panel"""
    
    def test_view_appointment_list(self):
        """Test viewing appointment list in admin"""
        self.login_admin()
        
        # Create test appointments
        appt1 = self.create_appointment(status='pending')
        appt2 = self.create_appointment(time='14:00', status='confirmed')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, appt1.name)
        self.assertContains(response, appt2.name)
    
    def test_view_appointment_detail(self):
        """Test viewing appointment detail in admin"""
        self.login_admin()
        
        appointment = self.create_appointment()
        
        url = reverse('admin:oroshine_webapp_appointment_change', args=[appointment.ulid])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, appointment.name)
        self.assertContains(response, appointment.email)
        self.assertContains(response, appointment.phone)
    
    def test_change_appointment_status_to_confirmed(self):
        """Test changing appointment status to confirmed"""
        self.login_admin()
        
        appointment = self.create_appointment(status='pending')
        
        url = reverse('admin:oroshine_webapp_appointment_change', args=[appointment.ulid])
        
        update_data = {
            'user': appointment.user.id,
            'service': appointment.service.ulid,
            'doctor': appointment.doctor.id,
            'name': appointment.name,
            'email': appointment.email,
            'phone': appointment.phone,
            'date': appointment.date.isoformat(),
            'time': appointment.time,
            'status': 'confirmed',
            'message': appointment.message or ''
        }
        
        response = self.client.post(url, update_data)
        
        # Verify status was changed
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'confirmed')
    
    def test_change_appointment_status_to_cancelled(self):
        """Test changing appointment status to cancelled"""
        self.login_admin()
        
        appointment = self.create_appointment(status='pending')
        
        url = reverse('admin:oroshine_webapp_appointment_change', args=[appointment.ulid])
        
        update_data = {
            'user': appointment.user.id,
            'service': appointment.service.ulid,
            'doctor': appointment.doctor.id,
            'name': appointment.name,
            'email': appointment.email,
            'phone': appointment.phone,
            'date': appointment.date.isoformat(),
            'time': appointment.time,
            'status': 'cancelled',
            'message': appointment.message or ''
        }
        
        response = self.client.post(url, update_data)
        
        # Verify status was changed
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'cancelled')
    
    def test_bulk_confirm_appointments(self):
        """Test bulk confirming appointments via admin action"""
        self.login_admin()
        
        # Create pending appointments
        appt1 = self.create_appointment(status='pending')
        appt2 = self.create_appointment(time='14:00', status='pending')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        
        action_data = {
            'action': 'mark_as_confirmed',
            '_selected_action': [appt1.ulid, appt2.ulid],
            'index': 0
        }
        
        response = self.client.post(url, action_data)
        
        # Verify appointments were confirmed
        appt1.refresh_from_db()
        appt2.refresh_from_db()
        self.assertEqual(appt1.status, 'confirmed')
        self.assertEqual(appt2.status, 'confirmed')
    
    def test_bulk_complete_appointments(self):
        """Test bulk completing appointments via admin action"""
        self.login_admin()
        
        # Create confirmed appointments
        appt1 = self.create_appointment(status='confirmed')
        appt2 = self.create_appointment(time='14:00', status='confirmed')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        
        action_data = {
            'action': 'mark_as_completed',
            '_selected_action': [appt1.ulid, appt2.ulid],
            'index': 0
        }
        
        response = self.client.post(url, action_data)
        
        # Verify appointments were completed
        appt1.refresh_from_db()
        appt2.refresh_from_db()
        self.assertEqual(appt1.status, 'completed')
        self.assertEqual(appt2.status, 'completed')
    
    def test_bulk_cancel_appointments(self):
        """Test bulk cancelling appointments via admin action"""
        self.login_admin()
        
        appt1 = self.create_appointment(status='pending')
        appt2 = self.create_appointment(time='12:00', status='pending')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        
        action_data = {
            'action': 'mark_as_cancelled',
            '_selected_action': [appt1.ulid, appt2.ulid],
            'index': 0
        }
        
        response = self.client.post(url, action_data)
        
        # Verify appointments were cancelled
        appt1.refresh_from_db()
        appt2.refresh_from_db()
        self.assertEqual(appt1.status, 'cancelled')
        self.assertEqual(appt2.status, 'cancelled')
    
    def test_filter_appointments_by_status(self):
        """Test filtering appointments by status in admin"""
        self.login_admin()
        
        # Create appointments with different statuses
        self.create_appointment(status='pending')
        self.create_appointment(time='14:00', status='confirmed')
        self.create_appointment(time='15:00', status='cancelled')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        
        # Filter by pending
        response = self.client.get(url + '?status=pending')
        self.assertEqual(response.status_code, 200)
        
        # Filter by confirmed
        response = self.client.get(url + '?status=confirmed')
        self.assertEqual(response.status_code, 200)
    
    def test_filter_appointments_by_date(self):
        """Test filtering appointments by date in admin"""
        self.login_admin()
        
        # Create appointments on different dates
        today = timezone.now().date()
        self.create_appointment(date=today + timezone.timedelta(days=1))
        self.create_appointment(date=today + timezone.timedelta(days=7), time='14:00')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_search_appointments_by_name(self):
        """Test searching appointments by patient name"""
        self.login_admin()
        
        appt1 = self.create_appointment(name='John Smith')
        appt2 = self.create_appointment(name='Jane Doe', time='14:00')
        
        url = reverse('admin:oroshine_webapp_appointment_changelist')
        
        # Search for John
        response = self.client.get(url + '?q=John')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Smith')


class AdminServiceManagementE2ETests(BaseTestCase):
    """Tests for managing services in admin panel"""
    
    def test_view_service_list(self):
        """Test viewing service list in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_service_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service1.name)
        self.assertContains(response, self.service2.name)
    
    def test_create_new_service(self):
        """Test creating a new service in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_service_add')
        
        service_data = {
            'name': 'Dental Implants',
            'code': 'dental_implants',
            'description': 'High-quality dental implants',
            'price': '15000.00',
            'duration_minutes': 120,
            'is_active': True,
            'display_order': 10,
            'icon': 'fa-tooth',
            'color': '#007bff'
        }
        
        response = self.client.post(url, service_data)
        
        # Verify service was created
        service = Service.objects.get(code='dental_implants')
        self.assertEqual(service.name, 'Dental Implants')
        self.assertEqual(service.price, Decimal('15000.00'))
        self.assertEqual(service.duration_minutes, 120)
    
    def test_update_service(self):
        """Test updating a service in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_service_change', args=[self.service1.ulid])
        
        update_data = {
            'name': 'Deep Teeth Cleaning',
            'code': self.service1.code,
            'description': 'Updated description',
            'price': '2000.00',
            'duration_minutes': 45,
            'is_active': True,
            'display_order': self.service1.display_order,
            'icon': self.service1.icon,
            'color': self.service1.color
        }
        
        response = self.client.post(url, update_data)
        
        # Verify service was updated
        self.service1.refresh_from_db()
        self.assertEqual(self.service1.name, 'Deep Teeth Cleaning')
        self.assertEqual(self.service1.price, Decimal('2000.00'))
    
    def test_deactivate_service(self):
        """Test deactivating a service"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_service_change', args=[self.service1.ulid])
        
        update_data = {
            'name': self.service1.name,
            'code': self.service1.code,
            'description': self.service1.description,
            'price': str(self.service1.price),
            'duration_minutes': self.service1.duration_minutes,
            'is_active': False,  # Deactivate
            'display_order': self.service1.display_order,
            'icon': self.service1.icon,
            'color': self.service1.color
        }
        
        response = self.client.post(url, update_data)
        
        # Verify service was deactivated
        self.service1.refresh_from_db()
        self.assertFalse(self.service1.is_active)
    
    def test_bulk_activate_services(self):
        """Test bulk activating services"""
        self.login_admin()
        
        # Make services inactive
        self.service1.is_active = False
        self.service1.save()
        self.service2.is_active = False
        self.service2.save()
        
        url = reverse('admin:oroshine_webapp_service_changelist')
        
        action_data = {
            'action': 'activate_services',
            '_selected_action': [self.service1.ulid, self.service2.ulid],
            'index': 0
        }
        
        response = self.client.post(url, action_data)
        
        # Verify services were activated
        self.service1.refresh_from_db()
        self.service2.refresh_from_db()
        self.assertTrue(self.service1.is_active)
        self.assertTrue(self.service2.is_active)


class AdminDoctorManagementE2ETests(BaseTestCase):
    """Tests for managing doctors in admin panel"""
    
    def test_view_doctor_list(self):
        """Test viewing doctor list in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_doctor_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.doctor1.full_name)
        self.assertContains(response, self.doctor2.full_name)
    
    def test_create_new_doctor(self):
        """Test creating a new doctor in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_doctor_add')
        
        doctor_data = {
            'email': 'dr.new@clinic.com',
            'full_name': 'New Doctor',
            'specialization': 'Cosmetic Dentistry',
            'is_active': True,
            'display_order': 5
        }
        
        response = self.client.post(url, doctor_data)
        
        # Verify doctor was created
        doctor = Doctor.objects.get(email='dr.new@clinic.com')
        self.assertEqual(doctor.full_name, 'New Doctor')
        self.assertEqual(doctor.specialization, 'Cosmetic Dentistry')
    
    def test_update_doctor_info(self):
        """Test updating doctor information"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_doctor_change', args=[self.doctor1.id])
        
        update_data = {
            'email': self.doctor1.email,
            'full_name': 'Smith Johnson Jr.',
            'specialization': 'Advanced General Dentistry',
            'is_active': True,
            'display_order': self.doctor1.display_order
        }
        
        response = self.client.post(url, update_data)
        
        # Verify doctor was updated
        self.doctor1.refresh_from_db()
        self.assertEqual(self.doctor1.full_name, 'Smith Johnson Jr.')
        self.assertEqual(self.doctor1.specialization, 'Advanced General Dentistry')
    
    def test_deactivate_doctor(self):
        """Test deactivating a doctor"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_doctor_change', args=[self.doctor1.id])
        
        update_data = {
            'email': self.doctor1.email,
            'full_name': self.doctor1.full_name,
            'specialization': self.doctor1.specialization,
            'is_active': False,  # Deactivate
            'display_order': self.doctor1.display_order
        }
        
        response = self.client.post(url, update_data)
        
        # Verify doctor was deactivated
        self.doctor1.refresh_from_db()
        self.assertFalse(self.doctor1.is_active)


class AdminContactManagementE2ETests(BaseTestCase):
    """Tests for managing contact submissions in admin panel"""
    
    def test_view_contact_list(self):
        """Test viewing contact list in admin"""
        self.login_admin()
        
        # Create contact submissions
        contact1 = self.create_contact()
        contact2 = self.create_contact(
            name='Another User',
            email='another@test.com'
        )
        
        url = reverse('admin:oroshine_webapp_contact_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contact1.name)
        self.assertContains(response, contact2.name)
    
    def test_view_contact_detail(self):
        """Test viewing contact detail in admin"""
        self.login_admin()
        
        contact = self.create_contact()
        
        url = reverse('admin:oroshine_webapp_contact_change', args=[contact.ulid])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contact.name)
        self.assertContains(response, contact.email)
        self.assertContains(response, contact.subject)
    
    def test_mark_contact_as_resolved(self):
        """Test marking a contact as resolved"""
        self.login_admin()
        
        contact = self.create_contact(is_resolved=False)
        
        url = reverse('admin:oroshine_webapp_contact_change', args=[contact.ulid])
        
        update_data = {
            'user': contact.user.id,
            'name': contact.name,
            'email': contact.email,
            'subject': contact.subject,
            'message': contact.message,
            'is_resolved': True
        }
        
        response = self.client.post(url, update_data)
        
        # Verify contact was marked as resolved
        contact.refresh_from_db()
        self.assertTrue(contact.is_resolved)
        self.assertIsNotNone(contact.resolved_at)
    
    def test_bulk_mark_contacts_as_resolved(self):
        """Test bulk marking contacts as resolved"""
        self.login_admin()
        
        contact1 = self.create_contact(is_resolved=False)
        contact2 = self.create_contact(
            is_resolved=False,
            name='User 2',
            email='user2@test.com'
        )
        
        url = reverse('admin:oroshine_webapp_contact_changelist')
        
        action_data = {
            'action': 'mark_as_resolved',
            '_selected_action': [contact1.ulid, contact2.ulid],
            'index': 0
        }
        
        response = self.client.post(url, action_data)
        
        # Verify contacts were marked as resolved
        contact1.refresh_from_db()
        contact2.refresh_from_db()
        self.assertTrue(contact1.is_resolved)
        self.assertTrue(contact2.is_resolved)
    
    def test_filter_contacts_by_resolution_status(self):
        """Test filtering contacts by resolution status"""
        self.login_admin()
        
        # Create resolved and unresolved contacts
        self.create_contact(is_resolved=True)
        self.create_contact(is_resolved=False, email='unresolved@test.com')
        
        url = reverse('admin:oroshine_webapp_contact_changelist')
        
        # Filter by resolved
        response = self.client.get(url + '?is_resolved=1')
        self.assertEqual(response.status_code, 200)
        
        # Filter by unresolved
        response = self.client.get(url + '?is_resolved=0')
        self.assertEqual(response.status_code, 200)


class AdminUserProfileManagementTests(BaseTestCase):
    """Tests for managing user profiles in admin panel"""
    
    def test_view_user_profile_list(self):
        """Test viewing user profile list in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_userprofile_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.regular_profile.user.username)
    
    def test_view_user_profile_detail(self):
        """Test viewing user profile detail in admin"""
        self.login_admin()
        
        url = reverse('admin:oroshine_webapp_userprofile_change', args=[self.regular_profile.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.regular_profile.phone)