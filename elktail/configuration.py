import os
import sys
import errno
import configparser


def get_config():
    """Get configuration from system or user config file."""
    # Try system-wide config first
    system_config = '/etc/elktail.conf'
    user_config = os.path.join(
        os.environ.get("HOME"),
        ".config/elktail/config.ini"
    )
    
    # Check system config first, then user config
    config_path = system_config if os.path.exists(system_config) else user_config

    if not os.path.exists(config_path):
        print("your elktail is not configured")
        opt = str(input("would you like to configure it now? <Y/n>: "))

        if opt in ['Y', 'y', 'yes', 'YES']:
            config_creator(config_path)

        sys.exit(-1)

    config = configparser.ConfigParser()
    config.read(config_path)
    return {
        'host': config['default']['host'],
        'username': config['default']['username'],
        'scheme': config['default']['scheme'],
        'password': config['default']['password'],
        'port': int(config['default']['port'])
    }


def config_creator(config_path):
    print(f"creating configuration file: {config_path}")

    try:
        os.makedirs(
            os.path.join(
                os.environ.get("HOME"),
                ".config/elktail"
            )
        )
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    host = input("elasticsearch host: ")
    username = input("username: ")
    password = input("password: ")
    scheme = input("scheme (HIGLY recommended https): ")
    port = input("port: ")

    config = configparser.RawConfigParser()
    config.add_section("default")
    config.set("default", "host", host)
    config.set("default", "username", username)
    config.set("default", "password", password)
    config.set("default", "scheme", scheme)
    config.set("default", "port", port)

    with open(config_path, 'w') as configfile:
        config.write(configfile)

    print("elktail configured")


def get_config_file():
    """Get the path to the configuration file."""
    # First try /etc/elktail.conf
    system_config = '/etc/elktail.conf'
    if os.path.exists(system_config):
        return system_config
        
    # Fallback to user config for backward compatibility
    user_config_dir = os.path.expanduser('~/.config/elktail')
    user_config = os.path.join(user_config_dir, 'config.ini')
    
    return user_config

def create_config():
    """Create a new configuration file."""
    config_file = '/etc/elktail.conf'
    
    print('your elktail is not configured')
    answer = input('would you like to configure it now? <Y/n>: ')
    if answer.lower() != 'y':
        sys.exit(1)
    
    print(f'creating configuration file: {config_file}')
    
    config = configparser.ConfigParser()
    config['default'] = {}
    
    config['default']['host'] = input('elasticsearch host: ')
    config['default']['username'] = input('username: ')
    config['default']['password'] = input('password: ')
    config['default']['scheme'] = input('scheme (HIGLY recommended https): ')
    config['default']['port'] = input('port: ')
    
    try:
        with open(config_file, 'w') as f:
            config.write(f)
        # Set secure permissions
        os.chmod(config_file, 0o600)
        print('elktail configured')
    except PermissionError:
        print(f'Error: Cannot write to {config_file}. Please run with sudo to create system-wide configuration.')
        sys.exit(1)
