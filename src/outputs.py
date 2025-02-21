import csv
import datetime as dt
import logging

from prettytable import PrettyTable

from constants import BASE_DIR, DATETIME_FORMAT, PRETTY, FILE


def control_output(results, cli_args):
    """
    Обрабатывает и выводит результаты в заданном формате.

    Формат вывода определяется аргументом cli_args.output:
    - PRETTY: красивый вывод с помощью PrettyTable.
    - FILE: сохранение результатов в файл.
    - По умолчанию: стандартный построчный вывод.
    """
    output = cli_args.output
    output_handlers = {
        PRETTY: pretty_output,
        FILE: file_output,
    }
    handler = output_handlers.get(output, default_output)
    handler(results, cli_args) if output == FILE else handler(results)


def default_output(results):
    """
    Печатает список results построчно.
    """
    for row in results:
        print(*row)


def pretty_output(results):
    """
    Выводит результаты в виде таблицы с помощью PrettyTable.

    Первая строка results используется как заголовки столбцов.
    Остальные строки добавляются в таблицу как данные.
    """
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)


def file_output(results, cli_args):
    """
    Сохраняет результаты в CSV-файл в папке 'results'.

    - results: данные для сохранения.
    - cli_args: аргументы командной строки, содержащие режим работы.

    Логи:
    - Создает папку 'results', если её нет.
    - Записывает логи о сохранении файла.
    """
    # Тесты не проходят, если при объявлении RESULTS_DIR
    # отсутствует переменная BASE_DIR
    # Прекод в этом уроке (это не самостоятельная работа)
    # Ссылка на урок: [Спринт 19/27 →
    # Тема 5/7: Вывод и хранение результатов парсинга → Урок 2/2]
    RESULTS_DIR = BASE_DIR / 'results'
    RESULTS_DIR.mkdir(exist_ok=True)

    parser_mode = cli_args.mode
    now = dt.datetime.now()
    now_formatted = now.strftime(DATETIME_FORMAT)
    file_name = f'{parser_mode}_{now_formatted}.csv'
    file_path = RESULTS_DIR / file_name
    with open(file_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(f, dialect='unix')
        writer.writerows(results)

    logging.info(f'Файл с результатами был сохранён: {file_path}')
