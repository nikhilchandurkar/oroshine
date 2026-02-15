"""
End-to-End Tests for Authentication and User Management
Tests registration, login, logout, password reset, and profile management
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from datetime import timedelta

from oroshine_webapp.models import UserProfile, Appointment,TIME_SLOTS
from .test_base import BaseTestCase, APITestMixin


class AuthenticationE2ETests(BaseTestCase, APITestMixin):
    """End-to-end tests for user authentication"""
    
    def test_user_registration_complete_flow(self):
        """Test complete user registration flow"""
        url = reverse('custom_register')
        
        # Test GET request - registration page loads
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')
        
        # Test POST - successful registration
        registration_data = {
            'username': 'newuser123',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@test.com',
            'password1': 'SecurePass123!@#',
            'password2': 'SecurePass123!@#'
        }
        
        response = self.client.post(url, registration_data)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('custom_login')))
        
        # Verify user was created
        user = User.objects.get(username='newuser123')
        self.assertEqual(user.email, 'newuser@test.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        
        # Verify profile was created
        profile = UserProfile.objects.get(user=user)
        self.assertIsNotNone(profile)
        
        # Verify welcome email was queued (check mail outbox)
        # Note: In production this would be sent via Celery
        # In tests, we can check if the task was called
    
    def test_registration_duplicate_username(self):
        """Test registration with duplicate username"""
        url = reverse('custom_register')
        
        registration_data = {
            'username': 'testuser',  # Already exists
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'another@test.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        }
        
        response = self.client.post(url, registration_data)
        
        # Should not redirect, should show error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists', status_code=200)
    
    def test_registration_duplicate_email(self):
        """Test registration with duplicate email"""
        url = reverse('custom_register')
        
        registration_data = {
            'username': 'newuser456',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',  # Already exists
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!'
        }
        
        response = self.client.post(url, registration_data)
        self.assertEqual(response.status_code, 200)
    
    def test_registration_password_mismatch(self):
        """Test registration with mismatched passwords"""
        url = reverse('custom_register')
        
        registration_data = {
            'username': 'newuser789',
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'newuser789@test.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass123!'
        }
        
        response = self.client.post(url, registration_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'password2', 
                           "The two password fields didn't match.")
    
    def test_user_login_success(self):
        """Test successful user login"""
        url = reverse('custom_login')
        
        # Test GET - login page loads
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST - successful login
        login_data = {
            'username': 'testuser',
            'password': 'TestPass123!'
        }
        
        response = self.client.post(url, login_data)
        self.assertEqual(response.status_code, 302)
        
        # Verify user is logged in
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, 'testuser')
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = reverse('custom_login')
        
        login_data = {
            'username': 'testuser',
            'password': 'WrongPassword123!'
        }
        
        response = self.client.post(url, login_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')
    
    def test_user_logout(self):
        """Test user logout"""
        # Login first
        self.login_user()
        
        # Logout
        url = reverse('custom_logout')
        response = self.client.get(url)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # User should not be authenticated
        response = self.client.get(reverse('home'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
    
    def test_check_username_availability_api(self):
        """Test username availability check API"""
        url = reverse('check_availability')
        
        # Test available username
        response = self.client.get(url, {'username': 'availableuser'})
        data = self.assertJSONResponse(response, 'success')
        self.assertFalse(data['is_taken'])
        self.assertEqual(data['message'], 'Username available')
        
        # Test taken username
        response = self.client.get(url, {'username': 'testuser'})
        data = self.assertJSONResponse(response, 'success')
        self.assertTrue(data['is_taken'])
        self.assertIn('already taken', data['message'])
        self.assertIn('suggestion', data)
    
    def test_check_email_availability_api(self):
        """Test email availability check API"""
        url = reverse('check_availability')
        
        # Test available email
        response = self.client.get(url, {'email': 'available@test.com'})
        data = self.assertJSONResponse(response, 'success')
        self.assertFalse(data['is_taken'])
        
        # Test taken email
        response = self.client.get(url, {'email': 'test@example.com'})
        data = self.assertJSONResponse(response, 'success')
        self.assertTrue(data['is_taken'])
        self.assertEqual(data['message'], 'Email already registered')


class PasswordResetE2ETests(BaseTestCase):
    """End-to-end tests for password reset functionality"""
    
    def test_password_reset_request_flow(self):
        """Test password reset request flow"""
        url = reverse('password_reset')
        
        # Test GET - reset page loads
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST - request reset
        reset_data = {'email': self.regular_user.email}
        response = self.client.post(url, reset_data)
        
        # Should redirect to done page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('password_reset_done')))
        
        # In production, email would be sent via Celery
        # In tests, we can verify the task was queued
    
    def test_password_reset_nonexistent_email(self):
        """Test password reset with non-existent email"""
        url = reverse('password_reset')
        
        reset_data = {'email': 'nonexistent@test.com'}
        response = self.client.post(url, reset_data)
        
        # Should still redirect (to prevent email enumeration)
        self.assertEqual(response.status_code, 302)
    
    def test_password_change_logged_in_user(self):
        """Test password change for logged-in user"""
        self.login_user()
        
        url = reverse('change_password')
        
        # Test GET - change password page loads
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST - change password
        change_data = {
            'old_password': 'TestPass123!',
            'new_password1': 'NewSecurePass123!',
            'new_password2': 'NewSecurePass123!'
        }
        
        response = self.client.post(url, change_data)
        
        # Should redirect to done page
        self.assertEqual(response.status_code, 302)
        
        # Verify password was changed
        self.client.logout()
        login_success = self.client.login(
            username='testuser',
            password='NewSecurePass123!'
        )
        self.assertTrue(login_success)


class UserProfileE2ETests(BaseTestCase):
    """End-to-end tests for user profile management"""
    
    def test_view_profile_page(self):
        """Test viewing user profile page"""
        self.login_user()
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertContains(response, self.regular_user.email)
    
    def test_profile_page_requires_login(self):
        """Test that profile page requires authentication"""
        url = reverse('user_profile')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
    
    def test_update_profile_basic_info(self):
        """Test updating basic profile information"""
        self.login_user()
        
        url = reverse('user_profile')
        
        profile_data = {
            'first_name': 'Jonathan',
            'last_name': 'Doe',
            'email': 'newemail@test.com',
            'phone': '+919999999999',
            'city': 'Delhi',
            'state': 'Delhi',
            'zip_code': '110001'
        }
        
        response = self.client.post(url, profile_data)
        
        # Should redirect back to profile
        self.assertEqual(response.status_code, 302)
        
        # Verify user was updated
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Jonathan')
        self.assertEqual(self.regular_user.email, 'newemail@test.com')
        
        # Verify profile was updated
        self.regular_profile.refresh_from_db()
        self.assertEqual(self.regular_profile.phone, '+919999999999')
        self.assertEqual(self.regular_profile.city, 'Delhi')
    
    def test_update_profile_with_medical_info(self):
        """Test updating profile with medical information"""
        self.login_user()
        
        url = reverse('user_profile')
        
        profile_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'test@example.com',
            'phone': '+919876543210',
            'medical_history': 'Diabetes, High Blood Pressure',
            'allergies': 'Penicillin',
            'emergency_contact_name': 'Jane Doe',
            'emergency_contact_phone': '+919999888877'
        }
        
        response = self.client.post(url, profile_data)
        
        # Verify medical info was saved
        self.regular_profile.refresh_from_db()
        self.assertEqual(self.regular_profile.medical_history, 'Diabetes, High Blood Pressure')
        self.assertEqual(self.regular_profile.allergies, 'Penicillin')
        self.assertEqual(self.regular_profile.emergency_contact_name, 'Jane Doe')
    
    def test_profile_displays_appointment_stats(self):
        """Test that profile page displays appointment statistics"""
        self.login_user()
        
        # Create appointments with different statuses
        self.create_appointment(status='pending')
        self.create_appointment(status='confirmed', time='11:00')
        self.create_appointment(status='completed', time='12:00')
        self.create_appointment(status='cancelled', time='13:00')
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that stats are displayed
        context = response.context
        self.assertEqual(context['total_appointments'], 4)
        self.assertEqual(context['pending_appointments'], 1)
        self.assertEqual(context['completed_appointments'], 1)
    
    def test_profile_displays_user_appointments(self):
        """Test that profile page displays user's appointments"""
        self.login_user()
        
        # Create some appointments
        appt1 = self.create_appointment(
            service=self.service1,
            doctor=self.doctor1,
            time='10:00'
        )
        appt2 = self.create_appointment(
            service=self.service2,
            doctor=self.doctor2,
            time='14:00'
        )
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check appointments are in context
        appointments = response.context['appointments']
        self.assertEqual(len(appointments), 2)
    
    def test_profile_pagination(self):
        """Test appointment pagination on profile page"""
        self.login_user()
        
        # Create 15 appointments
        for i in range(15):
            days_ahead = i + 1
            time_slot = TIME_SLOTS[i % len(TIME_SLOTS)][0]
            self.create_appointment(
                date=self.get_future_date(days_ahead),
                time=time_slot
            )
        
        url = reverse('user_profile')
        
        # First page
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        appointments = response.context['appointments']
        self.assertEqual(len(appointments), 10)  # Default page size
        
        # Second page
        response = self.client.get(url + '?page=2')
        appointments = response.context['appointments']
        self.assertEqual(len(appointments), 5)


class SocialAuthenticationTests(BaseTestCase):
    """Tests for social authentication integration"""
    
    def test_social_auth_creates_profile(self):
        """Test that social authentication creates a user profile"""
        # This would test Google OAuth flow
        # In a real scenario, you'd use mocking for OAuth providers
        pass
    
    def test_social_auth_email_verification(self):
        """Test email verification for social auth users"""
        # Test that social auth users are automatically verified
        pass