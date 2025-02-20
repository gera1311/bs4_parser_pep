from urllib.parse import urljoin
import re
import logging

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm
from collections import Counter

from constants import BASE_DIR, MAIN_DOC_URL, PEP_LIST_URL, EXPECTED_STATUS
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import get_response, find_tag, check_status_matches


def whats_new(session):
    # Вместо константы WHATS_NEW_URL, используйте переменную whats_new_url.
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    # Загрузка веб-страницы с кешированием.
    response = get_response(session, whats_new_url)
    if response is None:
        # Если основная страница не загрузится, программа закончит работу.
        return

    soup = BeautifulSoup(response.text, features='lxml')

    # Шаг 1-й: поиск в "супе" тега section с нужным id. Парсеру нужен только
    # первый элемент, поэтому используется метод find().
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})

    # Шаг 2-й: поиск внутри main_div тега div с классом toctree-wrapper.
    # Здесь тоже нужен только первый элемент, используется метод find()
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})

    # Шаг 3-й: поиск внутри div_with_ul элементов li с классом toctree-l1.
    # Нужны все теги, поэтому используется метод find_all().
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'})

    results = [('Ссылка на статью', 'Заголовок',
                'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')

        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)

        response = get_response(session, version_link)
        if response is None:
            continue

        soup = BeautifulSoup(response.text, 'lxml')

        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')

        dl_text = dl.text.replace('\n', ' ')
        # На печать теперь выводится переменная dl_text — без пустых строчек.
        # print(version_link, h1.text, dl.text)
        results.append(
            (version_link, h1.text, dl_text))
    return results


def latest_versions(session):
    # Загрузка веб-страницы с кешированием.
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return

    soup = BeautifulSoup(response.text, features='lxml')

    # sidebar = soup.find('dev', attrs={'calss': 'sphinxsidebarwrapper'})
    ul_tags = soup.find_all('ul')

    for ul in tqdm(ul_tags):
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')

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
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')

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
    pep_list_url = PEP_LIST_URL
    response = get_response(session, pep_list_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
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
        status_value = EXPECTED_STATUS.get(status_symbol, ('Unknown'))
        response = get_response(session, pep_item_url)
        if response is None:
            return
        soup = BeautifulSoup(response.text, features='lxml')

        for dt in soup.find_all('dt'):
            if dt.text.strip() == 'Status:':
                status_on_link = dt.find_next_sibling('dd').text
                status_confirmed = check_status_matches(
                    status_on_link, status_value, pep_item_url)
                if status_confirmed:
                    status_counter[status_confirmed] += 1

    results += ([[status, count] for status, count in status_counter.items()])
    results.append(['Total', sum(status_counter.values())])

    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    # Конфигурация парсера аргументов командной строки —
    # передача в функцию допустимых вариантов выбора.
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    # Считывание аргументов из командной строки.
    args = arg_parser.parse_args()

    # Логируем переданные аргументы командной строки.
    logging.info(f'Аргументы командной строки: {args}')

    # Создание кеширующей сессии.
    session = requests_cache.CachedSession()
    # Если был передан ключ '--clear-cache', то args.clear_cache == True.
    if args.clear_cache:
        # Очистка кеша.
        session.cache.clear()

    # Получение из аргументов командной строки нужного режима работы.
    parser_mode = args.mode
    # Поиск и вызов нужной функции по ключу словаря.
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    # Логируем завершение работы парсера.
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
