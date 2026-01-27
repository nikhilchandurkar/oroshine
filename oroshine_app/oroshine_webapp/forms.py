from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile,Appointment,TIME_SLOTS,Doctor
from .services_cache import get_service_tuples
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


class NewUserForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}))
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = UserProfile
        fields = [
            'phone', 'date_of_birth', 'address', 'city', 'state', 
            'zip_code', 'avatar', 'emergency_contact_name', 
            'emergency_contact_phone', 'medical_history', 'allergies'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+91 (555) 123-4567'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '123 Main Street'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Mumbai'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Maharashtra'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '441107'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control', 
                'accept': 'image/*'
            }),
            'emergency_contact_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'John Doe'
            }),
            'emergency_contact_phone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '+1 (555) 987-6543'
            }),
            'medical_history': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Any relevant medical history...'
            }),
            'allergies': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2, 
                'placeholder': 'List any allergies...'
            }),
        }

    def clean_avatar(self):
        """Validate and compress avatar image"""
        avatar = self.cleaned_data.get('avatar')
        
        if avatar:
            # Check file size (2MB limit)
            if avatar.size > 1 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2MB )")
            
            # Check file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = avatar.name.split('.')[-1].lower()
            if f'.{ext}' not in valid_extensions:
                raise forms.ValidationError("Unsupported file extension. Use JPG, PNG, or GIF.")
            
            try:
                # Compress and resize image
                img = Image.open(avatar)
                
                # Convert RGBA to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Resize if too large
                if img.height > 800 or img.width > 800:
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                # Save to BytesIO
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)
                
                # Create new InMemoryUploadedFile
                avatar = InMemoryUploadedFile(
                    output, 'ImageField', 
                    f"{avatar.name.split('.')[0]}.jpg",
                    'image/jpeg', 
                    sys.getsizeof(output), 
                    None
                )
            except Exception as e:
                raise forms.ValidationError(f"Error processing image: {str(e)}")
        
        return avatar


    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            profile.save()
        
        return profile


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'service',
            'doctor',
            'name',
            'email',
            'phone',
            'date',
            'time',
            'message'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctor'].queryset = Doctor.cached_active_doctors()
