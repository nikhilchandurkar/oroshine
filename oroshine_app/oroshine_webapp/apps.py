from django.apps import AppConfig
import os
from pathlib import Path
from django.apps import AppConfig
from PIL import Image

class OroshineWebappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oroshine_webapp'

    def ready(self):
        # Path to default avatar
        import oroshine_webapp.signals
        media_dir = Path("media/avatars")
        default_avatar = media_dir/ "default.jpeg"
        
        # Create folder if not exists
        os.makedirs(media_dir, exist_ok=True)
        
        # Create a placeholder image if not exists
        if not default_avatar.exists():
            img = Image.new("RGB", (128, 128), color=(200, 200, 200))  
            img.save(default_avatar)