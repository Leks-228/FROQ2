import io
import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from PIL import Image

from music_site.storage import SmartCloudinaryStorage

from .models import Playlist, Track, Artist


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


class CloudinaryResourceTypeTests(SimpleTestCase):
    """Cloudinary для image/video возвращает public_id без расширения,
    поэтому mp3 в media/tracks/ должен определяться как video, а не image."""

    def setUp(self):
        self.storage = SmartCloudinaryStorage()

    def test_audio_public_id_without_extension_is_video(self):
        self.assertEqual(self.storage._get_resource_type('media/tracks/song'), 'video')
        self.assertEqual(self.storage._get_resource_type('tracks/song'), 'video')

    def test_audio_with_extension_is_video(self):
        self.assertEqual(self.storage._get_resource_type('media/tracks/song.mp3'), 'video')
        self.assertEqual(self.storage._get_resource_type('tracks/song.flac'), 'video')

    def test_images_are_still_images(self):
        self.assertEqual(self.storage._get_resource_type('media/covers/cover'), 'image')
        self.assertEqual(self.storage._get_resource_type('media/avatars/photo.jpg'), 'image')


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

