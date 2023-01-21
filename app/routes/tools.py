import aiofiles as aiof
import aiofiles.os as aos

from aiohttp import BodyPartReader, MultipartReader
from aiohttp.web import Request
from pathlib import Path
from time import time
from typing import Any, Coroutine, Dict, Union, List, TypeVar, Optional

from app.db import Result

T = TypeVar('T', bound=Path)

def collector_query_params(request: Request, params_names: List[str], default: Any) -> Dict[str, Any]:
     return {name: request.query.get(name, default) for name in params_names}


class RequiredFormFieldError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

        self.__message = args[0] if args else None
    
    def __str__(self):
        if self.__message is not None:
            return 'Поля формы обязательны к заполнению!'
        
        else:
            return f'Возникло исключение: {self.__class__.__name__}.'
            

class FileHandler:
    def __init__(self, path: T, chunk_size: int = 65535) -> None:
        self._path = path
        self._chunk_size = chunk_size  
    
    async def _is_exist(self, mkdir: bool = True) -> Coroutine[Any, Any, bool]:
        file_existance = await aos.path.exists(self._path)
        
        if not file_existance:
            file_dir_existance = await aos.path.exists(self._path.parent)
            
            if not file_dir_existance and mkdir:
                await aos.makedirs(self._path.parent, exist_ok=True)

            if (not file_dir_existance or file_dir_existance) and not mkdir:
                raise FileNotFoundError
        
        else:
            raise FileExistsError
    
    async def file_uploader(self, source: BodyPartReader) -> Coroutine[Any, Any, int]:
        await self._is_exist()
        
        size = 0
        async with aiof.open(self._path, 'wb') as fd:
            while True:
                file_chunk  = await source.read_chunk(self._chunk_size)
                if not file_chunk:
                    break
            
                size += len(file_chunk)
                await fd.write(file_chunk)
    
        return size
    
    async def file_downloader(self) -> Coroutine[Any, Any, Optional[bytes]]:
        try:
            await self._is_exist(False)
        
        except FileExistsError:
            async with aiof.open(self._path, 'rb') as fd:
                result = await fd.read()
        
            return result
    
    async def file_deleter(self) -> Coroutine[Any, Any, None]:
        try:
            await self._is_exist(False)
        
        except FileExistsError:
            await aos.remove(self._path)
        
        # Заглушка, т.к. нету функции нормализации БД (пока примем, как условность, что БД и хранилище синхронизированы)    
        except FileNotFoundError:
            pass
        
    @staticmethod
    def path_constructor(save_dir_path: T, path:str = '', name: str = '', ext: str = '') -> T:
        if all((path, name, ext)):
            file_name = '.'.join((name.lstrip('/'), ext.lstrip('./\\')))
            rel_path = Path(path.lstrip('./')).joinpath(file_name)
        
        else:
            rel_path = Path('file_{tm}.bin'.format(tm=int(time() * 1000)))
        
        abs_path = save_dir_path.joinpath(rel_path)

        return abs_path


class FormHandler:
    def __init__(self, reader: MultipartReader) -> None:
        self.__reader = reader
    
    async def _field_decoder(self, field: BodyPartReader, encoding: str) -> Coroutine[Any, Any, str]:
        field_data = await field.read()
        
        return field_data.decode(encoding)    
    
    def _field_validator(self, field: Union[str, int]) -> None:
        if not field:
            raise RequiredFormFieldError
    
    async def parse_data(self, encoding: str='utf-8') -> Coroutine[Any, Any, Dict[str, Union[str, int]]]:
        self._form_data: Dict[str, Union[str, int]] = dict()
        
        field = None
        async for f in self.__reader:
            if f.name != 'submit':
                if f.name != 'file_choose':
                    self._form_data[f.name] = await self._field_decoder(f, encoding)
                    self._field_validator(self._form_data[f.name])
            
                else:
                    field = f
                    break

        return self._form_data, field

class PageContext:
    __slots__ = 'target', 'form_action_name', 'form_data', 'result', 'page_name', 'request'
    
    def __init__(
        self,
        request: Request, 
        target: str, 
        page_name: str,
        form_action_name: Optional[str] = None,
        form_data: Optional[Any] = None,
        result: Optional[List[Result]] = None
        
        ) -> None:
        
        self.target = target
        self.page_name = page_name
        self.request = request
        self.form_action_name = form_action_name    
        self.form_data = form_data
        self.result = result
    
    def get_context(self) -> Dict[str, Any]:
        c = {
            'target': self.target,
            'error': self.request.query.get('error', None),
            'f_action': self.request.app.router[self.form_action_name].url_for() if self.form_action_name else self.form_action_name,
            'f_data': self.form_data,
            'page_name': self.page_name,
            'result': self.result
        }
        
        return c