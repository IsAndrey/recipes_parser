import os
import re
import logging
import json

import pymorphy3

BASE_DIR = os.getcwd()

MORPH_ANALYZER = pymorphy3.MorphAnalyzer()
# nomn - именительный Примеры: хомяк
# gent - родительный Примеры: хомяка, нет сахара, нет яда
# datv - дательный Примеры: хомяку
# accs - винительный Примеры: хомяка, взвод солдат
# ablt - творительный Примеры: хомяком
# loct - предложный Примеры: хомяке, говорить о долге, снеге, шкафе
# voct - звательный Примеры: Саш подойди к окну
# gen2 - родительный2 Примеры: ложка сахару, стакан яду
# acc2 - винительный2 Примеры: записался в солдаты
# loc2 - предложный2 (местный) Примеры: я у него в долгу, весь в снегу, висит в шкафу

SPECIAL_MEASUREMENT_UNITS = [
    'по вкусу',
    'на глаз'
]

SPECIAL_AMOUNTS = {
    'один': '1',
    'два': '2',
    'один-два': '1,5',
    'три': '3',
    'два-три': '2,5',
    'пол': '0,5',
    'полтора': '1,5',
    'десяток': '10',
    'дюжина': '12',
    'половинка': '0,5'
}

NORM_EXEPTIONS = {'банк': 'банка'}

MEASUREMENT_UNITS = []  # {'name'}
INGRIDIENTS = []        # {'name', 'measurement_unit'}
TAGS = []               # {'slag', 'text'}

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] >> %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.DEBUG
    )
logger = logging.getLogger(__name__)

def normalize_word(word):
    p = MORPH_ANALYZER.parse(word)[0]
    try:
        norm = p.inflect({'sing', 'nomn'}).word
        if norm not in NORM_EXEPTIONS.keys():
            return norm
        return NORM_EXEPTIONS[norm]
    except:
        logger.error(
            'Ошибка при получении нормальноый формы. '
            f'слово: {word} '
            f'prase: {p}'
        )
        return word

def get_recipe_name(strings):
    recipe_name = ''
    if len(strings) > 0:
        recipe_name = strings.pop(0).strip()
    logger.debug(
        f'Получено наименование рецепта: {recipe_name}'
    )
    return recipe_name

def get_ingridient(ingridient_string):
    # Анализируем несколько шаблонов
    # Первый [ингредиент] [количество] [единица измерения]
    # Второй [ингредиент] [количество не указано = 0] [специальная единица измерения]
    # Третий [ингредиент] [специальное количество] [единица измерения]
    # Четвёртый [специальное количество] [ингредиент] [единица измерения не указана = штука]
    # Пятый [ингредиент] [количество не указано = 1] [единица измерения не указана = штука]

    first_pattern = r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+\d+(?:,\d{1,2})?(?:[ ][а-яё]+)+[;.]'
    second_pattern = (
        r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+'
        + '(?:'
        + '|'.join(smu for smu in SPECIAL_MEASUREMENT_UNITS)
        + ')[;.]'
    )
    third_pattern = (
        r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+'
        + '(?:'
        + '|'.join(sa for sa in SPECIAL_AMOUNTS.keys())
        + ')'
        + r'(?:[ ][а-яё]+)+[;.]'
    )
    forth_pattern = (
        '(?:'
        + '|'.join(sa for sa in SPECIAL_AMOUNTS.keys())
        + ')'
        + r'([ ]\d{1,3}%)?(?:[ ][А-ЯЁа-яё]+)+[;.]'
    )
    fives_pattern = r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])*(?:[а-яё]+[;.])'

    def check_pattern(ingridient_string, **kwargs):
        pattern = kwargs.get('pattern', None)
        if pattern == None:
            logger.error(
                f'Паттерн не передан. {kwargs}'
            )
            return None
        elif re.match(pattern, ingridient_string) is None:
            logger.debug(
                (
                    'Не найдены соответствия '
                    f'шаблог: {pattern} '
                    f'строка {ingridient_string}'
                )
            )
            return None
        logger.debug(
            (
                'Анализ по шаблону '
                f'шаблон: {pattern} '
                f'строка: {ingridient_string}'
            )
        )
          
        all = kwargs.get('all', [])
        defaults = kwargs.get('defaults', {})
        slices = kwargs.get('slices', {})
        if (
            not isinstance(all, list)
            or not isinstance(defaults, dict)
            or not isinstance(slices, dict)
        ):
            logger.error(
                (
                    'Ошибка при передаче параметров шаблона.'
                    f'all: {all}'
                    f'defaults: {defaults}'
                    f'slices: {slices}'
                )
            )
            return None
        ingridient = {}
        parse_string = ingridient_string.lower()
        for item in all:
            pattern = kwargs.get(item, '')
            if len(pattern) == 0:
                default = defaults.get(item, None)
                if default is None:
                    logger.error(
                        (
                            'Не определено значение элемента. '
                            f'элемент: {item} '
                            f'шаблон: {pattern}'
                        )
                    )
                    return None
                ingridient[item] = default
            else:
                val_of_item = re.search(pattern, parse_string)
                if val_of_item is None:
                    logger.error(
                        (
                            'Не определено значение элемента.',
                            f'элемент: {item}',
                            f'шаблон: {pattern}',
                            f'строка: {parse_string}'
                        )
                    )
                    return None
                else:
                    val_of_item = val_of_item.group()
                parse_string = parse_string.replace(val_of_item, '')
                slice = slices.get(item, [])
                if len(slice) == 1:
                    val_of_item = val_of_item[slice[0]:]
                if len(slice) == 2:
                    val_of_item = val_of_item[slice[0]: slice[1]]
                ingridient[item] = val_of_item
    
        return ingridient

    patterns = [
        {
            'pattern': first_pattern,
            'name': r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+',
            'amount': r'\d+(?:,\d{1,2})?',
            'measurement_unit': r'(?:[ ][а-яё]+)+[;.]',
            'all': ['name', 'amount', 'measurement_unit'],
            'defaults': {},
            'slices': {
                'name': [0, -1],
                'measurement_unit': [1, -1]
            }
        },
        {
            'pattern': second_pattern,
            'name': r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+',
            'amount': '',
            'special_measurement_unit': (
                '(?:'
                + '|'.join(smu for smu in SPECIAL_MEASUREMENT_UNITS)
                + ')[;.]'
            ),
            'all': ['special_measurement_unit', 'name', 'amount'],
            'defaults': {
                'amount': '0'
            },
            'slices': {
                'name': [0, -1],
                'special_measurement_unit': [0, -1]
            }
        },
        {
            'pattern': third_pattern,
            'name': r'(\d{1,3}%[ ])?(?:[А_ЯЁа-яё]+[ ])+',
            'special_amount': (
                '(?:'
                + '|'.join(sa for sa in SPECIAL_AMOUNTS.keys())
                + ')'
            ),
            'measurement_unit': r'(?:[ ][а-яё]+)+[;.]',
            'all': ['special_amount', 'name', 'measurement_unit'],
            'defaults': {},
            'slices': {
                'name': [0, -1],
                'measurement_unit': [1, -1]
            }
        },
        {
            'pattern': forth_pattern,
            'name': r'([ ]\d{1,3}%)?(?:[ ][А_ЯЁа-яё]+)+[;.]',
            'special_amount': (
                '(?:'
                + '|'.join(sa for sa in SPECIAL_AMOUNTS.keys())
                + ')'
            ),
            'measurement_unit': '',
            'all': ['special_amount', 'name', 'measurement_unit'],
            'defaults': {
                'measurement_unit': 'штука'
            },
            'slices': {
                'name': [1, -1]
            }
        },
        {
            'pattern': fives_pattern,
            'name': r'(\d{1,3}%[ ])?(?:[А-ЯЁа-яё]+[ ])+(?:[А-ЯЁа-яё]+[;.])',
            'amount': '',
            'measurement_unit': '',
            'all': ['name', 'amount', 'measurement_unit'],
            'defaults': {
                'amount': '1',
                'measurement_unit': 'штука'
            },
            'slices': {
                'name': [0, -1]
            }
        }
    ]
    for kwargs in patterns:
        ingridient = check_pattern(ingridient_string, **kwargs)
        if ingridient is not None:
            special_amount = ingridient.pop('special_amount', None)
            special_measurement_unit = ingridient.pop('special_measurement_unit', None)
            for key in ingridient.keys():
                if key == 'measurement_unit':
                    ingridient[key] = normalize_word(ingridient[key])
            if special_amount is not None:
                val_of_special_amount = SPECIAL_AMOUNTS.get(special_amount, None)
                if val_of_special_amount is not None:
                    ingridient['amount'] = val_of_special_amount
            if special_measurement_unit is not None:
                ingridient['measurement_unit'] = special_measurement_unit
            logger.debug(
                f'Получен ингридиент: {ingridient}'
            )
            INGRIDIENTS.append({'name': ingridient['name'], 'measurement_unit': ingridient['measurement_unit']})
            MEASUREMENT_UNITS.append({'name': ingridient['measurement_unit']})
            return ingridient
    return {}

def get_recipe_ingridients(strings):
    key_phrase = 'Ингридиенты'
    current_string = ''
    ingridients = []
    while len(strings) > 0 and key_phrase not in current_string:
        current_string = strings.pop(0).strip()
    while len(strings) > 0 and len(current_string) > 0:
        current_string = strings.pop(0).strip()
        if len(current_string) > 0:
            ingridients.append(get_ingridient(current_string))
    logger.debug(
        f'Получен список ингридиентов: {len(ingridients)} элементов.'
    )
    return ingridients

def get_recipe_text(strings):
    key_phrase_start = 'Способ приготовления'
    key_phrase_end = 'Блюдо готово'
    current_string = ''
    text = ''
    while len(strings) > 0 and key_phrase_start not in current_string:
        current_string = strings.pop(0).strip()
    while len(strings) > 0 and key_phrase_end not in current_string:
        current_string = strings.pop(0).strip()
        if key_phrase_end not in current_string:
            if len(text) > 0:
                text = text + ' '
            text = text + current_string
    logger.debug(
        f'Получен тект рецепта: {len(text)} символов.'
    )
    return text

def get_tag(tag_string):
    pattern_slag = r'(?:[a-z]+[_]?)+[a-z]+'  # Латинница в нижнем регистре возможно с подчеркиванием
    pattern_text = r'(?:[А-ЯЁа-яё]+[ ])+'    # Кириллица с пробелами
    slag = re.search(pattern_slag, tag_string).group()
    text = re.search(pattern_text, tag_string).group()
    logger.debug(
        f'Получен тэг: ({slag}) {text}'
    )
    TAGS.append({'slag': slag, 'text': text.strip()})
    return slag

def get_recipe_tags(strings):
    key_phrase = 'Тэги'
    current_string = ''
    tags = []
    while len(strings) > 0 and key_phrase not in current_string:
        current_string = strings.pop(0).strip()
    while len(strings) > 0 and len(current_string) > 0:
        current_string = strings.pop(0).strip()
        if len(current_string) > 0:
            logger.debug(
                f'Анализ строки тэгов {current_string}'
            )
            pattern = r'[ ]?(?:[А-ЯЁа-яё]+[ ])+[(](?:[a-z]+[_]?)+[a-z]+[)][,.]'
            # Слаг в круглых скобках, без цифр, разделители точка или запятая

            match_tag_strings = re.match(pattern, current_string)
            while match_tag_strings is not None:
                tag_string = match_tag_strings.group()
                logger.debug(
                    f'Анализ тэга {tag_string}'
                )
                tags.append(get_tag(tag_string))
                current_string = current_string.replace(tag_string, '')
                match_tag_strings = re.match(pattern, current_string)
            
    logger.debug(
        f'Получен список тэгов: {len(tags)} элементов.'
    )
    return tags

def get_recipe_author(strings):
    key_phrase = 'Автор'
    current_string = ''
    author = ''
    while len(strings) > 0 and key_phrase not in current_string:
        current_string = strings.pop(0).strip()
    if len(strings) > 0:
        author = strings.pop(0).strip()
    logger.debug(
        f'Получен автор рецепта: {author}'
    )
    return author

def get_recipe_image(file):
    image = f'\images\{file.name}'.replace('.txt', '.jpeg')
    logger.debug(
        f'Получено изображение: {image}'
    )
    return image

def load_recipe(file_info):
    with open(file=file_info.path, encoding='utf-8') as file:
        strings = file.readlines()
    recipe = {}
    recipe['name'] = get_recipe_name(strings)
    recipe['ingridients'] = get_recipe_ingridients(strings)
    recipe['text'] = get_recipe_text(strings)
    recipe['tags'] = get_recipe_tags(strings)
    recipe['author'] = get_recipe_author(strings)
    recipe['image'] = get_recipe_image(file_info)
    return recipe

def load_dir(path, to_parse = None):
    recipes = []
    i = 0
    with os.scandir(path) as file_list:
        for file in file_list:
            if file.is_file() and file.name[-4:] == '.txt':
                i+=1
                if to_parse is not None:
                    if i not in to_parse:
                        continue
                logger.info(
                    f'Загрузка рецепта: {i} {file.name}'
                )
                recipes.append(load_recipe(
                    file_info=file
                ))
    logger.debug(
        f'Загружено {len(recipes)} рецептов.'
    )
    return recipes

def wrap_list(list_to_wrap, key_field, reverse=-1):
    if len(list_to_wrap) == 0:
        return list_to_wrap
    if key_field not in list_to_wrap[0].keys():
        return list_to_wrap
    wrap = {}
    for record in list_to_wrap[::reverse]:
        wrap[record[key_field]] = record
    return list(wrap.values())

def main():
    data_recipes = load_dir(os.getcwd()+'\data')
    data_measurement_units = wrap_list(MEASUREMENT_UNITS, 'name')
    data_ingridients = wrap_list(INGRIDIENTS, 'name')
    data_tags = wrap_list(TAGS, 'slag')
    with open(os.getcwd()+'\data\\recipes.json', 'w', encoding='utf8') as outfile:
        json.dump(data_recipes, outfile, ensure_ascii=False, indent=4)
    with open(os.getcwd()+'\data\\measurement_units.json', 'w', encoding='utf8') as outfile:
        json.dump(data_measurement_units, outfile, ensure_ascii=False, indent=4)
    with open(os.getcwd()+'\data\\ingridients.json', 'w', encoding='utf8') as outfile:
        json.dump(data_ingridients, outfile, ensure_ascii=False, indent=4)
    with open(os.getcwd()+'\data\\tags.json', 'w', encoding='utf8') as outfile:
        json.dump(data_tags, outfile, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
