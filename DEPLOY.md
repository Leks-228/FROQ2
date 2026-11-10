# Деплой на Render

Схема: **Render** (сайт) + **Neon** (PostgreSQL) + **Cloudinary** (треки, обложки, аватары).

## 1. Что подготовить

1. **Git** и репозиторий на GitHub (в проекте уже есть `.gitignore`).
2. **Cloudinary** — https://cloudinary.com → Console → `Cloud name`, `API Key`, `API Secret`.
   - 100 треков по 3–5 МБ ≈ 300–500 МБ, это спокойно влезает в бесплатные 25 кредитов.
   - На free-плане 1 кредит = 1 ГБ трафика видео (аудио считается как видео),
     то есть примерно 5–8 тысяч полных прослушиваний в месяц.
3. **Neon** — https://neon.tech → создать проект → скопировать `postgresql://...?sslmode=require`.
4. **Render** — https://render.com.

## 2. Переменные окружения на Render

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | строка подключения из Neon |
| `CLOUDINARY_CLOUD_NAME` | Cloud name |
| `CLOUDINARY_API_KEY` | API key |
| `CLOUDINARY_API_SECRET` | API secret |
| `DJANGO_SUPERUSER_USERNAME` | логин админа |
| `DJANGO_SUPERUSER_PASSWORD` | пароль админа |
| `ALLOWED_HOSTS` | ваш домен, если подключили свой |
| `CSRF_TRUSTED_ORIGINS` | `https://ваш-домен`, если подключили свой |

`SECRET_KEY` Render генерирует сам (см. `render.yaml`).

## 3. Порядок

1. Запушить репозиторий на GitHub.
2. Render → **New** → **Blueprint** → выбрать репозиторий.
3. Заполнить переменные из таблицы выше.
4. Deploy. Сборка (`build.sh`) сама выполнит `collectstatic`, `migrate` и создаст админа.
5. Открыть `https://<имя>.onrender.com/admin/` и загрузить артистов, альбомы и треки.
6. Свой домен: Render → Settings → Custom Domain → CNAME у регистратора,
   затем добавить `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`.

## 4. Важно

- **Локальная база и папка media на прод не переезжают.** База будет пустая —
  треки нужно загрузить заново через админку (старые файлы лежат в `media/tracks/`).
- Без `CLOUDINARY_*` файлы сохранятся на диск Render и **пропадут** при следующем
  деплое/перезапуске, а `/media/` при `DEBUG=false` не раздаётся.
- Бесплатный Render засыпает через ~15 минут простоя: первый заход грузится 30–60 секунд.
- `DEBUG` должен быть `false` (уже задано в `render.yaml`).
- Задавать именно три переменные `CLOUDINARY_*`, а не одну `CLOUDINARY_URL`.

## 5. Проверка перед пушем

```bash
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```
