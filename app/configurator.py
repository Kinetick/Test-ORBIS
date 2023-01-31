import aiohttp_jinja2
import asyncio
import jinja2
from aiohttp.web import Application, TCPSite, AppRunner
from os import environ
from pathlib import Path
from sqlalchemy.orm import DeclarativeMeta
from typing import Dict, Any, Coroutine, List
from yaml import load, SafeLoader

import app
import app.routes.tools as tls
import app.yaml_env_parser as yml
from app.db import DBHandler, File
from app.routes import routes_setup

class AppConfigGetter:
    def __init__(self, conf_file_path: tls.T) -> None:
        self.__config_file = conf_file_path
        self.__config_loader = yml.yaml_env_setup(SafeLoader)
        self.__config = self.__conf_file_parser()

    def __conf_file_parser(self) -> Dict[str, Any]:
        with open(self.__config_file, 'r') as fd:
            config = load(fd, self.__config_loader)
        
        return config
    
    @property
    def config(self) -> Dict[str, Any]:
        return self.__config


class AppConfigurator:
    def __init__(self, config_path: tls.T, base: DeclarativeMeta) -> None:
        self.__base = base
        self.__config = AppConfigGetter(config_path).config
        self.__apps = None
        self.__save_dirs = {}
        self.__db_handlers = {}
        self.__sites = {}
    
    def __parameter_get(self, source: Dict[str, Any], key: str, error_message: str) -> Any:
        try:
            value = source[key]
        except KeyError:
            print(error_message)
            raise
            
        return value
            
    def __apps_create(self) -> None:
        try:
            self.__apps = {key: Application() for key in self.__config['applications']}
        
        except KeyError:
            print('Отсутствует обязательный элемент верхнего уровня "applications".')
            raise
        
        except TypeError:
            print('Неверный формат файла конфигурации.')
            raise
    
    def __path_make(self, app_val: Dict[str, Any], app_key: str) -> tls.T:
        app_vars = self.__parameter_get(app_val, 'app_vars', f'Отсутствует либо элемент "app_vars" в {app_key}.')
        save_path = Path(self.__parameter_get(app_vars, 'save_path', f'Отсутствует либо элемент "save_dir" в {app_key}.'))
        
        return save_path
    
    def __save_dirs_create(self) -> None:
        for app_key, app_val in self.__config['applications'].items():
            save_path = self.__path_make(app_val, app_key)
            self.__save_dirs[app_key] = save_path
                    
            if not save_path.exists():
                save_path.mkdir(parents=True)
    
    def __db_url_make(self, app_val: Dict[str, Any], app_key: str):
        db_settings = self.__parameter_get(app_val, 'db_settings', f'Отсутствует обязательный элемент "db_settings" в {app_key}.') 
        db_type = self.__parameter_get(db_settings, 'db_type', f'Отсутствует обязательный элемент "db_type" в {app_key}.')
        db_name = self.__parameter_get(db_settings, 'db_name', f'Отсутствует обязательный элемент: "db_path" в {app_key}.')
        
        if db_type == 'SQLite':
            db_path = Path(self.__parameter_get(db_settings, 'db_path', f'Отсутствует обязательный элемент: "db_path" в {app_key}.'))
            if not db_path.exists():
                db_path.mkdir(parents=True, exist_ok=True)
                db_path.joinpath(db_name).touch(exist_ok=True)
            
            url = f'sqlite+aiosqlite:///{db_path.joinpath(db_name)}'
            
        elif db_type == 'PostgreSQL':
            db_port = self.__parameter_get(db_settings, 'db_port', f'Отсутствует обязательный элемент: "db_port" в {app_key}.')
            db_host = self.__parameter_get(db_settings, 'db_host', f'Отсутствует обязательный элемент: "db_host" в {app_key}.')
            db_password = self.__parameter_get(environ, f'{app_key.upper()}_DB_PASSWORD', f'Отсутствует пароль от базы данных для {app_key}.')
            db_username = self.__parameter_get(environ, f'{app_key.upper()}_DB_USERNAME', f'Отсутствует имя пользователя от базы данных для {app_key}.')
            url = f'postgresql+asyncpg://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}'
        
        else:
            print('Неверное значение для "db_type". Допускается: "SQLite" или "PostgreSQL".')
            raise ValueError
        
        return url
          
    def __db_handlers_create(self) -> None:
        for app_key, app_val in self.__config['applications'].items():
            db_url = self.__db_url_make(app_val, app_key)
            self.__db_handlers[app_key] = DBHandler(db_url)
    
    def __app_vars_registrate(self) -> None:
        for item in zip(self.__apps.values(), self.__save_dirs.values(), self.__db_handlers.values()):
            item[0]['SAVE_DIR'] = item[1]
            item[0]['DB_HANDLER'] = item[2]       
    
    def __routes_setup(self) -> None:
        [routes_setup(application) for application in self.__apps.values()]
    
    def __templates_setup(self) -> None:
        [aiohttp_jinja2.setup(application, loader=jinja2.FileSystemLoader(app.TEMPLATES_DIR)) for application in self.__apps.values()]
    
    async def __sites_create(self) -> Coroutine[Any, Any, None]:   
        for app_key, app_val in self.__config['applications'].items():
            application = self.__apps[app_key]
            application_settings = self.__parameter_get(app_val, 'app_settings', f'Отсутствует обязательный элемент: "app_settings" в {app_key}.')
            tmp_host = self.__parameter_get(application_settings, 'host', f'Отсутствует обязательный элемент: "host" в {app_key}.')
            application_host = tmp_host if tmp_host else None
            application_port = int(self.__parameter_get(application_settings, 'port', f'Отсутствует обязательный элемент: "port" в {app_key}.'))
            runner = AppRunner(application)
            await runner.setup()
            site = TCPSite(runner, host=application_host, port=application_port)
            self.__sites[app_key] = site
    
    async def __site_start(self, site: TCPSite, app: Application) -> Coroutine[Any, Any, None]:
        try:
            await site.start()
            while True:
                await asyncio.sleep(3600)
        
        finally:
            await app['DB_HANDLER'].release()
    
    def sites_start_tasks_create(self) -> List[asyncio.Task]:
        tasks = []
        for key_app in self.__config['applications']:
            tasks.append(asyncio.create_task(self.__site_start(self.__sites[key_app], self.__apps[key_app])))
        
        return tasks
    
    async def configurate(self) -> Coroutine[Any, Any, None]:
        self.__apps_create()
        self.__save_dirs_create()
        self.__db_handlers_create()
        self.__app_vars_registrate()
        self.__routes_setup()
        self.__templates_setup()
        await self.__sites_create()
        await asyncio.gather(*[asyncio.create_task(application['DB_HANDLER'].create(self.__base)) for application in self.__apps.values()])
        await asyncio.gather(*[asyncio.create_task(application['DB_HANDLER'].normalize(application['SAVE_DIR'], application['SAVE_DIR']))\
            for application in self.__apps.values()])