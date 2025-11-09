# Generated migration for Decision model

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Decision',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ticker', models.CharField(db_index=True, max_length=10)),
                ('action', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell'), ('HOLD', 'Hold')], max_length=4)),
                ('shares', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('strategy', models.CharField(choices=[('secure', 'Secure'), ('moderate', 'Moderate'), ('aggressive', 'Aggressive')], max_length=20)),
                ('reasoning', models.TextField(blank=True, null=True)),
                ('recommendation', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='trading.portfolio')),
            ],
            options={
                'db_table': 'decisions',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='decision',
            index=models.Index(fields=['portfolio', 'strategy', 'timestamp'], name='decisions_portfo_strate_idx'),
        ),
        migrations.AddIndex(
            model_name='decision',
            index=models.Index(fields=['portfolio', 'ticker'], name='decisions_portfo_ticker_idx'),
        ),
        migrations.AddIndex(
            model_name='decision',
            index=models.Index(fields=['strategy', 'timestamp'], name='decisions_strategy_timestamp_idx'),
        ),
    ]

