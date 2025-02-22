import requests
import logging

from bs4 import BeautifulSoup

from exceptions import ParserFindTagException


def get_response(session, url, encoding='utf-8'):
    """
    Выполняет GET-запрос по указанному URL и устанавливает кодировку.

    Параметры:
    - session: объект requests.Session для выполнения запроса.
    - url: строка с адресом страницы, которую нужно загрузить.
    - encoding: кодировка для установки (по умолчанию 'utf-8').

    Возвращает:
    - объект response при успешном запросе.

    Исключения:
    - ConnectionError при сбое запроса.
    """
    try:
        response = session.get(url)
        response.encoding = encoding
        return response
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Ошибка соединения при запросе {url}") from e


def find_tag(soup, tag, attrs=None):
    """
    Ищет первый тег в переданном объекте BeautifulSoup.

    Параметры:
    - soup (BeautifulSoup): Объект парсера HTML/XML.
    - tag (str): Название искомого тега.
    - attrs (dict, optional): Атрибуты, по которым выполняется поиск).

    Возвращает:
    - (Tag): Найденный тег.

    Исключения:
    - ParserFindTagException: Если тег не найден.
    """
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag


def check_status_matches(data_page, data_table, url):
    """
    Проверяет соответствие статуса страницы ожидаемому статусу.

    Параметры:
    - data_page (str): Статус, найденный на странице.
    - data_table (tuple): Кортеж ожидаемых статусов.
    - url (str): URL страницы.

    Возвращает:
    - (str | bool): Совпадающий статус, если найден, иначе False.

    Логирование:
    - Выводит предупреждение, если статус не совпадает.
    """
    if data_page not in data_table:
        logging.warning(
            'Несовпадающие статусы:\n'
            f'URL: {url}\n'
            f'Статус в карточке: {data_page}\n'
            f'Ожидаемые статусы: {data_table}\n'
        )
        return False
    return data_page


def cook_soup(session, url, features='lxml'):
    """
    Выполняет HTTP-запрос и преобразует HTML-ответ в объект BeautifulSoup.

    Параметры:
    - session (requests.Session): Сессия для выполнения запроса.
    - url (str): URL страницы для запроса.
    - features (str): Парсер, который будет использовать BeautifulSoup.
      По умолчанию используется 'lxml' для быстрой обработки HTML.

    Возвращает:
    - soup (BeautifulSoup): Объект BeautifulSoup для парсинга HTML.
    """
    response = get_response(session, url)
    return BeautifulSoup(response.text, features)
