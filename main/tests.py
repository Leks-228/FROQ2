import io
import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from PIL import Image

from .models import Album, FavoritePlaylist, Playlist, Track, Artist


def make_image(name='cover.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), (30, 120, 220)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class PlaylistCoverTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix='pupu-test-media-')
        cls._override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('cover-user', password='secret')
        self.playlist = Playlist.objects.create(name='Тестовый плейлист', user=self.user)
        self.client.force_login(self.user)

    def post_cover(self, data, **extra):
        return self.client.post(
            f'/playlist/{self.playlist.id}/cover/',
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **extra,
        )

    def test_ajax_upload_saves_cover_and_returns_url(self):
        response = self.post_cover({'cover': make_image()})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['has_cover'])
        self.assertTrue(payload['cover_url'].startswith('/media/playlists/'))

        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.cover)
        self.assertTrue(self.playlist.cover.storage.exists(self.playlist.cover.name))

    def test_ajax_invalid_file_returns_errors_and_keeps_old_cover(self):
        self.post_cover({'cover': make_image('first.png')})
        self.playlist.refresh_from_db()
        old_name = self.playlist.cover.name

        broken = SimpleUploadedFile('broken.txt', b'not an image', content_type='text/plain')
        response = self.post_cover({'cover': broken})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertTrue(payload['errors'])

        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.cover.name, old_name)

    def test_ajax_remove_clears_cover(self):
        self.post_cover({'cover': make_image()})
        self.playlist.refresh_from_db()
        old_name = self.playlist.cover.name

        response = self.post_cover({'remove_cover': '1'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertFalse(payload['has_cover'])

        self.playlist.refresh_from_db()
        self.assertFalse(self.playlist.cover)
        self.assertFalse(self.playlist.cover.storage.exists(old_name))

    def test_regular_form_post_still_redirects(self):
        response = self.client.post(
            f'/playlist/{self.playlist.id}/cover/',
            {'cover': make_image()},
        )

        self.assertRedirects(response, f'/playlist/{self.playlist.id}/')
        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.cover)

    def test_create_playlist_with_cover_saves_it(self):
        response = self.client.post(
            '/playlist/create/',
            {'name': 'Плейлист с обложкой', 'cover': make_image()},
        )

        playlist = Playlist.objects.get(name='Плейлист с обложкой')
        self.assertRedirects(response, f'/playlist/{playlist.id}/')
        self.assertTrue(playlist.cover)

    def test_htmx_create_returns_detail_without_redirect(self):
        response = self.client.post(
            '/playlist/create/',
            {'name': 'HTMX-плейлист'},
            HTTP_HX_REQUEST='true',
        )

        playlist = Playlist.objects.get(name='HTMX-плейлист')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Push-Url'], f'/playlist/{playlist.id}/')
        self.assertContains(response, 'HTMX-плейлист')

    def test_htmx_create_returns_content_fragment_not_full_page(self):
        """HTMX-ответ при создании плейлиста должен быть только фрагментом
        страницы (без <!DOCTYPE>/<html>/<body>), иначе htmx подменяет контент
        целой страницей и ломает состояние плеера."""
        response = self.client.post(
            '/playlist/create/',
            {'name': 'HTMX-фрагмент'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<!DOCTYPE html>', status_code=200)
        self.assertNotContains(response, '<html', status_code=200)
        self.assertNotContains(response, '<body', status_code=200)
        self.assertContains(response, 'playlist-hero')

    def test_htmx_create_with_cover_returns_content_fragment(self):
        response = self.client.post(
            '/playlist/create/',
            {'name': 'HTMX-плейлист с обложкой', 'cover': make_image()},
            HTTP_HX_REQUEST='true',
        )

        playlist = Playlist.objects.get(name='HTMX-плейлист с обложкой')
        self.assertTrue(playlist.cover)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<!DOCTYPE html>', status_code=200)
        self.assertContains(response, 'playlist-hero')

    def test_htmx_create_invalid_returns_form_fragment(self):
        """Ошибки валидации при HTMX-создании должны возвращать фрагмент формы
        (без полного документа), чтобы innerHTML-swap не вставлял целую
        страницу внутрь #main-content и не ломал плеер."""
        response = self.client.post(
            '/playlist/create/',
            {'name': ''},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Playlist.objects.filter(name='').exists())
        self.assertNotContains(response, '<!DOCTYPE html>', status_code=200)
        self.assertNotContains(response, '<html', status_code=200)
        self.assertContains(response, 'hx-post="/playlist/create/"')
        self.assertContains(response, 'errorlist')


class PlaylistTrackRemovalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('remove-user', password='secret')
        self.playlist = Playlist.objects.create(name='Плейлист', user=self.user)
        self.artist = Artist.objects.create(name='Артист')
        self.track = Track.objects.create(title='Трек', audio_file='tracks/test.mp3')
        self.track.artists.add(self.artist)
        self.playlist.tracks.add(self.track)
        self.client.force_login(self.user)

    def remove_url(self):
        return f'/playlist/{self.playlist.id}/remove/{self.track.id}/'

    def test_htmx_post_removes_track_from_playlist(self):
        response = self.client.post(self.remove_url(), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.playlist.tracks.filter(id=self.track.id).exists())

    def test_removal_is_post_only(self):
        response = self.client.get(self.remove_url())

        self.assertEqual(response.status_code, 405)
        self.assertTrue(self.playlist.tracks.filter(id=self.track.id).exists())


class PlaylistVisibilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner-user', password='secret')
        self.other = User.objects.create_user('other-user', password='secret')
        self.playlist = Playlist.objects.create(name='Открытый', user=self.owner)

    def detail_url(self):
        return f'/playlist/{self.playlist.id}/'

    def test_open_playlist_is_visible_to_another_user(self):
        self.client.force_login(self.other)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Открытый')

    def test_private_playlist_is_hidden_from_another_user(self):
        self.playlist.is_private = True
        self.playlist.save(update_fields=['is_private'])
        self.client.force_login(self.other)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 404)

    def test_owner_can_change_visibility(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            f'/playlist/{self.playlist.id}/visibility/',
            {'is_private': '1'},
        )

        self.assertRedirects(response, self.detail_url())
        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.is_private)

    def test_playlist_list_shows_categories(self):
        self.client.force_login(self.owner)

        response = self.client.get('/playlists/')

        self.assertContains(response, 'Мои плейлисты')
        self.assertContains(response, 'Все плейлисты')
        self.assertContains(response, 'Избранные плейлисты')
        self.assertNotContains(response, 'Закрытые плейлисты')

    def test_default_tab_shows_own_playlists_only(self):
        Playlist.objects.create(name='Мой закрытый', user=self.owner, is_private=True)
        Playlist.objects.create(name='Чужой открытый', user=self.other)
        self.client.force_login(self.owner)

        response = self.client.get('/playlists/')

        self.assertEqual(response.context['active_tab'], 'mine')
        self.assertContains(response, 'Открытый')
        self.assertContains(response, 'Мой закрытый')
        self.assertNotContains(response, 'Чужой открытый')

    def test_all_tab_shows_every_open_playlist(self):
        Playlist.objects.create(name='Мой закрытый', user=self.owner, is_private=True)
        Playlist.objects.create(name='Чужой открытый', user=self.other)
        Playlist.objects.create(name='Чужой закрытый', user=self.other, is_private=True)
        self.client.force_login(self.owner)

        response = self.client.get('/playlists/?tab=all')

        self.assertEqual(response.context['active_tab'], 'all')
        self.assertContains(response, 'Открытый')
        self.assertContains(response, 'Чужой открытый')
        self.assertNotContains(response, 'Мой закрытый')
        self.assertNotContains(response, 'Чужой закрытый')

    def test_favorites_tab_shows_favorited_open_playlists(self):
        FavoritePlaylist.objects.create(user=self.other, playlist=self.playlist)
        self.client.force_login(self.other)

        response = self.client.get('/playlists/?tab=favorites')

        self.assertEqual(response.context['active_tab'], 'favorites')
        self.assertContains(response, 'Открытый')

    def test_unknown_tab_falls_back_to_mine(self):
        self.client.force_login(self.owner)

        response = self.client.get('/playlists/?tab=unknown')

        self.assertEqual(response.context['active_tab'], 'mine')

    def test_own_private_playlist_is_listed_in_mine_tab(self):
        Playlist.objects.create(name='Мой закрытый', user=self.owner, is_private=True)
        self.client.force_login(self.owner)

        response = self.client.get('/playlists/?tab=mine')

        self.assertContains(response, 'Мой закрытый')

    def test_non_owner_cannot_manage_playlist(self):
        self.client.force_login(self.other)

        cover_response = self.client.post(
            f'/playlist/{self.playlist.id}/cover/',
            {'remove_cover': '1'},
        )
        visibility_response = self.client.post(
            f'/playlist/{self.playlist.id}/visibility/',
            {'is_private': '1'},
        )
        delete_response = self.client.get(f'/playlist/{self.playlist.id}/delete/')

        self.assertEqual(cover_response.status_code, 404)
        self.assertEqual(visibility_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.playlist.refresh_from_db()
        self.assertFalse(self.playlist.is_private)


class PlaylistCreateVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('creator-user', password='secret')
        self.client.force_login(self.user)

    def test_create_with_open_choice_saves_open_playlist(self):
        response = self.client.post(
            '/playlist/create/',
            {'name': 'Новый открытый', 'is_private': '0'},
        )

        playlist = Playlist.objects.get(name='Новый открытый')
        self.assertFalse(playlist.is_private)
        self.assertRedirects(response, f'/playlist/{playlist.id}/')

    def test_create_with_private_choice_saves_private_playlist(self):
        self.client.post(
            '/playlist/create/',
            {'name': 'Новый закрытый', 'is_private': '1'},
        )

        playlist = Playlist.objects.get(name='Новый закрытый')
        self.assertTrue(playlist.is_private)

    def test_create_without_choice_defaults_to_open(self):
        self.client.post('/playlist/create/', {'name': 'Без выбора'})

        playlist = Playlist.objects.get(name='Без выбора')
        self.assertFalse(playlist.is_private)


class PlaylistFavoriteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner-user', password='secret')
        self.other = User.objects.create_user('other-user', password='secret')
        self.playlist = Playlist.objects.create(name='Чужой плейлист', user=self.owner)

    def like_url(self):
        return f'/like-playlist/{self.playlist.id}/'

    def test_other_user_can_toggle_favorite(self):
        self.client.force_login(self.other)

        response = self.client.get(self.like_url())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['liked'])
        self.assertTrue(
            FavoritePlaylist.objects.filter(
                user=self.other,
                playlist=self.playlist,
            ).exists()
        )

        response = self.client.get(self.like_url())

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['liked'])
        self.assertFalse(
            FavoritePlaylist.objects.filter(
                user=self.other,
                playlist=self.playlist,
            ).exists()
        )

    def test_owner_cannot_favorite_own_playlist(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.like_url())

        self.assertEqual(response.status_code, 400)
        self.assertFalse(FavoritePlaylist.objects.exists())

    def test_private_playlist_cannot_be_favorited(self):
        self.playlist.is_private = True
        self.playlist.save(update_fields=['is_private'])
        self.client.force_login(self.other)

        response = self.client.get(self.like_url())

        self.assertEqual(response.status_code, 404)
        self.assertFalse(FavoritePlaylist.objects.exists())

    def test_favorites_page_shows_favorited_playlist(self):
        FavoritePlaylist.objects.create(user=self.other, playlist=self.playlist)
        self.client.force_login(self.other)

        response = self.client.get('/favorites/')

        self.assertContains(response, 'Избранные плейлисты')
        self.assertContains(response, 'Чужой плейлист')

    def test_favorite_heart_is_shown_on_playlist_detail(self):
        FavoritePlaylist.objects.create(user=self.other, playlist=self.playlist)
        self.client.force_login(self.other)

        response = self.client.get(f'/playlist/{self.playlist.id}/')

        self.assertContains(response, 'like-playlist-btn active')


class IndexPageTests(TestCase):
    def setUp(self):
        artist = Artist.objects.create(name='Артист')
        for index in range(12):
            album = Album.objects.create(title=f'Альбом {index}', year=2020)
            album.artists.add(artist)
            Track.objects.create(
                title=f'Трек {index}',
                audio_file=f'tracks/{index}.mp3',
                plays=index,
            )

    def test_index_shows_ten_new_albums_and_ten_popular_tracks(self):
        response = self.client.get('/')

        self.assertEqual(len(response.context['albums']), 10)
        self.assertEqual(len(response.context['popular_tracks']), 10)
        self.assertContains(response, 'new-albums-next')
        self.assertContains(response, 'data-album-card="9"')
        self.assertContains(
            response,
            'class="col-md-3 col-lg-2 is-hidden"',
            count=4,
        )


class StreamAudioTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix='pupu-test-media-')
        cls._override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)

    def make_track_file(self):
        tracks_dir = os.path.join(self._media_root, 'tracks')
        os.makedirs(tracks_dir, exist_ok=True)
        with open(os.path.join(tracks_dir, 'demo.mp3'), 'wb') as f:
            f.write(b'ID3-demo-audio')

    def test_path_traversal_is_blocked(self):
        response = self.client.get('/stream/../db.sqlite3/')

        self.assertEqual(response.status_code, 404)

    def test_serves_file_inside_media_root(self):
        self.make_track_file()

        response = self.client.get('/stream/tracks/demo.mp3/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(b''.join(response.streaming_content), b'ID3-demo-audio')

    def test_range_request_returns_partial_content(self):
        self.make_track_file()

        response = self.client.get('/stream/tracks/demo.mp3/', HTTP_RANGE='bytes=0-2')

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], 'bytes 0-2/14')
        self.assertEqual(b''.join(response.streaming_content), b'ID3')


class RecordListenTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name='Артист')
        self.track = Track.objects.create(title='Трек', audio_file='tracks/listen.mp3')

    def test_anonymous_listen_increments_plays(self):
        response = self.client.post(f'/record-listen/{self.track.id}/')

        self.assertEqual(response.status_code, 200)
        self.track.refresh_from_db()
        self.assertEqual(self.track.plays, 1)

    def test_authenticated_listen_saves_history(self):
        user = User.objects.create_user('listen-user', password='secret')
        self.client.force_login(user)

        self.client.post(f'/record-listen/{self.track.id}/')

        self.assertEqual(user.listening_history.count(), 1)
        self.track.refresh_from_db()
        self.assertEqual(self.track.plays, 1)

    def test_record_listen_is_post_only(self):
        response = self.client.get(f'/record-listen/{self.track.id}/')

        self.assertEqual(response.status_code, 405)

    def test_listen_credits_every_artist_on_track(self):
        second_artist = Artist.objects.create(name='Второй артист')
        self.track.artists.add(self.artist, second_artist)

        response = self.client.post(
            f'/record-listen/{self.track.id}/', {'percent': '30.01'}
        )

        self.assertEqual(response.status_code, 200)
        self.track.refresh_from_db()
        self.artist.refresh_from_db()
        second_artist.refresh_from_db()
        self.assertEqual(self.track.plays, 1)
        self.assertEqual(self.artist.plays, 1)
        self.assertEqual(second_artist.plays, 1)

    def test_listen_below_threshold_is_not_counted(self):
        self.track.artists.add(self.artist)

        response = self.client.post(
            f'/record-listen/{self.track.id}/', {'percent': '30'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'skipped')
        self.track.refresh_from_db()
        self.artist.refresh_from_db()
        self.assertEqual(self.track.plays, 0)
        self.assertEqual(self.artist.plays, 0)

