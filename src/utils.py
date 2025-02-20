import logging

from requests import RequestException

from exceptions import ParserFindTagException


# Перехват ошибки RequestException.
def get_response(session, url):
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}',
            stack_info=True
        )


# Перехват ошибки поиска тегов.
def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag


# Перехват несовпадения статуса документации.
def check_status_matches(data_page, data_table, url):
    if data_page not in data_table:
        logging.warning(
            'Несовпадающие статусы:\n'
            f'URL: {url}\n'
            f'Статус в карточке: {data_page}\n'
            f'Ожидаемые статусы: {data_table}\n'
        )
        return False
    return data_page
