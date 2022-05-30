import logging
from datetime import timedelta as td
from crypto import BalanceType

LAUNCH_CONFIG_OPTIONS = {
    'dev': {
        'logging_level': logging.INFO,
        'subscription_period': 'minute',
        'subscription_fee': 2,
        'crypto': {
            'balance': BalanceType.DB_STORAGE
        },
        'updates_frequency': {
            (td(minutes=1), td(seconds=3)),
            (td(hours=1), td(minutes=3)),
            (td(days=1), td(hours=1)),
            (td(days=365), td(days=1)),
        },
        'roles': [
            'Подписчик',
        ],
        'info_channel_name': 'bot-info',
    },
    'prod': {
        'logging_level': logging.WARN,
        'subscription_fee': 2,
        'crypto': {
            'balance': BalanceType.CRYPTO
        }

    },
}