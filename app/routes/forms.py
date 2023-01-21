from aiohttp import BodyPartReader, MultipartReader
from typing import Any, Coroutine, TypeVar, Dict, Union

from app.routes.tools import FormHandler


class SearchForm:
    __slots__ = 'path' 
    
    def __init__(self, path: str) -> None:
        self.path = path
    
    def get_data(self) -> Dict[str, str]:
        r = {'path': self.path}
        
        return r


class InfoForm(SearchForm):
    __slots__ = 'name', 'ext'
    
    def __init__(self, path: str, name: str , ext: str) -> None:
        
        super().__init__(path)
        self.name = name
        self.ext = ext
    
    def get_data(self) -> Dict[str, str]:
        r = {
            **super().get_data(),
            **{'name': self.name, 'ext': self.ext}
        }
        
        return r
        

class InsertForm(InfoForm):
    __slots__ = 'comment', 'sz', 'create', 'update'
    
    def __init__(self, path: str, name: str, ext: str, comment: str) -> None:
        
        super().__init__(path, name, ext)
        self.comment = comment
        self.sz = None
        self.create = None
        self.update = None

    def get_data(self) -> Dict[str, str]:
        r = {
            **super().get_data(),
            **{'path': self.path, 'sz': self.sz, 'create': self.create, 'update': self.update},  
        }
        
        return r
    

FT = TypeVar('FT', bound=SearchForm)


class FormDataFabric:
    def __init__(self, form_cls: FT, handler: FormHandler, reader: MultipartReader) -> None:
        
        self.__reader = reader
        self.__handler = FormHandler
        self.__form = form_cls
        self.__form_data = None
        self.__field = None
    
    async def create(self) -> Coroutine[Any, Any, Union[FT, BodyPartReader]]:
        self.__form_data, self.__field = await self.__handler(self.__reader).parse_data()
        
        return self.__form(**self.__form_data), self.__field