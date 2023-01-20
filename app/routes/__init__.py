import aiofiles as aiof
import aiofiles.os as aos
import sqlalchemy as sql

from aiohttp.web import Application, Request, Response, HTTPFound, HTTPPermanentRedirect
from aiohttp_jinja2 import render_template
from datetime import datetime

import app.routes.tools as tools

from app.db import File

async def info(request: Request) -> Response:
    
    context = {
        'form_action_url': request.app.router['p_info'].url_for(),
        'target': 'info',
        'error': request.query.get('error', None),
        'result': None
    }
    
    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler =  tools.FormHandler(reader)
            form_data = await form_handler.handle_form()
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_info'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))

        else:
            result = await request.app['DB_HANDLER'].select(File, **form_data)
            context['result'] = result
            
    response = render_template('index.jinja2', request=request, context=context)
    
    return response


async def search(request: Request) -> Response:
    context = {
        'form_action_url': request.app.router['p_search'].url_for(),
        'target': 'search',
        'error': request.query.get('error', None),
        'result': None
    }
    
    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler =  tools.FormHandler(reader)
            form_data = await form_handler.handle_form()
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_search'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))

        else:
            result = await request.app['DB_HANDLER'].search(File, **form_data)
            context['result'] = result
            
    response = render_template('index.jinja2', request=request, context=context)
    
    return response


async def get_download(request: Request) -> Response:
    context = {
        'form_action_url': request.app.router['p_download'].url_for(),
        'target': 'download',
        'error': request.query.get('error', None),
        'result': None
    }
            
    response = render_template('index.jinja2', request=request, context=context)
    
    return response


async def download(request: Request) -> Response:
    reader = await request.multipart()
    try:
        form_handler =  tools.FormHandler(reader)
        download_path = request.app['SAVE_DIR'].joinpath(form_handler.path_constructor(await form_handler.handle_form()))
        file_handler = tools.FileHandler(download_path)
        fl = await file_handler.file_downloader()
        
        
    except tools.RequiredFormFieldError:
        raise HTTPFound(request.app.router['g_download'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))

    except FileNotFoundError:
        raise HTTPFound(request.app.router['g_download'].url_for().with_query({'error': 'Такого файла не существует!'}))
    
    else:
        return Response(
            body=fl, status=200, reason='OK', headers={'content-disposition': 'inline;filename="{name}"'.format(
                name = download_path.name
        )})


async def insert(request: Request) -> Response:

    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler = tools.InsertFormHandler(reader, request.app['SAVE_DIR'])
            form_data = await form_handler.handle_form()
        
        except FileExistsError:
            raise HTTPFound(request.app.router['g_insert'].url_for().with_query({'error': 'Файл уже существует!'}))
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_insert'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))
        
        else:
            await request.app['DB_HANDLER'].insert(File(**form_data))         
            raise HTTPFound(request.app.router['index'].url_for())
    
    context = {
        'form_action_url': request.app.router['p_insert'].url_for(),
        'target': 'insert',
        'error': request.query.get('error', None)
    }
    
    response = render_template('index.jinja2', request=request, context=context)
    
    return response
        
# Пока не реализовано
async def update(request: Request) -> Response:
    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler = tools.InsertFormHandler(reader, request.app['SAVE_DIR'])
            form_data = await form_handler.handle_form()
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_update'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))
        
        else:
            async with request.app['DB_HANDLER'].get_session() as session:
                result = await session.execute(
                    sql.select(File).where(
                        sql.and_(File.name == form_data['name'], File.path == form_data['path'], File.ext == form_data['ext'])))
                
                file = result.first()[0]
                
                if file:
                    print(file)
                    file.name = form_data['new_name']
                    file.path = form_data['new_path']
                    file.comment = form_data['new_comment']
                    file.update = datetime.now().isoformat()
                
                    await session.commit()       
    
    context = {
        'form_action_url': request.app.router['p_update'].url_for(),
        'target': 'update',
        'error': request.query.get('error', None)
    }
    
    response = render_template('index.jinja2', request=request, context=context)
    
    return response


async def delete(request: Request) -> Response:
    pass


async def index(request: Request) -> Response:
    results = await request.app['DB_HANDLER'].select_all(File)
    context = {
        'result': results,
        'target': 'index'
    }
    response = render_template('index.jinja2', request=request, context=context)
    
    return response


def routes_setup(app: Application) -> None:
    
    app.router.add_get('/info', info, name='g_info')
    app.router.add_post('/info', info, name='p_info')
    
    app.router.add_get('/insert', insert, name='g_insert')
    app.router.add_post('/insert', insert, name='p_insert')
    
    app.router.add_get('/', index, name='index')
    
    app.router.add_get('/search', search, name='g_search')
    app.router.add_post('/search', search, name='p_search')
    
    app.router.add_get('/get_download', get_download, name='g_download')
    app.router.add_post('/download', download, name='p_download')
    
    app.router.add_get('/update', update, name='g_update')
    app.router.add_post('/update', update, name='p_update')
    
    app.router.add_get('/delete', delete, name='g_delete')
    app.router.add_post('/delete', delete, name='p_delete')
    
    app.router.add_static('/static', app['STATIC'], name='static')