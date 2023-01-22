import asyncio
from aiohttp.web import run_app
from pathlib import Path

import app


MAIN_DIR = Path(__file__).parent
DB_PATH = MAIN_DIR.joinpath('test.sqlite')
APP_VARS = {
    'save_dir': MAIN_DIR.joinpath('file_holder'),
    'db_url': 'sqlite+aiosqlite:///{db_path}'.format(db_path=DB_PATH),
    'port': 5000,
    'await': 3600,
    'templates': MAIN_DIR.joinpath('templates'),
    'static': MAIN_DIR.joinpath('static')

}


async def server() -> None:
    
    if not APP_VARS['save_dir'].exists():
        APP_VARS['save_dir'].mkdir(parents=True)

    DB_PATH.touch(exist_ok=True)
    
    await asyncio.gather(app.app_starter(APP_VARS))
        

if __name__ == '__main__':
    try:
        print('Server - ON')
        asyncio.run(server())
    
    except KeyboardInterrupt:
        print('\b\bServer - OFF')