# Деплой на PythonAnywhere

Схема: **PythonAnywhere** (сайт) + **SQLite** (база) + **локальные файлы**
(треки, обложки, аватары). Внешние БД и облачные хранилища не используются.

## 1. Куда положить код

Загрузите проект в `/home/<username>/<project>` (например,
`/home/sasha/freq`). Удобнее всего через `git clone` / `git pull` —
тогда обновления не затрагивают файлы, которых нет в репозитории.

## 2. Виртуальное окружение

В Bash-консоли PythonAnywhere:

```bash
cd /home/<username>/<project>
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Постоянная папка с данными

Чтобы обновление кода не удаляло треки, обложки и аккаунты, база и media
хранятся вне папки проекта:

```bash
mkdir -p /home/<username>/freq-data
```

При первом запуске Django сам скопирует туда существующие `db.sqlite3`
и `media/`, если они есть в проекте. Старые файлы остаются как резервная
копия.

Затем в WSGI-файле (вкладка **Web → WSGI configuration file**) добавьте
строку с путём к этой папке:

```python
os.environ['FREQ_DATA_DIR'] = '/home/<username>/freq-data'
```

После этого база будет лежать в
`/home/<username>/freq-data/db.sqlite3`, а файлы — в
`/home/<username>/freq-data/media/`.

## 4. Настройки Django в WSGI

В том же WSGI-файле перед импортом приложения укажите:

```python
import os
import sys

path = '/home/<username>/<project>'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'music_site.settings'
os.environ['DEBUG'] = 'False'
os.environ['SECRET_KEY'] = 'длинный-случайный-секрет'
os.environ['ALLOWED_HOSTS'] = '<username>.pythonanywhere.com'
os.environ['FREQ_DATA_DIR'] = '/home/<username>/freq-data'

from music_site.wsgi import application
```

Если подключён свой домен, добавьте его в `ALLOWED_HOSTS` через запятую.

## 5. Первый запуск

В Bash-консоли:

```bash
cd /home/<username>/<project>
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 6. Статика и медиа на вкладке Web

В разделе **Static files** добавьте два соответствия:

| URL | Directory |
|---|---|
| `/static/` | `/home/<username>/<project>/staticfiles` |
| `/media/` | `/home/<username>/freq-data/media` |

После этого нажмите **Reload**.

## 7. Как обновлять сайт

```bash
cd /home/<username>/<project>
source venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Затем **Reload** на вкладке Web.

`db.sqlite3` и `media/` в git не входят, а на PythonAnywhere лежат в
`/home/<username>/freq-data`, поэтому при обновлении кода они не удаляются.
Не удаляйте папку `freq-data` — это все треки, обложки и аккаунты.

## 8. Проверка перед обновлением

```bash
python manage.py check
python manage.py test
```
