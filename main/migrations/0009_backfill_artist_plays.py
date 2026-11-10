# Заполняет счётчики исполнителей историческими прослушиваниями треков.

from django.db import migrations
from django.db.models import Sum


def backfill_artist_plays(apps, schema_editor):
    Artist = apps.get_model('main', 'Artist')
    Track = apps.get_model('main', 'Track')

    for artist in Artist.objects.all().iterator():
        total = (
            Track.objects.filter(artists=artist)
            .aggregate(total=Sum('plays'))['total'] or 0
        )
        if total:
            Artist.objects.filter(pk=artist.pk).update(plays=total)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_artist_plays'),
    ]

    operations = [
        migrations.RunPython(backfill_artist_plays, migrations.RunPython.noop),
    ]
