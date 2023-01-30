import asyncio
from pathlib import Path
from typing import Any, Coroutine

from app.configurator import AppConfigurator
from app.db import Base


PROJECT_DIR = Path(__file__).parent.parent

# Компоненты приложения
TEMPLATES_DIR = PROJECT_DIR.joinpath('templates')
STATIC_DIR = PROJECT_DIR.joinpath('static')
CONFIG_DIR = PROJECT_DIR.joinpath('config')


async def app_starter() -> Coroutine[Any, Any, None]:
    config_path = CONFIG_DIR.joinpath('app_config.yaml')
    configurator = AppConfigurator(config_path, Base)
    await configurator.configurate()
    sites_tasks = configurator.sites_start_tasks_create()
    await asyncio.gather(*sites_tasks)