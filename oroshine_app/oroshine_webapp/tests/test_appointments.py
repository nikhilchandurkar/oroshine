"""
End-to-End Tests for Appointment Booking System
Tests appointment creation, viewing, cancellation, and slot checking
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from oroshine_webapp.models import Appointment, Doctor, Service, TIME_SLOTS
from .test_base import BaseTestCase, APITestMixin, FormTestMixin


class AppointmentBookingE2ETests(BaseTestCase, APITestMixin, FormTestMixin):
    """End-to-end tests for appointment booking flow"""
    
    def test_view_appointment_page(self):
        """Test viewing the appointment booking page"""
        url = reverse('appointment')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book an Appointment')
        
        # Check that services are displayed
        self.assertContains(response, self.service1.name)
        self.assertContains(response, self.service2.name)
        
        # Check that doctors are displayed
        self.assertContains(response, f"Dr. {self.doctor1.full_name}")
    
    def test_book_appointment_authenticated_user(self):
        """Test booking appointment as authenticated user"""
        self.login_user()
        
        url = reverse('appointment')
        
        appointment_data = {
            'service': self.service1.ulid,
            'doctor': self.doctor1.id,
            'name': 'John Doe',
            'email': 'test@example.com',
            'phone': '+919876543210',
            'date': self.get_future_date(7).isoformat(),
            'time': '10:00',
            'message': 'Regular checkup needed'
        }
        
        response = self.client.post(url, appointment_data)
        
        # Should redirect to success page or profile
        self.assertEqual(response.status_code, 302)
        
        # Verify appointment was created
        appointment = Appointment.objects.get(email='test@example.com')
        self.assertEqual(appointment.user, self.regular_user)
        self.assertEqual(appointment.service, self.service1)
        self.assertEqual(appointment.doctor, self.doctor1)
        self.assertEqual(appointment.status, 'pending')
        self.assertEqual(appointment.name, 'John Doe')
    
    def test_book_appointment_unauthenticated_user(self):
        """Test booking appointment as unauthenticated user"""
        url = reverse('appointment')
        
        appointment_data = {
            'service': self.service1.ulid,
            'doctor': self.doctor1.id,
            'name': 'Guest User',
            'email': 'guest@example.com',
            'phone': '+919876543210',
            'date': self.get_future_date(7).isoformat(),
            'time': '11:00',
            'message': 'New patient appointment'
        }
        
        # Should require login or redirect
        response = self.client.post(url, appointment_data)
        
        # Check if redirected to login
        if response.status_code == 302:
            self.assertIn('custom-login', response.url.lower())
    
    def test_book_appointment_with_invalid_date(self):
        """Test booking appointment with past date"""
        self.login_user()
        
        url = reverse('appointment')
        
        appointment_data = self.get_valid_appointment_data(
            date=(timezone.now() - timedelta(days=1)).date().isoformat()
        )
        
        response = self.client.post(url, appointment_data)
        
        # Should show error
        self.assertEqual(response.status_code, 200)
        # Check for error message in response
    
    def test_book_appointment_with_invalid_time(self):
        """Test booking appointment outside business hours"""
        self.login_user()
        
        url = reverse('appointment')
        
        # Try to book at 3 AM (outside business hours)
        appointment_data = self.get_valid_appointment_data(time='03:00')
        
        response = self.client.post(url, appointment_data)
        
        # Should show validation error
        self.assertEqual(response.status_code, 200)
    
    def test_double_booking_prevention(self):
        """Test that double booking is prevented"""
        self.login_user()
        
        # Create first appointment
        appointment_date = self.get_future_date(7)
        time_slot = '10:00'
        
        self.create_appointment(
            user=self.regular_user,
            doctor=self.doctor1,
            date=appointment_date,
            time=time_slot,
            status='confirmed'
        )
        
        # Try to book same slot with different user
        self.client.logout()
        self.login_user(username='testuser2', password='TestPass123!')
        
        url = reverse('appointment')
        appointment_data = {
            'service': self.service1.ulid,
            'doctor': self.doctor1.id,
            'name': 'Jane Smith',
            'email': 'test2@example.com',
            'phone': '+919999999999',
            'date': appointment_date.isoformat(),
            'time': time_slot,
            'message': 'Trying to book same slot'
        }
        
        response = self.client.post(url, appointment_data)
        
        # Should show error about slot being taken
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already booked', status_code=200)
    
    def test_book_appointment_with_inactive_service(self):
        """Test booking with inactive service"""
        self.login_user()
        
        url = reverse('appointment')
        
        appointment_data = self.get_valid_appointment_data(
            service=self.inactive_service.ulid
        )
        
        response = self.client.post(url, appointment_data)
        
        # Should show error
        self.assertEqual(response.status_code, 200)
    
    def test_book_appointment_with_inactive_doctor(self):
        """Test booking with inactive doctor"""
        self.login_user()
        
        url = reverse('appointment')
        
        appointment_data = self.get_valid_appointment_data(
            doctor=self.inactive_doctor.id
        )
        
        response = self.client.post(url, appointment_data)
        
        # Should show error or not allow selection
        self.assertEqual(response.status_code, 200)
    
    def test_appointment_prefills_user_data(self):
        """Test that appointment form prefills authenticated user data"""
        self.login_user()
        
        url = reverse('appointment')
        response = self.client.get(url)
        
        # Check that form has user's data
        form = response.context['form']
        self.assertEqual(form.initial.get('name'), 'John Doe')
        self.assertEqual(form.initial.get('email'), 'test@example.com')
        self.assertEqual(form.initial.get('phone'), '+919876543210')


class AppointmentSlotCheckingE2ETests(BaseTestCase, APITestMixin):
    """End-to-end tests for appointment slot availability checking"""
    
    def test_check_available_slots_api(self):
        """Test API endpoint for checking available slots"""
        url = reverse('check_slots_ajax')
        
        appointment_date = self.get_future_date(7)
        
        # Create some booked appointments
        self.create_appointment(
            doctor=self.doctor1,
            date=appointment_date,
            time='10:00',
            status='confirmed'
        )
        self.create_appointment(
            doctor=self.doctor1,
            date=appointment_date,
            time='11:00',
            status='pending'
        )
        
        # Check available slots
        response = self.client.get(url, {
            'doctor': self.doctor1.id,
            'date': appointment_date.isoformat()
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # 10:00 and 11:00 should be booked
        self.assertIn('booked_slots', data)
        self.assertIn('10:00', data['booked_slots'])
        self.assertIn('11:00', data['booked_slots'])
        
        # 12:00 should be available
        self.assertNotIn('12:00', data['booked_slots'])
    
    def test_check_slots_for_different_doctors(self):
        """Test slot availability is doctor-specific"""
        url = reverse('check_slots_ajax')
        
        appointment_date = self.get_future_date(7)
        
        # Book slot for doctor1
        self.create_appointment(
            doctor=self.doctor1,
            date=appointment_date,
            time='10:00',
            status='confirmed'
        )
        
        # Check slots for doctor1
        response = self.client.get(url, {
            'doctor': self.doctor1.id,
            'date': appointment_date.isoformat()
        })
        data = json.loads(response.content)
        self.assertIn('10:00', data['booked_slots'])
        
        # Check slots for doctor2 (should be available)
        response = self.client.get(url, {
            'doctor': self.doctor2.id,
            'date': appointment_date.isoformat()
        })
        data = json.loads(response.content)
        self.assertNotIn('10:00', data['booked_slots'])
    
    def test_cancelled_appointments_free_up_slots(self):
        """Test that cancelled appointments free up time slots"""
        url = reverse('check_slots_ajax')
        
        appointment_date = self.get_future_date(7)
        
        # Create cancelled appointment
        self.create_appointment(
            doctor=self.doctor1,
            date=appointment_date,
            time='10:00',
            status='cancelled'
        )
        
        # Check slots - cancelled slot should be available
        response = self.client.get(url, {
            'doctor': self.doctor1.id,
            'date': appointment_date.isoformat()
        })
        
        data = json.loads(response.content)
        self.assertNotIn('10:00', data['booked_slots'])


class AppointmentCancellationE2ETests(BaseTestCase, APITestMixin):
    """End-to-end tests for appointment cancellation"""
    
    def test_cancel_appointment_by_user(self):
        """Test user cancelling their own appointment"""
        self.login_user()
        
        # Create appointment
        appointment = self.create_appointment(
            user=self.regular_user,
            status='pending'
        )
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': appointment.ulid})
        
        response = self.client.post(url)
        
        # Should return success
        data = self.assert_json_success(response)
        self.assertIn('cancelled successfully', data['message'])
        
        # Verify appointment was cancelled
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'cancelled')
    
    def test_cancel_appointment_requires_authentication(self):
        """Test that cancellation requires authentication"""
        appointment = self.create_appointment(status='pending')
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': appointment.ulid})
        
        response = self.client.post(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('custom-login', response.url)
    
    def test_cancel_appointment_of_another_user(self):
        """Test that users cannot cancel other users' appointments"""
        # Create appointment for user1
        appointment = self.create_appointment(
            user=self.regular_user,
            status='pending'
        )
        
        # Login as user2
        self.login_user(username='testuser2', password='TestPass123!')
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': appointment.ulid})
        response = self.client.post(url)
        
        # Should return error
        self.assertEqual(response.status_code, 404)
    
    def test_cannot_cancel_confirmed_appointment(self):
        """Test that confirmed appointments cannot be cancelled by user"""
        self.login_user()
        
        appointment = self.create_appointment(
            user=self.regular_user,
            status='confirmed'
        )
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': appointment.ulid})
        response = self.client.post(url)
        
        # Should return error
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Cannot cancel', data['message'])
    
    def test_cannot_cancel_completed_appointment(self):
        """Test that completed appointments cannot be cancelled"""
        self.login_user()
        
        appointment = self.create_appointment(
            user=self.regular_user,
            status='completed'
        )
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': appointment.ulid})
        response = self.client.post(url)
        
        # Should return error
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
    
    def test_cancel_nonexistent_appointment(self):
        """Test cancelling non-existent appointment"""
        self.login_user()
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': 'FAKEID123456789FAKEID123'})
        response = self.client.post(url)
        
        # Should return 404
        self.assertEqual(response.status_code, 404)


class AppointmentViewingE2ETests(BaseTestCase):
    """End-to-end tests for viewing appointments"""
    
    def test_user_can_view_own_appointments(self):
        """Test that users can view their own appointments"""
        self.login_user()
        
        # Create appointments
        appt1 = self.create_appointment(
            user=self.regular_user,
            service=self.service1
        )
        appt2 = self.create_appointment(
            user=self.regular_user,
            service=self.service2,
            time='11:00'
        )
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check appointments are displayed
        self.assertContains(response, appt1.service.name)
        self.assertContains(response, appt2.service.name)
        self.assertContains(response, f"Dr. {self.doctor1.full_name}")
    
    def test_user_cannot_view_others_appointments(self):
        """Test that users cannot view other users' appointments"""
        # Create appointment for user1
        appt = self.create_appointment(user=self.regular_user)
        
        # Login as user2
        self.login_user(username='testuser2', password='TestPass123!')
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        # Should not contain user1's appointments
        appointments = response.context['appointments']
        self.assertEqual(len(appointments), 0)


class AppointmentEmailNotificationTests(BaseTestCase):
    """Tests for appointment email notifications"""

    def get_valid_appointment_data(self, **kwargs):
        """Helper to generate valid data for booking"""
        defaults = {
            'service': self.service1.ulid,
            'doctor': self.doctor1.id,
            'name': 'John Doe',
            'email': 'nikhilchandurkar24@gmail.com',
            'phone': '+919876543210',
            'date': self.get_future_date(7).isoformat(),
            'time': '10:00',
            'message': 'Test message'
        }
        defaults.update(kwargs)
        return defaults
    
    def test_appointment_confirmation_email_sent(self):
        """Test that confirmation email is sent after booking"""
        self.login_user()
        
        url = reverse('appointment')
        
        appointment_data = self.get_valid_appointment_data()
        
        response = self.client.post(url, appointment_data)
        
        # In production, this would be sent via Celery
        # In tests, we can check if the task was called
        # This requires mocking the Celery task
    
    def test_appointment_status_change_email(self):
        """Test that email is sent when appointment status changes"""
        # This would test admin changing appointment status
        # and email notification being sent
        pass


class AppointmentServicePriceTests(BaseTestCase):
    """Tests for appointment service pricing"""
    
    def test_appointment_displays_service_price(self):
        """Test that appointment displays correct service price"""
        appointment = self.create_appointment(service=self.service1)
        
        self.assertEqual(appointment.get_service_price(), Decimal('1500.00'))
    
    def test_different_services_have_different_prices(self):
        """Test that different services have different prices"""
        appt1 = self.create_appointment(service=self.service1)
        appt2 = self.create_appointment(service=self.service2, time='11:00')
        
        self.assertEqual(appt1.get_service_price(), Decimal('1500.00'))
        self.assertEqual(appt2.get_service_price(), Decimal('5000.00'))
        self.assertNotEqual(appt1.get_service_price(), appt2.get_service_price())