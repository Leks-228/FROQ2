import os
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.forms import formset_factory
from django.http import (
    FileResponse, HttpResponseNotAllowed, HttpResponseBadRequest,
    Http404, JsonResponse, StreamingHttpResponse, HttpResponse
)
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction
from django.db.models import F, Q
from django.utils._os import safe_join
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .forms import RegisterForm, TrackUploadForm, AlbumUploadForm, TrackForm, BaseTrackFormSet
from .forms import UserEditForm, ProfileEditForm, CustomPasswordChangeForm
from .forms import PlaylistForm, PlaylistCoverForm
from .models import Artist, Album, Track, Favorite, FavoriteAlbum, Playlist, ListeningHistory, Profile


def _safe_media_path(file_path):
    """
    Путь внутри MEDIA_ROOT. safe_join не даёт выйти за его пределы
    (например, /stream/../db.sqlite3/ больше не отдаст файл).
    """
    try:
        return safe_join(settings.MEDIA_ROOT, file_path)
    except SuspiciousFileOperation:
        raise Http404("Файл не найден")


def _serve_file(request, full_path, default_content_type='application/octet-stream'):
    """Отдаёт локальный файл с поддержкой Range-запросов (нужно для seek в плеере)."""
    size = os.path.getsize(full_path)
    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or default_content_type

    range_header = request.META.get('HTTP_RANGE', '').strip()
    if range_header:
        match = range_header.split('=')
        if len(match) == 2 and match[0] == 'bytes':
            byte_range = match[1].split(',')[0]
            start, end = byte_range.split('-')
            start = int(start) if start else 0
            end = int(end) if end else size - 1
            if start >= size or end >= size or start > end:
                return HttpResponse(status=416)

            length = end - start + 1
            response = StreamingHttpResponse(
                file_iterator(full_path, start, end),
                status=206,
                content_type=content_type
            )
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
            response['Content-Length'] = str(length)
            response['Accept-Ranges'] = 'bytes'
            return response

    response = StreamingHttpResponse(
        file_iterator(full_path, 0, size - 1),
        content_type=content_type
    )
    response['Content-Length'] = str(size)
    response['Accept-Ranges'] = 'bytes'
    return response


def stream_audio(request, file_path):
    full_path = _safe_media_path(file_path)

    if not os.path.exists(full_path):
        # Файла нет на диске — возможно, он лежит в облачном хранилище
        # (Cloudinary). Тогда отдаём редирект на его публичный URL.
        track = Track.objects.filter(audio_file=file_path).only('audio_file').first()
        if track is not None:
            try:
                remote_url = track.audio_file.url
            except Exception:
                remote_url = None
            if remote_url and remote_url.startswith(('http://', 'https://')):
                return redirect(remote_url)
        raise Http404("Файл не найден")

    return _serve_file(request, full_path, default_content_type='audio/mpeg')


def serve_media(request, file_path):
    """
    Раздача MEDIA_ROOT через Django для варианта без Cloudinary
    (например, на VPS с постоянным диском). При DEBUG=True этот маршрут
    не подключается — там работает django.conf.urls.static.
    """
    full_path = _safe_media_path(file_path)
    if not os.path.isfile(full_path):
        raise Http404("Файл не найден")
    return _serve_file(request, full_path)


def file_iterator(file_path, start, end, chunk_size=8192):
    with open(file_path, 'rb') as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)


def get_liked_track_ids(user):
    if user.is_authenticated:
        return list(Favorite.objects.filter(user=user).values_list('track_id', flat=True))
    return []


def index(request):
    # prefetch/select_related убирают N+1: иначе на 100 треках
    # страница делает сотни запросов к базе.
    tracks = Track.objects.select_related('album').prefetch_related('artists')
    popular_tracks = (
        Track.objects.select_related('album')
        .prefetch_related('artists')
        .order_by('-plays')[:5]
    )
    albums = Album.objects.prefetch_related('artists').order_by('-created_at')[:8]
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/index.html', {
        'tracks': tracks,
        'popular_tracks': popular_tracks,
        'albums': albums,
        'liked_track_ids': liked_track_ids,
    })


def popular_playlist(request):
    popular_tracks = (
        Track.objects.select_related('album')
        .prefetch_related('artists')
        .order_by('-plays')
    )
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/popular.html', {
        'popular_tracks': popular_tracks,
        'liked_track_ids': liked_track_ids,
    })


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = RegisterForm()
    return render(request, 'main/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'main/login.html', {'form': form})


@staff_member_required
def upload_track(request):
    if request.method == 'POST':
        form = TrackUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = TrackUploadForm()
    return render(request, 'main/upload.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('index')


def album_detail(request, album_id):
    album = get_object_or_404(Album.objects.prefetch_related('artists'), id=album_id)
    tracks = (
        album.tracks.select_related('album')
        .prefetch_related('artists')
        .order_by('track_number')
    )
    liked_track_ids = get_liked_track_ids(request.user)
    is_favorite_album = False
    if request.user.is_authenticated:
        is_favorite_album = FavoriteAlbum.objects.filter(user=request.user, album=album).exists()
    return render(request, 'main/album.html', {
        'album': album,
        'tracks': tracks,
        'liked_track_ids': liked_track_ids,
        'is_favorite_album': is_favorite_album,
    })


@staff_member_required
def upload_album(request):
    TrackFormSet = formset_factory(TrackForm, formset=BaseTrackFormSet, extra=1)

    if request.method == 'POST':
        album_form = AlbumUploadForm(request.POST, request.FILES)
        track_formset = TrackFormSet(request.POST, request.FILES, prefix='tracks')

        if album_form.is_valid() and track_formset.is_valid():
            album = album_form.save()

            for form in track_formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    if form.cleaned_data.get('title') and form.cleaned_data.get('audio_file'):
                        track = form.save(commit=False)
                        track.album = album
                        track.save()
                        track.artists.set(album.artists.all())

            return redirect('album_detail', album_id=album.id)
    else:
        album_form = AlbumUploadForm()
        track_formset = TrackFormSet(prefix='tracks')

    return render(request, 'main/upload_album.html', {
        'album_form': album_form,
        'track_formset': track_formset
    })


def artist_detail(request, artist_id):
    artist = get_object_or_404(Artist, id=artist_id)
    albums = artist.albums.prefetch_related('artists')
    tracks = (
        artist.tracks.select_related('album')
        .prefetch_related('artists')
        .order_by('-plays')[:10]
    )
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/artist.html', {
        'artist': artist,
        'albums': albums,
        'tracks': tracks,
        'liked_track_ids': liked_track_ids,
        'monthly_plays': artist.get_monthly_plays(),
    })


@login_required
def like_track(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, track=track)
    if not created:
        favorite.delete()
    return JsonResponse({'liked': created})


@login_required
def like_album(request, album_id):
    album = get_object_or_404(Album, id=album_id)
    favorite, created = FavoriteAlbum.objects.get_or_create(user=request.user, album=album)
    if not created:
        favorite.delete()
    return JsonResponse({'liked': created})


@login_required
def favorites(request):
    query = request.GET.get('q', '').strip()
    tracks = (
        Track.objects.select_related('album')
        .prefetch_related('artists')
        .filter(favorited_by__user=request.user)
    )
    if query:
        tracks = tracks.filter(
            Q(title__icontains=query) | Q(artists__name__icontains=query)
        ).distinct()
    liked_track_ids = list(tracks.values_list('id', flat=True))
    favorite_albums = (
        Album.objects.prefetch_related('artists')
        .filter(favorited_by__user=request.user)
    )
    return render(request, 'main/favorites.html', {
        'tracks': tracks,
        'liked_track_ids': liked_track_ids,
        'query': query,
        'favorite_albums': favorite_albums,
    })


@login_required
def check_like(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    liked = Favorite.objects.filter(user=request.user, track=track).exists()
    return JsonResponse({'liked': liked})


def search(request):
    query = request.GET.get('q', '').strip()
    tracks = []
    artists = []
    albums = []
    if query:
        tracks = (
            Track.objects.select_related('album')
            .prefetch_related('artists')
            .filter(Q(title__icontains=query) | Q(artists__name__icontains=query))
            .distinct()
        )
        artists = Artist.objects.filter(name__icontains=query)
        albums = (
            Album.objects.prefetch_related('artists')
            .filter(title__icontains=query)
        )
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/search.html', {
        'query': query,
        'tracks': tracks,
        'artists': artists,
        'albums': albums,
        'liked_track_ids': liked_track_ids,
    })


# --- Плейлисты ---

@login_required
def playlist_list(request):
    playlists = request.user.playlists.all()
    return render(request, 'main/playlist_list_page.html', {'playlists': playlists})


@login_required
def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    tracks = (
        playlist.tracks.select_related('album').prefetch_related('artists').all()
    )
    query = request.GET.get('q', '').strip()
    if query:
        tracks = tracks.filter(
            Q(title__icontains=query) | Q(artists__name__icontains=query)
        ).distinct()
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/playlist_detail.html', {
        'playlist': playlist,
        'tracks': tracks,
        'liked_track_ids': liked_track_ids,
        'query': query,
        'cover_form': PlaylistCoverForm(instance=playlist),
    })


@login_required
def create_playlist(request):
    form = PlaylistForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            playlist = form.save(commit=False)
            playlist.user = request.user
            playlist.save()
            # При HTMX-отправке возвращаем только фрагмент страницы плейлиста.
            # Форма создания использует hx-swap="innerHTML" по #main-content
            # (без hx-select), поэтому подменяется только содержимое области,
            # а фиксированный плеер (hx-preserve, вне #main-content) и сам
            # элемент #main-content сохраняются.
            if request.headers.get('HX-Request') == 'true':
                tracks = (
                    playlist.tracks.select_related('album')
                    .prefetch_related('artists')
                    .all()
                )
                response = render(request, 'main/playlist_detail_content.html', {
                    'playlist': playlist,
                    'tracks': tracks,
                    'liked_track_ids': get_liked_track_ids(request.user),
                    'query': '',
                    'cover_form': PlaylistCoverForm(instance=playlist),
                })
                response['HX-Push-Url'] = reverse('playlist_detail', args=[playlist.id])
                return response
            return redirect('playlist_detail', playlist_id=playlist.id)
        # Ошибки валидации: для HTMX отдаём фрагмент формы, чтобы swap
        # innerHTML не получил полный документ.
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'main/create_playlist_content.html', {'form': form})
    return render(request, 'main/create_playlist.html', {'form': form})


def _is_ajax(request):
    """Запрос отправлен через fetch/htmx, а не обычной отправкой формы."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


@login_required
@require_POST
def update_playlist_cover(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    is_ajax = _is_ajax(request)

    if request.POST.get('remove_cover'):
        if playlist.cover:
            try:
                playlist.cover.storage.delete(playlist.cover.name)
            except Exception:
                # Не мешаем убрать обложку из плейлиста, даже если
                # удалить сам файл в хранилище не удалось.
                pass
        playlist.cover = None
        playlist.save(update_fields=['cover'])
        if is_ajax:
            return JsonResponse({'success': True, 'has_cover': False, 'cover_url': ''})
        return redirect('playlist_detail', playlist_id=playlist.id)

    # Имя старого файла нужно запомнить до валидации формы: после
    # form.is_valid() экземпляр уже указывает на только что загруженный файл.
    old_cover_name = playlist.cover.name if playlist.cover else None

    form = PlaylistCoverForm(request.POST, request.FILES, instance=playlist)
    if form.is_valid():
        form.save()
        new_cover_name = playlist.cover.name if playlist.cover else None
        # Удаляем старый файл только после успешного сохранения нового,
        # иначе можно случайно стереть только что загруженную обложку.
        if old_cover_name and old_cover_name != new_cover_name:
            try:
                playlist.cover.storage.delete(old_cover_name)
            except Exception:
                # Обложка уже сохранена — ошибка удаления старого файла
                # не должна ломать ответ пользователю.
                pass
        if is_ajax:
            return JsonResponse({
                'success': True,
                'has_cover': bool(playlist.cover),
                'cover_url': playlist.cover.url if playlist.cover else '',
            })
        return redirect('playlist_detail', playlist_id=playlist.id)

    errors = [str(error) for field_errors in form.errors.values() for error in field_errors]
    if not errors:
        errors = ['Не удалось сохранить обложку. Выберите файл изображения.']
    if is_ajax:
        return JsonResponse({'success': False, 'errors': errors}, status=400)
    messages.error(request, ' '.join(errors))
    return redirect('playlist_detail', playlist_id=playlist.id)


@login_required
def user_playlists(request):
    playlists = request.user.playlists.all()
    track_id = request.GET.get('track_id')
    return render(request, 'main/playlist_list.html', {
        'playlists': playlists,
        'track_id': track_id
    })


@require_POST
@login_required
def add_to_playlist(request, track_id):
    track = get_object_or_404(Track, id=track_id)
    playlist_id = request.POST.get('playlist_id')
    if not playlist_id:
        return JsonResponse({'success': False, 'error': 'Плейлист не указан'}, status=400)
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    if track not in playlist.tracks.all():
        playlist.tracks.add(track)
        return JsonResponse({'success': True, 'message': f'Трек добавлен в «{playlist.name}»'})
    else:
        return JsonResponse({'success': False, 'error': 'Трек уже в этом плейлисте'})


@login_required
@require_POST
def remove_from_playlist(request, playlist_id, track_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    track = get_object_or_404(Track, id=track_id)
    playlist.tracks.remove(track)
    # HTMX: элемент трека удаляется на клиенте через hx-swap="delete",
    # поэтому достаточно пустого успешного ответа.
    if request.headers.get('HX-Request') == 'true':
        return HttpResponse(status=200)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('playlist_detail', playlist_id=playlist.id)


# --- История прослушиваний ---

@require_POST
def record_listen(request, track_id):
    track = get_object_or_404(Track, id=track_id)

    # Прослушивание засчитывается только после 30% трека. Клиент присылает
    # процент; если его нет (например, старый клиент или прямой запрос),
    # считаем запрос доверенным, чтобы не ломать обратную совместимость.
    percent = request.POST.get('percent')
    if percent not in (None, ''):
        try:
            percent = float(percent)
        except (TypeError, ValueError):
            return JsonResponse(
                {'status': 'error', 'error': 'Некорректный процент прослушивания'},
                status=400,
            )
        if percent <= 30:
            return JsonResponse({'status': 'skipped'})

    artist_ids = list(track.artists.values_list('id', flat=True))

    with transaction.atomic():
        # Историю ведём только для вошедших, а счётчики прослушиваний —
        # для всех: иначе «Популярное» не работает у анонимных слушателей.
        if request.user.is_authenticated:
            ListeningHistory.objects.create(user=request.user, track=track)
        Track.objects.filter(id=track.id).update(plays=F('plays') + 1)
        # Прослушивание засчитывается каждому исполнителю трека.
        if artist_ids:
            Artist.objects.filter(id__in=artist_ids).update(plays=F('plays') + 1)

    return JsonResponse({'status': 'ok'})


@login_required
def listening_history(request):
    history = (
        request.user.listening_history
        .select_related('track', 'track__album')
        .prefetch_related('track__artists')
        .all()
    )
    liked_track_ids = get_liked_track_ids(request.user)
    return render(request, 'main/history.html', {
        'history': history,
        'liked_track_ids': liked_track_ids,
    })


# --- Профиль ---

@login_required
def profile_view(request):
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    stats = {
        'favorites_count': request.user.favorites.count(),
        'playlists_count': request.user.playlists.count(),
        'history_count': request.user.listening_history.count(),
    }
    return render(request, 'main/profile.html', {
        'profile': profile,
        'stats': stats
    })


@login_required
def profile_edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)
        profile_form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль обновлён.')
            return redirect('profile')
    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = ProfileEditForm(instance=profile)

    return render(request, 'main/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успешно изменён.')
            return redirect('profile')
    else:
        form = CustomPasswordChangeForm(user=request.user)
    return render(request, 'main/change_password.html', {'form': form})

@login_required
def delete_playlist(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    if playlist.cover:
        playlist.cover.delete(save=False)
    playlist.delete()
    return redirect('playlist_list')