import asyncio

import app


if __name__ == '__main__':
    try:
        print('Server - ON')
        asyncio.run(app.app_starter())
    
    except KeyboardInterrupt:
        print('\b\bServer - OFF')