import aiohttp.web as web
from aiohttp.web import Application

import app as m_app
from app.routes import handlers


def routes_setup(app: Application) -> None:
    search_handler = handlers.SearchHanler(app)
    index_handler = handlers.IndexHandler(app)
    info_handler = handlers.InfoHandler(app)
    download_handler = handlers.DownloadHandler(app)
    delete_handler = handlers.DeleteHandler(app)
    insert_handler = handlers.InsertHandler(app)
    update_handler = handlers.UpdateHandler(app)
    
    app.add_routes([
        web.get('/search', search_handler.get, name='g_search'),
        web.post('/search', search_handler.post, name='p_search'),
        web.get('/', index_handler.get, name='index'),
        web.get('/info', info_handler.get, name='g_info'),
        web.post('/info', info_handler.post, name='p_info'),
        web.get('/download', download_handler.get, name='download'),
        web.get('/delete', delete_handler.get, name='delete'),
        web.get('/insert', insert_handler.get, name='g_insert'),
        web.post('/insert', insert_handler.post, name='p_insert'),
        web.get('/update', update_handler.get, name='g_update'),
        web.post('/update', update_handler.post, name='p_update')
    ])
    
    app.router.add_static('/static', m_app.STATIC_DIR, name='static')