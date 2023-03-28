from dotenv import dotenv_values

__CONFIG = dotenv_values()


class EventBusError(Exception):
    pass


def get_config(config_name, default=None):
    if default:
        return __CONFIG.get(config_name, default)
    return __CONFIG.get(config_name)


def get_bootstrap_servers():
    try:
        return get_config('KAFKA_BOOTSTRAP_SERVERS')
    except KeyError:
        raise EventBusError(f'No config found for bootstrap servers from environment')