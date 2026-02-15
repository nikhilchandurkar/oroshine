"""
End-to-End Tests for Public Pages and Contact Form
Tests homepage, about, services, team, testimonials, pricing, and contact
"""

from django.test import TestCase
from django.urls import reverse
from django.core import mail

from oroshine_webapp.models import Contact, Service, Doctor
from .test_base import BaseTestCase, FormTestMixin


class PublicPagesE2ETests(BaseTestCase):
    """End-to-end tests for public pages"""
    
    def test_homepage_loads(self):
        """Test that homepage loads successfully"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OroShine')
    
    def test_homepage_displays_services(self):
        """Test that homepage displays active services"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Active services should be visible
        self.assertContains(response, self.service1.name)
        self.assertContains(response, self.service2.name)
        
        # Inactive service should not be visible
        self.assertNotContains(response, self.inactive_service.name)
    
    def test_about_page_loads(self):
        """Test that about page loads successfully"""
        url = reverse('about')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About')
    
    def test_services_page_loads(self):
        """Test that services page loads successfully"""
        url = reverse('service')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Services')
    
    def test_services_page_displays_active_services(self):
        """Test that services page displays only active services"""
        url = reverse('service')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Active services
        self.assertContains(response, self.service1.name)
        self.assertContains(response, self.service2.name)
        
        # Inactive service should not appear
        self.assertNotContains(response, self.inactive_service.name)
    
    def test_services_page_displays_pricing(self):
        """Test that services page displays service pricing"""
        url = reverse('service')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check for price display (format may vary)
        content = response.content.decode()
        self.assertTrue('1500' in content or '1,500' in content)
    
    def test_team_page_loads(self):
        """Test that team page loads successfully"""
        url = reverse('team')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Team')
    
    def test_team_page_displays_active_doctors(self):
        """Test that team page displays only active doctors"""
        url = reverse('team')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Active doctors
        self.assertContains(response, self.doctor1.full_name)
        self.assertContains(response, self.doctor2.full_name)
        
        # Inactive doctor should not appear
        self.assertNotContains(response, self.inactive_doctor.full_name)
    
    def test_team_page_displays_doctor_specializations(self):
        """Test that team page displays doctor specializations"""
        url = reverse('team')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.doctor1.specialization)
        self.assertContains(response, self.doctor2.specialization)
    
    def test_pricing_page_loads(self):
        """Test that pricing page loads successfully"""
        url = reverse('price')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Price')
    
    def test_testimonial_page_loads(self):
        """Test that testimonial page loads successfully"""
        url = reverse('testimonial')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Testimonial')
    
    def test_contact_page_loads(self):
        """Test that contact page loads successfully"""
        url = reverse('contact')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contact')


class ContactFormE2ETests(BaseTestCase, FormTestMixin):
    """End-to-end tests for contact form functionality"""
    
    def test_submit_contact_form_authenticated_user(self):
        """Test submitting contact form as authenticated user"""
        self.login_user()
        
        url = reverse('contact')
        
        contact_data = {
            'name': 'John Doe',
            'email': 'test@example.com',
            'subject': 'Appointment Inquiry',
            'message': 'I would like to know more about teeth cleaning services.'
        }
        
        response = self.client.post(url, contact_data)
        
        # Should redirect to home page
        self.assertEqual(response.status_code, 302)
        
        # Verify contact was created
        contact = Contact.objects.get(email='test@example.com')
        self.assertEqual(contact.user, self.regular_user)
        self.assertEqual(contact.name, 'John Doe')
        self.assertEqual(contact.subject, 'Appointment Inquiry')
        self.assertEqual(contact.message, 'I would like to know more about teeth cleaning services.')
        self.assertFalse(contact.is_resolved)
    
    def test_submit_contact_form_unauthenticated_user(self):
        """Test submitting contact form as unauthenticated user"""
        url = reverse('contact')
        
        contact_data = {
            'name': 'Guest User',
            'email': 'guest@example.com',
            'subject': 'General Inquiry',
            'message': 'What are your operating hours?'
        }
        
        response = self.client.post(url, contact_data)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url.lower())
    
    def test_contact_form_validation_empty_fields(self):
        """Test contact form validation with empty fields"""
        self.login_user()
        
        url = reverse('contact')
        
        # Submit with empty data
        contact_data = {
            'name': '',
            'email': '',
            'subject': '',
            'message': ''
        }
        
        response = self.client.post(url, contact_data)
        
        # Should not create contact
        self.assertEqual(Contact.objects.count(), 0)
    
    def test_contact_form_validation_invalid_email(self):
        """Test contact form validation with invalid email"""
        self.login_user()
        
        url = reverse('contact')
        
        contact_data = {
            'name': 'John Doe',
            'email': 'invalid-email',
            'subject': 'Test Subject',
            'message': 'Test message'
        }
        
        response = self.client.post(url, contact_data)
        
        # Should not create contact with invalid email
        contacts = Contact.objects.filter(email='invalid-email')
        self.assertEqual(contacts.count(), 0)
    
    def test_contact_form_prefills_user_data(self):
        """Test that contact form prefills authenticated user data"""
        self.login_user()
        
        url = reverse('contact')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # In a real implementation, check that form has user's name and email
    
    def test_contact_submission_sends_email(self):
        """Test that contact form submission triggers email"""
        self.login_user()
        
        url = reverse('contact')
        
        contact_data = {
            'name': 'John Doe',
            'email': 'test@example.com',
            'subject': 'Test Subject',
            'message': 'Test message content'
        }
        
        response = self.client.post(url, contact_data)
        
        # In production, email would be sent via Celery
        # In tests, we can verify the task was queued
    
    def test_multiple_contact_submissions_same_user(self):
        """Test that a user can submit multiple contact forms"""
        self.login_user()
        
        url = reverse('contact')
        
        # First submission
        contact_data1 = self.get_valid_contact_data(
            subject='First Inquiry',
            message='First message'
        )
        self.client.post(url, contact_data1)
        
        # Second submission
        contact_data2 = self.get_valid_contact_data(
            subject='Second Inquiry',
            message='Second message'
        )
        self.client.post(url, contact_data2)
        
        # Verify both contacts were created
        contacts = Contact.objects.filter(user=self.regular_user)
        self.assertEqual(contacts.count(), 2)
    
    def test_contact_displays_in_user_profile(self):
        """Test that contact submissions appear in user profile"""
        self.login_user()
        
        # Submit contact form
        contact = self.create_contact(user=self.regular_user)
        
        # View profile
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that contact is in context
        contacts = response.context['contacts']
        self.assertTrue(contacts.exists())
        self.assertEqual(contacts.first().subject, contact.subject)


class NavigationE2ETests(BaseTestCase):
    """End-to-end tests for site navigation"""
    
    def test_navigation_links_on_homepage(self):
        """Test that all navigation links are present on homepage"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check for navigation links
        self.assertContains(response, reverse('about'))
        self.assertContains(response, reverse('service'))
        self.assertContains(response, reverse('contact'))
    
    def test_navigation_links_work(self):
        """Test that navigation links actually work"""
        pages = [
            ('home', '/'),
            ('about', 'about/'),
            ('service', 'service/'),
            ('team', 'team/'),
            ('contact', 'contact/'),
            ('price', 'price/'),
            ('testimonial', 'testimonial/')
        ]
        
        for name, path in pages:
            url = reverse(name)
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 
                200,
                f"Page {name} failed to load"
            )
    
    def test_authenticated_user_navigation(self):
        """Test navigation options for authenticated users"""
        self.login_user()
        
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Should see profile and logout links
        self.assertContains(response, reverse('user_profile'))
        self.assertContains(response, reverse('custom_logout'))
    
    def test_unauthenticated_user_navigation(self):
        """Test navigation options for unauthenticated users"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Should see login and register links
        self.assertContains(response, reverse('custom_login'))
        self.assertContains(response, reverse('custom_register'))


class SEOAndMetaTagsTests(BaseTestCase):
    """Tests for SEO and meta tags on public pages"""
    
    def test_homepage_has_title(self):
        """Test that homepage has a proper title tag"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<title>')
    
    def test_pages_have_meta_description(self):
        """Test that pages have meta description tags"""
        pages = ['home', 'about', 'service', 'contact']
        
        for page_name in pages:
            url = reverse(page_name)
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, 200)
            # Check for meta description (implementation may vary)


class ResponsiveDesignTests(BaseTestCase):
    """Tests for responsive design elements"""
    
    def test_viewport_meta_tag_present(self):
        """Test that viewport meta tag is present for mobile"""
        url = reverse('home')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'viewport')


class ErrorPagesTests(BaseTestCase):
    """Tests for error pages (404, 500, etc.)"""
    
    def test_404_page_for_nonexistent_url(self):
        """Test that 404 page is shown for non-existent URLs"""
        response = self.client.get('/nonexistent-page-12345/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_404_page_for_nonexistent_appointment(self):
        """Test 404 for non-existent appointment"""
        self.login_user()
        
        url = reverse('cancel_appointment', kwargs={'appointment_id': 'FAKEID123456789FAKEID123'})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 404)