from django.db import migrations, models


def copy_artist_to_artists(apps, schema_editor):
    """Переносим существующего исполнителя альбома в новое поле many-to-many."""
    Album = apps.get_model('main', 'Album')
    db_alias = schema_editor.connection.alias
    for album in Album.objects.using(db_alias).all():
        if album.artist_id:
            album.artists.add(album.artist_id)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='artists',
            field=models.ManyToManyField(
                blank=True,
                related_name='albums_new',
                to='main.artist',
                verbose_name='Исполнители',
            ),
        ),
        migrations.RunPython(copy_artist_to_artists, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='album',
            name='artist',
        ),
        migrations.AlterField(
            model_name='album',
            name='artists',
            field=models.ManyToManyField(
                related_name='albums',
                to='main.artist',
                verbose_name='Исполнители',
            ),
        ),
    ]
