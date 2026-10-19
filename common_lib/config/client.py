import os
import logging
from dataclasses import dataclass
from pathlib import Path
from os.path import join
from configparser import ConfigParser
import yaml

logger = logging.getLogger('service')


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    host: str
    port: int

    @classmethod
    def from_service(cls):
        app_name = ConfigClient.get_property(key="APP_NAME", section="DEFAULT")
        app_env = os.getenv('APP_ENV', 'dev')
        host = ConfigClient.get_property(key="HOST", section="UVICORN")
        port = int(ConfigClient.get_property(key="PORT", section="UVICORN"))
        return cls(
            app_name=app_name,
            app_env=app_env,
            host=host,
            port=port,
        )


def detect_service_root() -> Path:
    """Resolve the current microservice root from the running working directory."""
    candidates = []
    cwd = Path.cwd().resolve()

    candidates.extend([
        cwd,
        cwd / 'src',
        cwd.parent,
        cwd.parent / 'src' if cwd.parent.exists() else None,
    ])

    for candidate in candidates:
        if candidate is None:
            continue
        config_file = candidate / 'config' / 'application.ini'
        if config_file.exists():
            return candidate
        if (candidate / 'src' / 'config' / 'application.ini').exists():
            return candidate / 'src'

    # Fallback: if running from inside src, use src; otherwise use cwd.
    if (cwd / 'config' / 'application.ini').exists():
        return cwd
    if (cwd / 'src' / 'config' / 'application.ini').exists():
        return cwd / 'src'

    return cwd


class ConfigClient:
    _config = None
    _base_path = None

    @classmethod
    def get_base_path(cls) -> Path:
        if cls._base_path is None:
            cls._base_path = detect_service_root()
        return cls._base_path

    @classmethod
    def load_config(cls):
        base_path = cls.get_base_path()
        env_name = os.getenv('APP_ENV', 'dev')
        env = f'{env_name}.ini'

        base_config_file = base_path / 'config' / 'application.ini'
        env_config_file = base_path / 'config' / 'env' / env

        config = ConfigParser()
        for file_path in [base_config_file, env_config_file]:
            if file_path.exists():
                logger.info('Loading configuration file : %s', file_path)
                config.read(file_path)

        cls._config = config

    @classmethod
    def get_property(cls, key: str, section: str = 'DEFAULT', default=None):
        if cls._config is None:
            cls.load_config()
        section_cfg = cls._config[section]
        return section_cfg.get(key, default)

    @classmethod
    def has_property(cls, key: str, section: str = 'DEFAULT', default=None):
        if cls._config is None:
            cls.load_config()
        hp = False
        if section in cls._config:
            hp = key in cls._config[section]
        return hp


class ConfigCommon:
    @staticmethod
    def get_path():
        return join(ConfigClient.get_base_path(), 'config', 'config.yaml')


class ConfigApp:
    _config = None

    @classmethod
    def load_config(cls):
        base_path = ConfigClient.get_base_path()
        config_path = base_path / 'config' / 'config.yaml'
        with open(config_path, encoding='utf-8') as stream:
            try:
                cls._config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.error(exc)
                raise exc

    @classmethod
    def get_property(cls, path):
        if cls._config is None:
            cls.load_config()
        value = cls._config
        for key in path.split('/'):
            value = value[key]
        return value
