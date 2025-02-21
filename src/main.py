import logging
import re
from collections import Counter
from urllib.parse import urljoin

import requests_cache
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import (BASE_DIR, EXPECTED_STATUS,
                       MAIN_DOC_URL, PEP_LIST_URL, UNKNOWN_VALUE)
from exceptions import ParserMainError, VersionsNotFoundException
from outputs import control_output
from utils import check_status_matches, cook_soup, find_tag


def whats_new(session):
    """
    Собирает информацию о нововведениях в Python.

    Функция парсит страницу "What's New in Python" и извлекает:
    - Ссылку на статью.
    - Заголовок статьи.
    - Информацию о редакторах и авторах.

    Если загрузка страницы версии Python не удалась, итерация пропускается,
    а в лог записывается предупреждение.

    Аргументы:
    - session (requests_cache.CachedSession):
        Кеширующая сессия для HTTP-запросов.

    Возвращает:
    - list[tuple[str, str, str]]: Список кортежей, содержащих:
      ('Ссылка на статью', 'Заголовок', 'Редактор, автор').
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')

    soup = cook_soup(session, whats_new_url)

    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'})

    results = [('Ссылка на статью', 'Заголовок',
                'Редактор, автор')]
    error_messages = []
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')

        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)

        try:
            soup = cook_soup(session, version_link)
        except ConnectionError as error:
            error_messages.append(
                f'Ошибка при загрузке {version_link}: {error}'
            )
            continue
    if error_messages:
        logging.warning("\n".join(error_messages))

        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')

        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text))
    return results


def latest_versions(session):
    """
    Извлекает список последних версий Python со страницы документации.

    Параметры:
    - session (requests.Session): Сессия с поддержкой кеширования.

    Возвращает:
    - list[tuple]: Список кортежей с данными о версиях в формате:
      ('Ссылка на статью', 'Версия Python', 'Статус')

    Исключения:
    - VersionsNotFoundException: Если список версий не найден на странице.
    """
    soup = cook_soup(session, MAIN_DOC_URL)

    ul_tags = soup.find_all('ul')

    for ul in tqdm(ul_tags):
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise VersionsNotFoundException(
            "Не удалось найти список версий Python на странице. "
            "Возможно, структура сайта изменилась."
        )

    results = [('Ссылка на статью', 'Заголовок',
                'Редактор, автор')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'

    for a_tag in tqdm(a_tags, desc='Поиск ссылок, версий и их статуса.'):
        link = a_tag['href']
        text = a_tag.text
        match = re.search(pattern, text)

        if match:
            results.append(
                (link, match.group('version'), match.group('status'))
            )

    return results


def download(session):
    """
    Скачивает архив с документацией Python в формате PDF (A4).

    Параметры:
    - session (requests.Session): Сессия с поддержкой кеширования.

    Возвращает:
    - None
    """
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')

    soup = cook_soup(session, downloads_url)

    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(table_tag,
                          'a',
                          {'href': re.compile(r'.+pdf-a4\.zip$')})

    pdf_a4_link = pdf_a4_tag['href']

    archive_url = urljoin(downloads_url, pdf_a4_link)

    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)

    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    """
    Парсит список PEP и собирает статистику по статусам.

    Параметры:
    - session (requests.Session): Сессия с поддержкой кеширования.

    Логика работы:
    1. Загружает страницу со списком PEP-документов.
    2. Ищет таблицу с перечнем PEP и извлекает статусы.
    3. По каждой записи извлекает ссылку на PEP-документ и получает страницу.
    4. Сравнивает статус PEP из списка со статусом в карточке документа.
    5. Подсчитывает количество PEP в каждом статусе.
    6. Возвращает таблицу с распределением PEP по статусам и общим количеством.

    Возвращает:
    - list: Таблица со статусами и их количеством, включая ['Total', сумма].

    Исключения:
    - ParserFindTagException: Если необходимые теги на страницах не найдены.
    - В случае проблем с доступом к странице отдельного PEP, он пропускается.
    """
    pep_list_url = PEP_LIST_URL

    soup = cook_soup(session, pep_list_url)
    section_id = find_tag(soup, 'section', attrs={'id': 'index-by-category'})
    rows = section_id.find_all('tr')

    results = [('Статус', 'Количество')]
    status_counter = Counter()

    for row in tqdm(rows):
        if not row.find('td'):
            continue
        version_pep_tag = find_tag(row, 'a')
        href = version_pep_tag['href']
        pep_item_url = urljoin(PEP_LIST_URL, href)
        abbr_td = find_tag(row, 'td')
        abbr = find_tag(abbr_td, 'abbr')
        types_and_status_list = abbr.text
        status_symbol = (
            types_and_status_list[1]
            if len(types_and_status_list) > 1
            else ''
        )
        status_value = EXPECTED_STATUS.get(status_symbol, (UNKNOWN_VALUE))

        error_messages = []
        try:
            soup = cook_soup(session, pep_item_url)
        except ConnectionError as e:
            error_messages.append(f"Ошибка при загрузке {pep_item_url}: {e}")
            continue

    if error_messages:
        logging.warning("\n".join(error_messages))

        for dt in soup.find_all('dt'):
            if re.search(r'^\s*Status\s*:\s*$', dt.text, re.IGNORECASE):
                status_on_link = dt.find_next_sibling('dd').text
                status_confirmed = check_status_matches(
                    status_on_link, status_value, pep_item_url)
                if status_confirmed:
                    status_counter[status_confirmed] += 1

    results.extend(map(list, status_counter.items()))
    results.append(['Total', sum(status_counter.values())])

    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    """
    Главная функция парсера, управляющая процессом запуска и выполнения.

    В случае исключения:
    - Логирует исключение.
    - Генерирует `ParserMainError`, указывая на сбой в работе парсера.
    """
    configure_logging()
    logging.info('Парсер запущен!')
    try:
        arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
        args = arg_parser.parse_args()

        logging.info(f'Аргументы командной строки: {args}')

        session = requests_cache.CachedSession()
        if args.clear_cache:
            session.cache.clear()

        parser_mode = args.mode
        results = MODE_TO_FUNCTION[parser_mode](session)
        if results is not None:
            control_output(results, args)
    except Exception as error:
        logging.exception(
            f'Во время работы программы произошло исключение: {error}'
        )
        raise ParserMainError('Ошибка выполнения работы парсера.') from error
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
