import asyncio
import sqlalchemy as sql
from typing import Any, Coroutine, List, Optional, Tuple, TypeVar, Dict
from aiohttp import BodyPartReader
from aiohttp.web import Application, Request, Response, HTTPFound
from aiohttp_jinja2 import render_template
from datetime import datetime

import app.db as db
from app.routes import exceptipon as exc
from app.routes import tools as tls
from app.routes import forms as fs

F = TypeVar('F', bound=fs.SearchForm)

class BaseHandler:
    def __init__(self, app: Application) -> None:
        self._app = app
    
    def _redirect_maker(self, endpoint_name: str, query_params: Optional[Dict[str, str]] = None) -> HTTPFound:
        url = self._app.router[endpoint_name].url_for()
        
        if query_params is not None:
            url = url.with_query(query_params)
        
        return HTTPFound(url)
    
    async def _form_data_maker(self, request: Request, form_cls: F) -> Tuple[F, BodyPartReader]:
        reader = await request.multipart()
        factory = fs.FormDataFabric(form_cls, tls.FormHandler, reader)
        
        return await factory.create()
    
    def _page_context_maker(
        self, 
        request: Request, 
        page_target: str, 
        page_name: str, 
        form_handler_name: Optional[str] = None, 
        query_params: Optional[Dict[str, str]] = None
        ) -> tls.PageContext:
        
        if form_handler_name is not None:
            action_url = self._app.router[form_handler_name].url_for()
        
            if query_params is not None:
                action_url = action_url.with_query(query_params)
        
        else:
            action_url = None
        
        return tls.PageContext(request, page_target, page_name, action_url)
    
    def _file_menu_link_maker(
        self, 
        result: List[db.Result],
        delete_endpoint_name: str,
        update_endpoint_name: str,
        download_endpoint_name: str,
        link_keys: Tuple[str]
        ) -> List[db.Result]:
        
        if result:
            for item in result:
                item.make_url(
                    delete_endpoint_name, 
                    update_endpoint_name, 
                    download_endpoint_name, 
                    self._app, 
                    {key: item.value[key] for key in link_keys}
                    )
        
        return result


class SearchHanler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'search', 'Search', 'p_search')
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response
    
    async def post(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'search', 'Search', 'p_search')
        
        try:
            form, _ = await self._form_data_maker(request, fs.SearchForm)
        
        except exc.RequiredFormFieldError as e:
            error_message = str(e)
            raise self._redirect_maker('g_search', {'error': error_message})
        
        else:
            db_handler: db.DBHandler = self._app['DB_HANDLER']
            sql_query = sql.select(db.File).where(db.File.path.like(f'{form.path}%'))
            result = await db_handler.execute(sql_query)
            context.result = self._file_menu_link_maker(result, 'delete', 'g_update', 'download', ('name', 'ext', 'path', 'comment'))
        
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response

class IndexHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'index', 'Search')
        db_handler: db.DBHandler = self._app['DB_HANDLER']
        sql_query = sql.select(db.File)
        result = await db_handler.execute(sql_query)
        context.result = self._file_menu_link_maker(result, 'delete', 'g_update', 'download', ('name', 'ext', 'path', 'comment'))
        
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response


class InfoHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'info', 'info', 'p_info')
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response
    
    async def post(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'info', 'Info', 'p_info')
        
        try:
            form, _ = await self._form_data_maker(request, fs.InfoForm)
        
        except exc.RequiredFormFieldError as e:
            error_message = str(e)
            raise self._redirect_maker('g_info', {'error': error_message})
        
        else:
            db_handler: db.DBHandler = self._app['DB_HANDLER']
            sql_query = sql.select(db.File).where(db.File.name == form.name, db.File.path == form.path, db.File.ext == form.ext)
            result = await db_handler.execute(sql_query)
            context.result = self._file_menu_link_maker(result, 'delete', 'g_update', 'download', ('name', 'ext', 'path', 'comment'))
        
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response

    
class DownloadHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
        
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        handle_path = tls.FileHandler.path_constructor(
            self._app['SAVE_DIR'], **tls.collector_query_params(request, ['path', 'name', 'ext'], None))
        
        try:
            file_handler = tls.FileHandler(handle_path)
            body = await file_handler.file_downloader()
        
        # В идеале, если БД и хранилище синхронизированы такого не может случиться, но тут может =)
        except FileNotFoundError:
            error_message = 'Такого файла не существует.'
            raise self._redirect_maker('index', {'error': error_message})
        
        response = Response(body=body, status=200, reason='OK', headers={'content-disposition': f'inline; filename="{handle_path.name}"'})
        
        return response


class DeleteHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        query_params = tls.collector_query_params(request, ['path', 'name', 'ext'], None)
        handle_path = tls.FileHandler.path_constructor(request.app['SAVE_DIR'], **tls.collector_query_params(request, ['path', 'name', 'ext'], None))
        file_handler = tls.FileHandler(handle_path)
        db_handler: db.DBHandler = self._app['DB_HANDLER']
        sql_query = sql.delete(db.File).where(
            db.File.name == request.query.get('name'), db.File.path == request.query.get('path'), db.File.ext == request.query.get('ext')
            )
    
        await asyncio.gather(file_handler.file_deleter(), db_handler.execute(sql_query, True))
    
        raise self._redirect_maker('index')

class InsertHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'insert', 'Insert', 'p_insert')
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response

    async def post(self, request: Request) -> Coroutine[Any, Any, Any]:
        context = self._page_context_maker(request, 'insert', 'Insert', 'p_insert')
        
        try:
            form, field = await self._form_data_maker(request, fs.InsertForm)
            handle_path = tls.FileHandler.path_constructor(self._app['SAVE_DIR'], **form.get_spec_data(('name', 'path', 'ext')))
            file_handler = tls.FileHandler(handle_path)
            form.sz = await file_handler.file_uploader(field)
            form.create = datetime.now().isoformat()
            
        except exc.RequiredFormFieldError as e:
            error_message = str(e)
            raise self._redirect_maker('g_insert', {'error': error_message})
        
        except FileExistsError:
            error_message = 'По данному пути уже существует файл с таким именем.'
            raise self._redirect_maker('g_insert', {'error': error_message})
        
        else:
            db_handler: db.DBHandler = self._app['DB_HANDLER']
            await db_handler.insert(db.File(**form.get_data()))
            raise self._redirect_maker('index')

class UpdateHandler(BaseHandler):
    def __init__(self, app: Application) -> None:
        super().__init__(app)
    
    async def get(self, request: Request) -> Coroutine[Any, Any, Response]:
        context = self._page_context_maker(request, 'update', 'Update', 'p_update', request.query)
        context.form_data = fs.UpdateForm(**tls.collector_query_params(request, ['path', 'name', 'ext', 'comment'], None))
        
        response = render_template('index.jinja2', request=request, context=context.get_context())
    
        return response

    def _file_meta_difference_check(self, request: Request, form: fs.UpdateForm) -> bool:
        for key, value in form.get_data().items():
                if key == 'name' or key == 'path':
                    if value != request.query.get(key):
                        return False
                        
        return True
    
    async def post(self, request: Request) -> Coroutine[Any, Any, Any]:
        context = self._page_context_maker(request, 'index', 'Index')
        
        try:
            form, _ = await self._form_data_maker(request, fs.UpdateForm)
        
        except exc.RequiredFormFieldError as e:
            error_message = str(e)
            raise self._redirect_maker('g_update', {'error': error_message, **request.query})

        db_handler: db.DBHandler = self._app['DB_HANDLER']
        
        if not self._file_meta_difference_check(request, form):
            form.ext = request.query.get('ext')
            current_path = tls.FileHandler.path_constructor(request.app['SAVE_DIR'], **tls.collector_query_params(request, ['path', 'name', 'ext'], None))
            new_path = tls.FileHandler.path_constructor(self._app['SAVE_DIR'], **form.get_spec_data(('name', 'path', 'ext')))
            file_handler = tls.FileHandler(current_path)
            
            try:
                await file_handler.file_replacer(new_path)
            
            except FileExistsError:
                error_message = 'Файл с указанными параметрами уже существует.'
                raise self._redirect_maker('g_update', {'error': error_message, **request.query})
            
            except OSError:
                error_message = 'Во время переноса файла произошла ошибка.'
                raise self._redirect_maker('g_update', {'error': error_message, **request.query})
            
            await db_handler.update(db.File, request, {'update': datetime.now().isoformat(), **form.get_spec_data(('name', 'path', 'comment'))})
        
        if request.query.get('comment') != form.comment:
            await db_handler.update(db.File, request, {'update': datetime.now().isoformat(), **form.get_spec_data(('comment',))})
    
        response = render_template('index.jinja2', request=request, context=context.get_context())
        
        return response
            