def strbool(value):
    """ 
    Конвертирует строку в булевое значение

    Python 3.12 более не поддерживает distutils.util.strtobool
    данная функция заменяет его функционал
    
    """

    value = value.lower()
    if value in ("true", "t", "yes", "y", "1", "on"):
        return True
    elif value in ("false", "f", "no", "n", "0", "off"):
        return False
    else:
        raise ValueError(f"Invalid truth value: {value}")
