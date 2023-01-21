import aiofiles as aiof
import aiofiles.os as aos
import asyncio
import sqlalchemy as sql

from aiohttp.web import Application, Request, Response, HTTPFound
from aiohttp_jinja2 import render_template
from datetime import datetime

import app.routes.tools as tools
import app.routes.forms as forms

from app.db import File

async def info(request: Request) -> Response:
    context = tools.PageContext(request, 'info', 'Info', 'p_info')
    
    if request.method == 'POST':
        reader = await request.multipart()
        fabric = forms.FormDataFabric(forms.InfoForm, tools.FormHandler, reader)
        
        try:
            form, _ = await fabric.create()
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_info'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))

        else:
            results = await request.app['DB_HANDLER'].select(File, **form.get_data())
            if results:
                for item in results:
                    parameters = {'name': item.value['name'], 'ext': item.value['extension'], 'path': item.value['path']}
                    item.make_url('delete', 'g_update', 'download', request.app, parameters)
            
            context.result = results
            
    response = render_template('index.jinja2', request=request, context=context.get_context())
    
    return response


async def search(request: Request) -> Response:
    context = tools.PageContext(request, 'search', 'Search', 'p_search')
    
    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler =  tools.FormHandler(reader)
            form_data = await form_handler.parse_data()
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_search'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))

        else:
            results = await request.app['DB_HANDLER'].search(File, **form_data)
            if results:
                for item in results:
                    parameters = {'name': item.value['name'], 'ext': item.value['extension'], 'path': item.value['path']}
                    item.make_url('delete', 'g_update', 'download', request.app, parameters)
            
            context.result = results
    
            
    response = render_template('index.jinja2', request=request, context=context.get_context())
    
    return response


async def download(request: Request) -> Response:
    download_path = tools.FileHandler.path_constructor(
        request.app['SAVE_DIR'],
        request.query.get('path'), 
        request.query.get('name'), 
        request.query.get('ext')
        )
    
    try:
        file_handler = tools.FileHandler(download_path)
        fl = await file_handler.file_downloader()

    except FileNotFoundError:
        raise HTTPFound(request.app.router['index'].url_for().with_query({'error': 'Такого файла не существует!'}))
    
    else:
        return Response(
            body=fl, status=200, reason='OK', headers={'content-disposition': 'inline;filename="{name}"'.format(
                name = download_path.name
        )})


async def insert(request: Request) -> Response:
    context = tools.PageContext(request, 'insert', 'Insert', 'p_insert')
    
    if request.method == 'POST':
        reader = await request.multipart()
        fabric = forms.FormDataFabric(forms.InsertForm, tools.FileHandler, reader)
        
        try:
            form, field = await fabric.create()
            upload_path = tools.FileHandler.path_constructor(request.app['SAVE_DIR'], form.path, form.name, form.ext)
            file_handler = tools.FileHandler(upload_path)
            form.sz = await file_handler.file_uploader(field)
            form.create = datetime.now().isoformat()
        
        except FileExistsError:
            raise HTTPFound(request.app.router['g_insert'].url_for().with_query({'error': 'Файл уже существует!'}))
        
        except tools.RequiredFormFieldError:
            raise HTTPFound(request.app.router['g_insert'].url_for().with_query({'error': 'Поля формы обязательны к заполнению!'}))
        
        else:
            await request.app['DB_HANDLER'].insert(File(**form.get_data()))         
            raise HTTPFound(request.app.router['index'].url_for())
    
    response = render_template('index.jinja2', request=request, context=context.get_context())
    
    return response
        
# Пока не реализовано
async def update(request: Request) -> Response:
    if request.method == 'POST':
        reader = await request.multipart()
        try:
            form_handler = tools.InsertFormHandler(reader, request.app['SAVE_DIR'])
            form_data = await form_handler.parse_data()
        
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


async def delete(request: Request) -> None:
    query_params = tools.collector_query_params(request, ['path', 'name', 'ext'], None)
    delete_path = tools.FileHandler.path_constructor(request.app['SAVE_DIR'], **query_params)
    file_handler = tools.FileHandler(delete_path)
    
    await asyncio.gather(file_handler.file_deleter(), request.app['DB_HANDLER'].delete(File, **query_params))
    
    raise HTTPFound(request.app.router['index'].url_for())


async def index(request: Request) -> Response:
    context = tools.PageContext(request, 'index', 'Index')
    results = await request.app['DB_HANDLER'].select_all(File)
    if results:
        for item in results:
            parameters = {'name': item.value['name'], 'ext': item.value['extension'], 'path': item.value['path']}
            item.make_url('delete', 'g_update', 'download', request.app, parameters)
            
    context.result = results
    
    response = render_template('index.jinja2', request=request, context=context.get_context())
    
    return response


def routes_setup(app: Application) -> None:
    
    app.router.add_get('/info', info, name='g_info')
    app.router.add_post('/info', info, name='p_info')
    
    app.router.add_get('/insert', insert, name='g_insert')
    app.router.add_post('/insert', insert, name='p_insert')
    
    app.router.add_get('/', index, name='index')
    
    app.router.add_get('/search', search, name='g_search')
    app.router.add_post('/search', search, name='p_search')
    
    app.router.add_get('/download', download, name='download')
    
    app.router.add_get('/update', update, name='g_update')
    app.router.add_post('/update', update, name='p_update')
    
    app.router.add_get('/delete', delete, name='delete')
    
    app.router.add_static('/static', app['STATIC'], name='static')