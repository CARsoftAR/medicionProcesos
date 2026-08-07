import re

def configure_drf():
    # 1. Update config/settings.py
    with open('config/settings.py', 'r', encoding='utf-8') as f:
        settings_content = f.read()

    # Add to INSTALLED_APPS if not present
    if "'rest_framework'" not in settings_content:
        # Find INSTALLED_APPS
        apps_pattern = r'INSTALLED_APPS = \['
        replacement = "INSTALLED_APPS = [\n    'rest_framework',\n    'rest_framework.authtoken',"
        settings_content = re.sub(apps_pattern, replacement, settings_content, count=1)
        
    # Add REST_FRAMEWORK settings at the end if not present
    if "REST_FRAMEWORK" not in settings_content:
        drf_settings = """\n
# REST Framework Configuration (Mobile API)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ]
}
"""
        settings_content += drf_settings

    with open('config/settings.py', 'w', encoding='utf-8') as f:
        f.write(settings_content)

    # 2. Update config/urls.py
    with open('config/urls.py', 'r', encoding='utf-8') as f:
        urls_content = f.read()
        
    if "'api/calidad/'" not in urls_content:
        # Find urlpatterns
        url_pattern = r"urlpatterns = \["
        replacement = "urlpatterns = [\n    path('api/calidad/', include('mediciones.api_urls')),"
        urls_content = re.sub(url_pattern, replacement, urls_content, count=1)
        
        # Ensure include is imported
        if "from django.urls import path, include" not in urls_content:
            urls_content = urls_content.replace("from django.urls import path", "from django.urls import path, include")

    with open('config/urls.py', 'w', encoding='utf-8') as f:
        f.write(urls_content)

configure_drf()
print("Settings and URLs updated.")
