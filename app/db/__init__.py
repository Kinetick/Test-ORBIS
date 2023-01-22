import sqlalchemy as sql
from aiohttp.web import Application, Request
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import asynccontextmanager
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Coroutine, Any, List, Dict, TypeVar


Base = declarative_base()
T = TypeVar('T', bound=Base)


class File(Base):
    __tablename__ = 'files'
    
    name = sql.Column('name', sql.String)
    ext = sql.Column('extension', sql.String)
    sz = sql.Column('size', sql.Integer, nullable=False)
    path = sql.Column('path', sql.String)
    create = sql.Column('created_at', sql.String, nullable=False)
    update = sql.Column('updated_at', sql.String)
    comment = sql.Column('comment', sql.String)
    
    sql.PrimaryKeyConstraint(name, ext, path, name='pk_files')
    
    def __repr__(self):
        return f'File(name={self.name}, extension={self.ext}, size={self.sz}, path={self.path}, \
    created_at={self.create}, updated_at={self.update})'


class Result:
    __slots__ = 'value', 'del_url', 'upd_url', 'dwld_url'
    
    def __init__(self, value: str) -> None:
        self.value = value
        self.del_url = None
        self.upd_url = None
        self.dwld_url = None
    
    def make_url(
        self, 
        del_endpoint_name: str, 
        upd_endpoint_name: str, 
        dwld_endpoint_name: str,
        app: Application, 
        query_params: Dict[str, Any]
        ) -> None:
        
        download_delete_p = {'name': query_params['name'], 'path': query_params['path'], 'ext': query_params['ext']}
        
        self.del_url = app.router[del_endpoint_name].url_for().with_query(download_delete_p)
        self.upd_url = app.router[upd_endpoint_name].url_for().with_query(query_params)
        self.dwld_url = app.router[dwld_endpoint_name].url_for().with_query(download_delete_p)
    

class DBHandler:
    def __init__(self, db_url: str, echo: bool=False, future: bool=True) -> None:
        self.__engine = create_async_engine(db_url, echo=True, future=future)
        self.__session_maker = sessionmaker(self.__engine, expire_on_commit=False, class_=AsyncSession)
    
    async def create(self, Base: DeclarativeMeta) -> None:
        async with self.__engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    
    async def drop(self, Base: DeclarativeMeta) -> None:
        async with self.__engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    
            
    @asynccontextmanager
    async def get_session(self):
        try:
            async with self.__session_maker() as session:
                yield session
        
        finally:
            await session.close()
    
    async def insert(self, file: File) -> Coroutine[Any, Any, None]:
        async with self.get_session() as session:
            session.add(file)
            await session.commit()
    
    @staticmethod
    def __result_unpacker(result_item: File) -> Dict[str, Any]:
        res = {
        'name': result_item.name,
        'ext': result_item.ext,
        'size': result_item.sz,
        'path': result_item.path,
        'created_at': result_item.create,
        'updated_at': result_item.update,
        'comment': result_item.comment
        }
    
        return res
    
    async def execute(self, sql_query: Any, is_dml: bool = False) -> Coroutine[Any, Any, List[Result]]:
        async with self.get_session() as session:
            if is_dml:
                await session.execute(sql_query)
                await session.commit()
            
            else:
                result = await session.execute(sql_query)
                return [Result(self.__result_unpacker(item)) for item in result.scalars()]
            
    async def update(self, file: File, request: Request, values: Dict[str, Any]) -> Coroutine[Any, Any, None]:
        sql_query = sql.update(file)\
            .where(
                file.name == request.query.get('name'),
                file.ext == request.query.get('ext'),
                file.path == request.query.get('path')
            )\
            .values(values)
        
        async with self.get_session() as session:
            await session.execute(sql_query)
            await session.commit()
    
    async def release(self):
        await self.__engine.dispose()
