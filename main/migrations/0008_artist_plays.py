# Generated manually for artist play counters

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_playlist_cover'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='plays',
            field=models.IntegerField(default=0, verbose_name='Прослушивания'),
        ),
    ]
