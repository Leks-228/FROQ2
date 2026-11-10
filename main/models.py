from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone

class Artist(models.Model):
    name = models.CharField(max_length=200, verbose_name='Имя')
    photo = models.ImageField(upload_to='artists/', blank=True, null=True, verbose_name='Фото')
    bio = models.TextField(blank=True, verbose_name='Описание')
    plays = models.IntegerField(default=0, verbose_name='Прослушивания')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_monthly_plays(self):
        """Прослушивания треков исполнителя за последние 30 дней."""
        month_ago = timezone.now() - timedelta(days=30)
        return ListeningHistory.objects.filter(
            track__artists=self,
            listened_at__gte=month_ago,
        ).count()

class Album(models.Model):
    ALBUM_TYPES = [
        ('album', 'Альбом'),
        ('single', 'Сингл'),
        ('ep', 'EP'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Название')
    artists = models.ManyToManyField(Artist, related_name='albums', verbose_name='Исполнители')
    cover = models.ImageField(upload_to='covers/', blank=True, null=True, verbose_name='Обложка')
    year = models.IntegerField(verbose_name='Год выпуска')
    type = models.CharField(max_length=10, choices=ALBUM_TYPES, default='album', verbose_name='Тип')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.pk:
            artists_names = ", ".join([a.name for a in self.artists.all()])
            if artists_names:
                return f"{artists_names} - {self.title}"
        return self.title

class Track(models.Model):
    title = models.CharField(max_length=200, verbose_name='Название')
    artists = models.ManyToManyField(Artist, related_name='tracks', verbose_name='Исполнители')
    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, blank=True, related_name='tracks', verbose_name='Альбом')
    track_number = models.IntegerField(default=1, verbose_name='Номер трека')
    audio_file = models.FileField(upload_to='tracks/', verbose_name='Аудиофайл')
    plays = models.IntegerField(default=0, verbose_name='Прослушивания')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        artists_names = ", ".join([a.name for a in self.artists.all()])
        return f"{artists_names} - {self.title}"

    def get_stream_url(self):
        return reverse('stream_audio', args=[self.audio_file.name])

class Playlist(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists', verbose_name='Пользователь')
    tracks = models.ManyToManyField(Track, blank=True, related_name='playlists', verbose_name='Треки')
    cover = models.ImageField(upload_to='playlists/', blank=True, null=True, verbose_name='Обложка')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'track')

    def __str__(self):
        return f"{self.user.username} - {self.track.title}"


class FavoriteAlbum(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_albums')
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'album')

    def __str__(self):
        return f"{self.user.username} - {self.album.title}"

class ListeningHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listening_history')
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='listening_history')
    listened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-listened_at']
        verbose_name = 'История прослушивания'
        verbose_name_plural = 'История прослушиваний'

    def __str__(self):
        return f"{self.user.username} слушал {self.track.title} в {self.listened_at}"
    
# Добавить в конец:
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Аватар')
    bio = models.TextField(blank=True, verbose_name='О себе')

    def __str__(self):
        return self.user.username