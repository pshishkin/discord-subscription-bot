import logging

LAUNCH_CONFIG_OPTIONS = {
    'dev': {
        'logging_level': logging.INFO,
    },
    'prod': {
        'logging_level': logging.WARN,
    },
}