import asyncio
import aiohttp_jinja2
import jinja2

from aiohttp.web import Application, AppRunner, TCPSite
from functools import partial
from pathlib import Path
from typing import Dict, Union

from app.routes import routes_setup
from app.db import Base, DBHandler, File


async def app_setup(app: Application, app_vars: Dict[str, Union[Path, int, str]]) -> Application:

    for key , value in app_vars.items():
        app[key.upper()] = value
        
    routes_setup(app)
    
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(app['TEMPLATES']))
    db_hanler = DBHandler(app['DB_URL'])
    app['DB_HANDLER'] = db_hanler
    await db_hanler.create(Base)
    await db_hanler.db_normalizer(app['SAVE_DIR'], app['SAVE_DIR'], File)
    
    return app


async def app_starter(app_vars: Dict[str, Union[Path, str]]):
    app = Application()
    
    app = await app_setup(app, app_vars)
    
    runner = AppRunner(app)
    await runner.setup()
    
    site = TCPSite(runner, port=app['PORT'])
    
    try:
        await site.start()
    
        while True:
            await asyncio.sleep(app['AWAIT'])
    
    finally:
        await app['DB_HANDLER'].release()