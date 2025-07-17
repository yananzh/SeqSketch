import os
import configparser

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
CONFIG_SECTION = 'BLAST'
CONFIG_KEY = 'bin_dir'

def get_blast_bin_dir():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        return None
    config.read(CONFIG_FILE, encoding='utf-8')
    if CONFIG_SECTION in config and CONFIG_KEY in config[CONFIG_SECTION]:
        return config[CONFIG_SECTION][CONFIG_KEY]
    return None

def set_blast_bin_dir(bin_dir):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
    if CONFIG_SECTION not in config:
        config[CONFIG_SECTION] = {}
    config[CONFIG_SECTION][CONFIG_KEY] = bin_dir
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f) 