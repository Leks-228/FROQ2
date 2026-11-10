from django.contrib import admin
from .models import Artist, Album, Track, Playlist

@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('name', 'plays', 'created_at')
    search_fields = ('name',)

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist_names', 'year', 'type', 'track_count')
    list_filter = ('artists', 'type', 'year')
    search_fields = ('title', 'artists__name')
    filter_horizontal = ('artists',)
    
    def artist_names(self, obj):
        return ", ".join(a.name for a in obj.artists.all())
    artist_names.short_description = 'Исполнители'
    
    def track_count(self, obj):
        return obj.tracks.count()
    track_count.short_description = 'Треков'

@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist_names', 'album', 'track_number', 'plays')
    list_filter = ('artists', 'album')
    search_fields = ('title', 'artists__name')
    filter_horizontal = ('artists',)
    
    def artist_names(self, obj):
        return ", ".join([a.name for a in obj.artists.all()])
    artist_names.short_description = 'Исполнители'

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'track_count', 'created_at')
    search_fields = ('name', 'user__username')

    def track_count(self, obj):
        return obj.tracks.count()
    track_count.short_description = 'Треки'