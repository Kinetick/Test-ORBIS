import sqlalchemy as sql

from aiohttp.web import Application
from json import dumps
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import asynccontextmanager
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Type, Coroutine, Any, List, Tuple, Dict, Union


Base = declarative_base()


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
    
    async def select_all(self, file: File) -> List[Dict[str, Union[str, int]]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(file))
            
            return [dumps(self.__result_extractor(item)) for item in result.all()]
    
    async def select(self, file: File, name: str='', ext: str='', path: str='') -> List[Dict[str, Union[str, int]]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(file).where(sql.and_(file.name == name, file.ext == ext, file.path == path)))
            
            return [dumps(self.__result_extractor(item)) for item in result.all()]
    
    async def search(self, file: File, path='') -> List[Dict[str, Union[str, int]]]:
        async with self.get_session() as session:
            result = await session.execute(sql.select(file).where(file.path.like(f'{path}%')))
            
            return [dumps(self.__result_extractor(item)) for item in result.all()]
            
    
    async def release(self):
        await self.__engine.dispose()
