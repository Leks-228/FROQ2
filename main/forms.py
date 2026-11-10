from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Track, Artist, Album, Playlist
from django.forms import formset_factory, BaseFormSet
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from .models import Profile

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class TrackUploadForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = ['title', 'artists', 'album', 'track_number', 'audio_file']
        labels = {
            'title': 'Название',
            'artists': 'Исполнитель',
            'album': 'Альбом',
            'track_number': 'Номер трека',
            'audio_file': 'MP3 файл'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['artists'].queryset = Artist.objects.all()
        self.fields['album'].queryset = Album.objects.all()
        self.fields['album'].required = False
        
class AlbumUploadForm(forms.ModelForm):
    class Meta:
        model = Album
        fields = ['title', 'artists', 'year', 'type', 'cover']
        widgets = {
            'artists': forms.CheckboxSelectMultiple,
        }
        labels = {
            'title': 'Название альбома',
            'artists': 'Исполнители',
            'year': 'Год выпуска',
            'type': 'Тип',
            'cover': 'Обложка'
        }

class TrackForm(forms.ModelForm):
    class Meta:
        model = Track
        fields = ['title', 'track_number', 'audio_file']
        labels = {
            'title': 'Название трека',
            'track_number': 'Номер трека',
            'audio_file': 'MP3 файл'
        }

# Базовый formset для нескольких треков
class BaseTrackFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        titles = []
        for form in self.forms:
            if form.cleaned_data and form.cleaned_data.get('title') and not form.cleaned_data.get('DELETE', False):
                title = form.cleaned_data['title']
                if title in titles:
                    raise forms.ValidationError("Треки с одинаковыми названиями в одном альбоме")
                titles.append(title)
    
    def should_delete(self, form):
        """Помечает пустые формы как подлежащие удалению"""
        return not form.has_changed() and form not in self.extra_forms
    
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'bio']

class CustomPasswordChangeForm(PasswordChangeForm):
    # Можно оставить стандартную
    pass

class PlaylistForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = ['name', 'cover', 'is_private']
        labels = {
            'name': 'Название плейлиста',
            'cover': 'Обложка плейлиста',
            'is_private': 'Закрытый плейлист',
        }
        widgets = {
            # RadioSelect (а не CheckboxInput) нужен, чтобы значение "0"
            # из формы не превращалось в True: CheckboxInput считает
            # непустую строку "0" истиной.
            'is_private': forms.RadioSelect(choices=[
                (False, 'Открытый'),
                (True, 'Закрытый'),
            ]),
        }

class PlaylistCoverForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = ['cover']
        labels = {
            'cover': 'Обложка плейлиста',
        }