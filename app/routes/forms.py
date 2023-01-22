from aiohttp import BodyPartReader, MultipartReader
from typing import Any, Coroutine, TypeVar, Dict, Union, Type, Tuple

from app.routes.tools import FormHandler


class SearchForm:
    __slots__ = 'path' 
    
    def __init__(self, path: str) -> None:
        self.path = path
    
    def get_data(self) -> Dict[str, str]:
        r = {'path': self.path}
        
        return r
    
    def get_spec_data(self, keys: Tuple[str]) -> Dict[str, str]:
        data = self.get_data()
        
        return {key: data.get(key, None) for key in keys}


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


class UpdateForm(InfoForm):
    __slots__ = 'comment'
    
    def __init__(self, path: str, name: str , comment: str, ext: str = '') -> None:
        
        super().__init__(path, name, ext)
        self.comment = comment
    
    def get_data(self) -> Dict[str, str]:
        r = {
            **super().get_data(),
            **{'comment': self.comment}
        }
        
        return r
        

class InsertForm(UpdateForm):
    __slots__ = 'sz', 'create', 'update'
    
    def __init__(self, *args, **kwargs) -> None:
        
        super().__init__(*args, **kwargs)
        self.sz = None
        self.create = None
        self.update = None

    def get_data(self) -> Dict[str, str]:
        r = {
            **super().get_data(),
            **{'path': self.path, 'sz': self.sz, 'create': self.create, 'update': self.update, 'comment': self.comment},  
        }
        
        return r
    

FT = TypeVar('FT', bound=SearchForm)


class FormDataFabric:
    def __init__(self, form_cls: FT, handler: Type[FormHandler], reader: MultipartReader) -> None:
        
        self.__reader = reader
        self.__handler = handler
        self.__form = form_cls
        self.__form_data = None
        self.__field = None
    
    async def create(self) -> Coroutine[Any, Any, Union[FT, BodyPartReader]]:
        self.__form_data, self.__field = await self.__handler(self.__reader).parse_data()
        
        return self.__form(**self.__form_data), self.__field