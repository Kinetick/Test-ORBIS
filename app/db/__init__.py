import sqlalchemy as sql
import aiofiles.os as aos
import asyncio
from aiohttp.web import Application, Request
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Coroutine, Any, List, Dict, Set, TypeVar, Type, Callable, Tuple, Union


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
    
import app.routes.tools as tls
from app.routes.tools import FileHandler

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
    
    async def insert(self, file: Union[File, List[File]]) -> Coroutine[Any, Any, None]:
        async with self.get_session() as session:
            session.add(file) if isinstance(file, File) else session.add_all(file)
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
    
    async def execute(self, sql_query: Any, is_dml: bool = False, prms: List[Dict[str, str]] = None) -> Coroutine[Any, Any, List[Result]]:
        async with self.get_session() as session:
            if is_dml:   
                await session.execute(sql_query, prms)
                await session.commit()
            
            else:
                result = await session.execute(sql_query)
                return [Result(self.__result_unpacker(item)) for item in result.scalars()]
            
    async def update(self, file: Type[File], request: Request, values: Dict[str, Any]) -> Coroutine[Any, Any, None]:
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


    # ?????????? ?? ?? ????????????, ??.??. ????-???? ???????? ???????????????????? ???? ?????????? ??????, ???? ?????????? ???????????????? ?????? ????????
    async def _path_aggregate(self, entry_path: tls.T) -> Coroutine[Any, Any, List[tls.T]]:
        result = []
        entry_path_items = [Path(entry_path).joinpath(item) for item in await aos.listdir(entry_path)]
        [result.extend(await self._path_aggregate(item)) if await aos.path.isdir(item) else result.append(item) for item in entry_path_items]
    
        return result

    # ?????????????????????? ??????????????????, ?????? ?? ?? ?????????????? ????????
    def _path_relating(self, paths: List[tls.T], related_to_path: tls.T) -> Set[tls.T]:
        return {path.relative_to(related_to_path) for path in paths}
    
    async def _db_path_aggregate(self, save_dir_path: tls.T) -> Coroutine[Any, Any, List[tls.T]]:
        sql_query = sql.select(File)
        paths = [FileHandler.path_constructor(save_dir_path, item.value.get('path', ''), item.value.get('name', ''), item.value.get('ext', ''))\
            for item in await self.execute(sql_query)]

        return paths
    
    async def _path_extract(
        self, 
        entry_path: tls.T, 
        related_to_path: tls.T, 
        aggr_func: Callable[[tls.T], Coroutine[Any, Any, List[tls.T]]]
        
        ) -> Coroutine[Any, Any, Set[tls.T]]:
        
        paths = await aggr_func(entry_path)
        r_paths = self._path_relating(paths, related_to_path)
    
        return r_paths
    
    def _difference_get(self, paths_fh: Set[tls.T], paths_bd: Set[tls.T]) -> Tuple[Set[tls.T], Set[tls.T]]:
        symmetric = paths_fh.symmetric_difference(paths_bd)
        paths_fh_db = symmetric - paths_fh
        paths_db_fh = symmetric - paths_bd
        
        return paths_fh_db, paths_db_fh
    
    def _ext_make(self, path: tls.T, default: str = '') -> str:
        return ''.join(path.suffixes).lstrip('./\\') if path.suffixes else f'{default}'
    
    async def _files_obj_create(self, save_dir_path: tls.T, paths_db_fh: Set[tls.T]) -> Coroutine[Any, Any, List[File]]:
        files_objs = []
        
        for path in paths_db_fh:
            file_data_dict = dict()
            file_data_dict['name'] = path.stem
            file_data_dict['ext'] = self._ext_make(path)
            file_data_dict['path'] = str(path.parent)
            file_data_dict['update'] = None
            file_data_dict['comment'] = '?? ?????????? ?????? ??????????????????????.'
            
            try:    
                file_stat = await aos.stat(save_dir_path.joinpath(path))
            
            except FileNotFoundError:
                created = ''
                sz = 0
            else:
                created = datetime.utcfromtimestamp(file_stat.st_ctime).isoformat()
                sz = file_stat.st_size
                
            file_data_dict['create'] = created
            file_data_dict['sz'] = sz
            
            files_objs.append(File(**file_data_dict))
            
        return files_objs  
    
    async def _add(self, save_dir_path: tls.T, paths_db_fh: Set[tls.T]) -> Coroutine[Any, Any, None]:
        files = await self._files_obj_create(save_dir_path, paths_db_fh)
        await self.insert(files)
    
    async def _cleane(self, paths_fh_db: Set[tls.T]) -> Coroutine[Any, Any, None]:
        params = [{"path": str(path.parent), "name": path.stem, "ext": self._ext_make(path)} for path in paths_fh_db]
        
        if params:
            sql_query = sql.delete(File).where(
                File.name == sql.bindparam('name'),
                File.path == sql.bindparam('path'),
                File.ext == sql.bindparam('ext')
                )
        
            await self.execute(sql_query, True, params)
             
    async def normalize(self, save_dir_path: tls.T, related_to: tls.T) -> Coroutine[Any, Any, None]:
        files_holder_paths, db_files_paths = await asyncio.gather(
            self._path_extract(save_dir_path, related_to, self._path_aggregate),
            self._path_extract(save_dir_path, related_to, self._db_path_aggregate)
        )
        paths_fh_db, paths_db_fh = self._difference_get(files_holder_paths, db_files_paths)
        
        await asyncio.gather(self._add(save_dir_path, paths_db_fh), self._cleane(paths_fh_db))