class RequiredFormFieldError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

        self.__message = args[0] if args else None
    
    def __str__(self):
        if self.__message is not None:
            return self.__message
        
        else:
            return f'{self.__class__.__name__}: Поля формы обязательны для заполнения.'

class FileMetaDifference(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

        self.__message = args[0] if args else None
    
    def __str__(self):
        if self.__message is not None:
            return 'Имя или относительный путь файла изменились.'
        
        else:
            return f'Возникло исключение: {self.__class__.__name__}.'