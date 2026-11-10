from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_backfill_artist_plays'),
    ]

    operations = [
        migrations.AddField(
            model_name='playlist',
            name='is_private',
            field=models.BooleanField(default=False, verbose_name='Закрытый плейлист'),
        ),
    ]
