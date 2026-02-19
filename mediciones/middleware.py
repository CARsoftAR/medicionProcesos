from django.contrib.auth import login
from django.contrib.auth.models import User
from django.conf import settings

class AutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG and not request.user.is_authenticated:
            # We try to find 'admin' user, if not, 'administrador', or the first superuser
            user = User.objects.filter(username='admin').first()
            if not user:
                user = User.objects.filter(username='administrador').first()
            if not user:
                user = User.objects.filter(is_superuser=True).first()
            
            if user:
                # Log in the user without password for development
                login(request, user)
                
                # Ensure profile exists
                from .models import Profile
                Profile.objects.get_or_create(user=user, defaults={'role': 'CALIDAD'})
        
        response = self.get_response(request)
        return response
