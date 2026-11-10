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
