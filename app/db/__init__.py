import sqlalchemy as sql

from aiohttp.web import Application
from json import dumps
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import asynccontextmanager
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Coroutine, Any, List, Tuple, Dict, TypeVar


Base = declarative_base()
T = TypeVar('T', bound=Base)


class File(Base):
    __tablename__ = 'files'
    
    name = sql.Column('name', sql.String)
    ext = sql.Column('extension', sql.String(8))
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
        
        self.del_url = app.router[del_endpoint_name].url_for().with_query(query_params)
        self.upd_url = app.router[upd_endpoint_name].url_for().with_query(query_params)
        self.dwld_url = app.router[dwld_endpoint_name].url_for().with_query(query_params)
    

class DBHandler:
    def __init__(self, db_url: str, echo: bool=False, future: bool=True) -> None:
        self.__engine = create_async_engine(db_url, echo=echo, future=future)
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
    
    async def insert(self, file: File) -> None:
        async with self.get_session() as session:
            session.add(file)
            await session.commit()
    
    @staticmethod
    def __result_extractor(result_item: Tuple[File]) -> Dict[str, Any]:
        res = {
        'name': result_item[0].name,
        'extension': result_item[0].ext,
        'size': result_item[0].sz,
        'path': result_item[0].path,
        'created_at': result_item[0].create,
        'updated_at': result_item[0].update,
        'comment': result_item[0].comment
        }
    
        return res
    
    async def select_all(self, db_item_cls: T) -> Coroutine[Any, Any, List[Result]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(db_item_cls))
            
            return [Result(self.__result_extractor(item)) for item in result.all()]
    
    async def select(self, db_item_cls: T, name: str='', ext: str='', path: str='') -> Coroutine[Any, Any, List[Result]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(db_item_cls).where(
                sql.and_(
                    db_item_cls.name == name, 
                    db_item_cls.ext == ext, 
                    db_item_cls.path == path)
                ))
            
            return [Result(self.__result_extractor(item)) for item in result.all()]
    
    async def search(self, db_item_cls: T, path: str = '') -> Coroutine[Any, Any, List[Result]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(db_item_cls).where(db_item_cls.path.like(f'{path}%')))
            
            return [Result(self.__result_extractor(item)) for item in result.all()]
    
    async def delete(self, db_item_cls: T, name: str='', ext: str='', path: str='') -> Coroutine[Any, Any, None]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(db_item_cls).where(
                sql.and_(
                    db_item_cls.name == name, 
                    db_item_cls.ext == ext, 
                    db_item_cls.path == path)
                ))
            
            result = result.first()
            await session.delete(result[0])
            await session.commit()
    
    async def release(self):
        await self.__engine.dispose()
