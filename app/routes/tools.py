import aiofiles as aiof
import aiofiles.os as aos

from aiohttp import BodyPartReader, MultipartReader
from aiohttp.web import Request
from json import dumps
from pathlib import Path
from datetime import datetime
from typing import Any, Coroutine, Dict, Type, Union, List, Tuple


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
    def __init__(self, path: Type[Path], chunk_size: int = 65535) -> None:
        self._path = path
        self._chunk_size = chunk_size  
    
    async def _is_exist(self, mkdir: bool = True) -> Coroutine[Any, Any, bool]:
        if not await aos.path.exists(self._path):
            if not await aos.path.exists(self._path.parent) and mkdir:
                await aos.makedirs(self._path.parent, exist_ok=True)

            else:
                raise FileNotFoundError
        
        else:
            if mkdir:
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
    
    async def file_downloader(self) -> Coroutine[Any, Any, int]:
        await self._is_exist(False)
        
        async with aiof.open(self._path, 'rb') as fd:
            result = await fd.read()
            print(result)
        
        return result
    
       
       
class FormHandler:
    def __init__(self, reader: MultipartReader) -> None:
        self.__reader = reader
    
    async def _field_decoder(self, field: BodyPartReader, encoding: str) -> Coroutine[Any, Any, str]:
        field_data = await field.read()
        
        return field_data.decode(encoding)    
    
    def _field_validator(self, field: Union[str, int]) -> None:
        if not field:
            raise RequiredFormFieldError
    
    @staticmethod
    def path_constructor(path:str, name: str, ext: str) -> Type[Path]:
        file_name = '.'.join((name.lstrip('/'), ext.lstrip('./\\')))

        return Path(path.lstrip('./')).joinpath(file_name)
    
    async def handle_form(self, encoding: str='utf-8') -> Coroutine[Any, Any, Dict[str, Union[str, int]]]:
        self._form_data: Dict[str, Union[str, int]] = dict()
        
        async for field in self.__reader:
            if field.name != 'submit':
                self._form_data[field.name] = await self._field_decoder(field, encoding)
                self._field_validator(self._form_data[field.name])
        
        return self._form_data
               

class InsertFormHandler(FormHandler):
    def __init__(
        self,
        reader: MultipartReader,
        save_dir: Type[Path],
        chunk_size: int = 65535
        ) -> None:
        
        super().__init__(reader)
        self.__reader = reader
        self.__save_dir = save_dir
        self.__chunk_size = chunk_size
    
    async def handle_form(self, encoding: str='utf-8') -> Coroutine[Any, Any, Dict[str, Union[str, int]]]:
        self._form_data: Dict[str, Union[str, int]] = dict()
        
        async for field in self.__reader: 
            if field.name != 'submit':
                if field.name != 'file_choose':
                    self._form_data[field.name] = await self._field_decoder(field, encoding)
                    self._field_validator(self._form_data[field.name])
                
                else:
                    full_path = self.__save_dir.joinpath(self.path_constructor(self._form_data['path'], self._form_data['name'], self._form_data['ext']))
                    file_handler = FileHandler(full_path, self.__chunk_size)
        
                    self._form_data['sz'] = await file_handler.file_uploader(field)
                    self._form_data['create'] = datetime.now().isoformat()
                    self._form_data['update'] = None
        
        return self._form_data