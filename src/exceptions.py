class ParserFindTagException(Exception):
    """Вызывается, когда парсер не может найти тег."""


class VersionsNotFoundException(Exception):
    """Выбрасывается, если не удалось найти список версий Python."""


class ParserMainError(Exception):
    """Исключение для основной логики программы."""
