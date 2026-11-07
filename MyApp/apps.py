from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'MyApp'

    def ready(self):
        # Gracefully handle missing files on disk without crashing templates/views with FileNotFoundError
        try:
            from django.db.models.fields.files import FieldFile
            _original_size = FieldFile.size.fget

            def _safe_size(self):
                try:
                    if not self.name:
                        return 0
                    if hasattr(self, 'storage') and self.storage.exists(self.name):
                        return _original_size(self)
                    return 0
                except (FileNotFoundError, OSError, ValueError):
                    return 0

            FieldFile.size = property(_safe_size)
        except Exception:
            pass
