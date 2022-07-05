from decimal import Decimal
import logging
from datetime import timedelta as td
from crypto import BalanceType

LAUNCH_CONFIG_OPTIONS = {
    'dev': {
        'logging_level': logging.INFO,
        'subscription_period': 'minute',
        'subscription_fee': Decimal(3) / 100,
        'crypto': {
            'balance': BalanceType.CRYPTO,
            'token_name': 'USDC',
            'token_address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'decimals': 6,
            'solana_url': 'https://api.mainnet-beta.solana.com',
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
        'logging_level': logging.INFO,
        'subscription_period': 'minute',
        'subscription_fee': Decimal(3) / 100,
        'crypto': {
            'balance': BalanceType.CRYPTO,
            'token_name': 'USDC',
            'token_address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'decimals': 6,
            'solana_url': 'https://api.mainnet-beta.solana.com',
        },
        'updates_frequency': {
            (td(minutes=1), td(seconds=20)),
            (td(hours=1), td(minutes=3)),
            (td(days=1), td(hours=1)),
            (td(days=365), td(days=1)),
        },
        'roles': [
            'BotTestRole',
        ],
        'info_channel_name': 'bot-log',
    },
}
