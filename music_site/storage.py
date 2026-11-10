import os

from cloudinary_storage.storage import MediaCloudinaryStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage


class LenientCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Manifest-хранилище статики, которое не роняет страницу с 500,
    если collectstatic не запускали (нет манифеста или самого файла).

    В этом случае возвращается обычный URL файла, а не хэшированный.
    """

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name


# Расширения, которые Cloudinary хранит как resource_type='video'.
# Аудио (mp3 и т.п.) в Cloudinary относится именно к video, а не к image.
AUDIO_EXTENSIONS = {
    '.mp3', '.wav', '.ogg', '.oga', '.m4a', '.aac', '.flac',
    '.opus', '.wma', '.aiff', '.aif', '.alac', '.mp2', '.m4b',
}

# Папки, в которые Django сохраняет аудио (см. upload_to у Track.audio_file).
# Нужны на случай, если Cloudinary вернул public_id без расширения файла.
# Проверяем любой сегмент пути, потому что к имени добавляется префикс
# MEDIA_URL: реальное имя в БД выглядит как "media/tracks/song" (без .mp3).
AUDIO_FOLDERS = {'tracks'}


class SmartCloudinaryStorage(MediaCloudinaryStorage):
    """
    Хранилище Cloudinary, которое само выбирает тип ресурса:
    аудио загружается как video, всё остальное — как image.

    Без этого mp3 пытались бы загрузить как картинку, и Cloudinary
    отклонял бы загрузку.
    """

    def _get_resource_type(self, name):
        parts = str(name).replace('\\', '/').lstrip('/').split('/')
        extension = os.path.splitext(parts[-1])[1].lower()
        if extension in AUDIO_EXTENSIONS:
            return 'video'
        # Cloudinary для image/video отдаёт public_id без расширения,
        # поэтому определяем аудио ещё и по папке (media/tracks/...).
        if any(part.lower() in AUDIO_FOLDERS for part in parts[:-1]):
            return 'video'
        return 'image'
