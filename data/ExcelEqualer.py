import pandas as pd
import re
from difflib import SequenceMatcher
import sqlite3
from datetime import datetime
import os


def normalize_dish_name(name):
    """
    УЛУЧШЕННАЯ нормализация для обработки сложных случаев
    """
    if pd.isna(name):
        return ""

    name_str = str(name).strip()

    # 1. Приводим к нижнему регистру
    name_str = name_str.lower()

    # 2. Убираем слово "салат" в начале с любыми символами после
    if name_str.startswith('салат'):
        # Убираем "салат" и все не-буквенные символы после него
        name_str = name_str[5:]  # "салат" = 5 символов
        # Убираем пробелы, кавычки, дефисы и т.д.
        name_str = re.sub(r'^[^а-яa-z0-9]+', '', name_str)

    # 3. Убираем ВСЕ кавычки любых типов (включая "умные" кавычки)
    name_str = re.sub(r'[\"\'\«\»\„\`\"]', '', name_str)

    # 4. Убираем категории в конце (К, П и т.д.)
    name_str = re.sub(r'\s*[кпгснв]\s*$', '', name_str)

    # 5. Убираем вес (гр, г)
    name_str = re.sub(r'\s*\d+\s*гр?\b', '', name_str)
    name_str = re.sub(r'\s*\(\s*\d+\s*гр?\s*\)', '', name_str)

    # 6. Убираем количество штук
    name_str = re.sub(r'\s*\d+\s*шт\.?\b', '', name_str)

    # 7. Убираем цену (85 руб., 112 руб. и т.д.)
    name_str = re.sub(r'\s*\d+[\.,]?\d*\s*руб?\.?\s*$', '', name_str)

    # 8. Убираем всё, что в скобках (описание ингредиентов)
    # Сначала убираем скобки с описанием
    name_str = re.sub(r'\([^)]*\)', '', name_str)

    # 9. Убираем хэштеги и специальные символы
    name_str = re.sub(r'#', '', name_str)

    # 10. Заменяем дефисы и тире на пробелы (для "по-корейски" -> "по корейски")
    name_str = re.sub(r'[-–—]', ' ', name_str)

    # 11. Убираем лишние пробелы
    name_str = re.sub(r'\s+', ' ', name_str)
    name_str = name_str.strip()

    return name_str


def calculate_similarity(name1, name2):
    """
    Улучшенный расчет схожести
    """
    norm1 = normalize_dish_name(name1)
    norm2 = normalize_dish_name(name2)

    if not norm1 or not norm2:
        return 0

    # Полное совпадение после нормализации
    if norm1 == norm2:
        return 1.0

    # Если одно название содержится в другом
    if norm1 in norm2 or norm2 in norm1:
        return 0.9

    # Используем SequenceMatcher
    similarity = SequenceMatcher(None, norm1, norm2).ratio()

    # Бонус для коротких названий
    if len(norm1) <= 5 or len(norm2) <= 5:
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.9)

    # Бонус если названия начинаются одинаково
    if norm1[:3] == norm2[:3]:
        similarity = max(similarity, 0.85)

    return min(similarity, 1.0)

def load_price_margin_file(file_path):
    """
    Загружает файл с ценами и маржами
    """
    try:
        df = pd.read_excel(file_path)
        print(f"📥 Загружен файл с ценами: {file_path}")
        print(f"   Колонки: {list(df.columns)}")
        print(f"   Всего строк: {len(df)}")

        # Определяем структуру столбцов
        column_mapping = {}

        # Автоматическое определение столбцов
        for col in df.columns:
            col_lower = str(col).lower()

            if 'товар' in col_lower or 'наименование' in col_lower or 'блюдо' in col_lower:
                column_mapping['dish_name'] = col
            elif 'тип' in col_lower or 'категория' in col_lower:
                column_mapping['dish_type'] = col
            elif 'цена' in col_lower or 'продаж' in col_lower or 'стоимость' in col_lower:
                column_mapping['price'] = col
            elif 'маржа' in col_lower and '%' in str(col).lower():
                column_mapping['margin'] = col
            elif 'себестоимость' in col_lower or 'cost' in col_lower:
                column_mapping['cost'] = col

        print(f"   Определены столбцы: {column_mapping}")

        # Проверяем наличие обязательных столбцов
        required = ['dish_name']
        missing = [col for col in required if col not in column_mapping]

        if missing:
            print(f"❌ ОШИБКА: Отсутствуют обязательные столбцы: {missing}")
            return None

        # Создаем DataFrame с нормализованными данными
        result_data = []

        for idx, row in df.iterrows():
            # Пропускаем пустые строки или строки с категориями
            if pd.isna(row.get(column_mapping['dish_name'], '')):
                continue

            dish_data = {
                'original_index': idx + 2,  # +2 для Excel (шапка + 1-индексация)
                'original_name': str(row[column_mapping['dish_name']]).strip(),
                'normalized_name': normalize_dish_name(row[column_mapping['dish_name']]),
                'type': str(row.get(column_mapping.get('dish_type'), '')).strip() if column_mapping.get(
                    'dish_type') else '',
                'price': row.get(column_mapping.get('price')),
                'margin': row.get(column_mapping.get('margin')),
                'cost': row.get(column_mapping.get('cost'))
            }

            # Обрабатываем маржу (убираем % и преобразуем в число)
            if pd.notna(dish_data['margin']):
                try:
                    margin_str = str(dish_data['margin'])
                    margin_str = margin_str.replace('%', '').replace(',', '.').strip()
                    dish_data['margin'] = float(margin_str)
                except:
                    dish_data['margin'] = None

            result_data.append(dish_data)

        return pd.DataFrame(result_data)

    except Exception as e:
        print(f"❌ Ошибка загрузки файла: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_database_dishes(db_path="canteen.db"):
    """
    Загружает блюда из базы данных
    """
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT id, type, name, description, cost, weight, 
                   main_ingredient, marge, is_using
            FROM dishes
            WHERE is_using = 1
            ORDER BY id
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        print(f"📊 Загружено {len(df)} блюд из базы данных")

        if df.empty:
            print("⚠️  База данных пуста")
            return df

        # Добавляем нормализованное название
        df['normalized_name'] = df['name'].apply(normalize_dish_name)

        return df

    except Exception as e:
        print(f"❌ Ошибка загрузки базы данных: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()  # Возвращаем пустой DataFrame вместо None


def match_dishes_with_high_confidence(price_df, db_df, similarity_threshold=0.95):
    """
    Сопоставляет блюда с высокой степенью уверенности
    Возвращает три DataFrame: точные совпадения, возможные совпадения, проблемы
    """
    exact_matches = []
    possible_matches = []
    problems = []

    # Создаем словарь для быстрого поиска по нормализованному имени
    db_dict = {}
    for _, db_row in db_df.iterrows():
        norm_name = db_row['normalized_name']
        if norm_name:
            if norm_name not in db_dict:
                db_dict[norm_name] = []
            # Преобразуем строку DataFrame в словарь
            db_dict[norm_name].append(db_row.to_dict())

    # Преобразуем db_df в список словарей для более удобного поиска
    db_list = db_df.to_dict('records')

    # Проходим по всем блюдам из файла цен
    for _, price_row in price_df.iterrows():
        # Получаем данные как словарь
        price_dict = price_row.to_dict()
        price_norm_name = price_dict['normalized_name']
        price_original_name = price_dict['original_name']
        price_type = price_dict['type']

        # Пропускаем пустые названия
        if not price_norm_name:
            problems.append({
                **price_dict,
                'problem': 'Пустое название',
                'suggested_solution': 'Проверить исходные данные'
            })
            continue

        # Ищем точное совпадение по нормализованному имени
        if price_norm_name in db_dict:
            db_matches = db_dict[price_norm_name]

            if len(db_matches) == 1:
                # Идеальное совпадение - одно блюдо с таким же нормализованным именем
                exact_matches.append({
                    **price_dict,
                    'db_id': db_matches[0]['id'],
                    'db_name': db_matches[0]['name'],
                    'db_type': db_matches[0]['type'],
                    'confidence': 1.0,
                    'match_type': 'exact_normalized'
                })
            else:
                # Несколько блюд с одинаковым нормализованным именем
                # Пробуем уточнить по типу
                type_matches = [m for m in db_matches if m['type'] == price_type]

                if len(type_matches) == 1:
                    exact_matches.append({
                        **price_dict,
                        'db_id': type_matches[0]['id'],
                        'db_name': type_matches[0]['name'],
                        'db_type': type_matches[0]['type'],
                        'confidence': 0.98,
                        'match_type': 'exact_with_type'
                    })
                else:
                    # Неоднозначное совпадение
                    possible_matches.append({
                        **price_dict,
                        'possible_db_matches': [
                            {'id': m['id'], 'name': m['name'], 'type': m['type']}
                            for m in db_matches[:3]  # Берем только первые 3
                        ],
                        'confidence': 0.8,
                        'match_type': 'ambiguous_normalized'
                    })
        else:
            # Точного совпадения нет, ищем похожие
            best_match = None
            best_similarity = 0

            # Ищем по всему списку блюд
            for db_item in db_list:
                similarity = calculate_similarity(
                    price_original_name,
                    db_item['name']
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = db_item

            if best_similarity >= similarity_threshold and best_match:
                # Высокая схожесть - считаем совпадением
                exact_matches.append({
                    **price_dict,
                    'db_id': best_match['id'],
                    'db_name': best_match['name'],
                    'db_type': best_match['type'],
                    'confidence': best_similarity,
                    'match_type': 'high_similarity'
                })
            elif best_similarity >= 0.7 and best_match:
                # Средняя схожесть - возможное совпадение
                possible_matches.append({
                    **price_dict,
                    'possible_db_matches': [{
                        'id': best_match['id'],
                        'name': best_match['name'],
                        'type': best_match['type'],
                        'similarity': best_similarity
                    }],
                    'confidence': best_similarity,
                    'match_type': 'medium_similarity'
                })
            else:
                # Низкая схожесть или нет совпадений
                problem_item = {
                    **price_dict,
                    'problem': f'Не найдено совпадение (максимальная схожесть: {best_similarity:.2%})',
                    'suggested_solution': 'Требуется ручная проверка'
                }

                if best_match:
                    problem_item['best_match'] = {
                        'id': best_match['id'],
                        'name': best_match['name'],
                        'similarity': best_similarity
                    }

                problems.append(problem_item)

    exact_df = pd.DataFrame(exact_matches) if exact_matches else pd.DataFrame()
    possible_df = pd.DataFrame(possible_matches) if possible_matches else pd.DataFrame()
    problems_df = pd.DataFrame(problems) if problems else pd.DataFrame()

    return exact_df, possible_df, problems_df


def update_database_with_matches(exact_matches_df, db_path="canteen.db"):
    """
    Обновляет базу данных с маржой на основе точных совпадений
    """
    if exact_matches_df.empty:
        print("⚠️  Нет точных совпадений для обновления")
        return 0

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        updated_count = 0
        errors_count = 0

        print(f"\n🔄 Обновление базы данных маржой...")

        for _, row in exact_matches_df.iterrows():
            try:
                db_id = row['db_id']
                margin_value = row['margin']

                # Проверяем, что маржа валидна
                if pd.isna(margin_value):
                    print(f"   ID {db_id}: пропуск - маржа отсутствует")
                    continue

                # Проверяем существование записи
                cur.execute("SELECT name FROM dishes WHERE id = ?", (db_id,))
                if not cur.fetchone():
                    print(f"   ID {db_id}: запись не найдена в БД")
                    errors_count += 1
                    continue

                # Обновляем маржу
                cur.execute("""
                    UPDATE dishes 
                    SET marge = ?, date_last_used = ?
                    WHERE id = ?
                """, (
                    float(margin_value),
                    "2026-01-01 10:00:00",
                    db_id
                ))

                updated_count += 1
                print(f"   ✓ ID {db_id}: маржа обновлена до {margin_value}%")

            except Exception as e:
                print(f"   ✗ ID {db_id}: ошибка обновления - {e}")
                errors_count += 1
                continue

        conn.commit()
        conn.close()

        print(f"\n✅ Обновлено записей: {updated_count}")
        print(f"   Ошибок: {errors_count}")

        return updated_count

    except Exception as e:
        print(f"❌ Ошибка обновления базы данных: {e}")
        return 0


def create_clear_report(price_df, db_df, exact_df, possible_df, problems_df, output_dir="reports"):
    """
    Создает четкий отчет в соответствии с требованиями
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Основной отчет с фиксированным именем
    main_report_path = os.path.join(output_dir, "sync_report.xlsx")

    print(f"\n📋 СОЗДАНИЕ ОТЧЕТА...")

    try:
        # Создаем Excel writer для нескольких листов
        with pd.ExcelWriter(main_report_path, engine='openpyxl') as writer:

            # 1. Не найдено в ценах (блюда из меню без соответствий в файле цен)
            print("   1. Лист: Не найдено в ценах")

            # Получаем ID всех блюд, которые были сопоставлены
            matched_db_ids = set(exact_df['db_id'].tolist())

            # Ищем блюда из базы, которые не нашли в файле цен
            not_found_in_prices = []
            for _, db_row in db_df.iterrows():
                if db_row['id'] not in matched_db_ids:
                    # Проверяем, есть ли это блюдо в possible совпадениях
                    in_possible = False
                    for _, pos_row in possible_df.iterrows():
                        if 'possible_db_matches' in pos_row and pos_row['possible_db_matches']:
                            for match in pos_row['possible_db_matches']:
                                if match.get('id') == db_row['id']:
                                    in_possible = True
                                    break

                    if not in_possible:
                        not_found_in_prices.append({
                            'ID_меню': db_row['id'],
                            'Тип_меню': db_row['type'],
                            'Название_меню': db_row['name'],
                            'Себестоимость_меню': db_row['cost'],
                            'Маржа_меню': db_row['marge'],
                            'Вес_меню': db_row['weight'],
                            'Основной_ингредиент': db_row['main_ingredient'],
                            'Статус': 'Не найден в файле цен'
                        })

            if not_found_in_prices:
                not_found_df = pd.DataFrame(not_found_in_prices)
                not_found_df.to_excel(
                    writer, sheet_name='Не_найдено_в_ценах', index=False
                )
                print(f"      ✓ Записей: {len(not_found_df)}")
            else:
                pd.DataFrame([{'Сообщение': 'Все блюда из меню найдены в ценах'}]).to_excel(
                    writer, sheet_name='Не_найдено_в_ценах', index=False
                )
                print(f"      ✓ Все блюда найдены в ценах")

            # 2. Не найдено в меню (строки из файла цен без соответствий в базе)
            print("   2. Лист: Не найдено в меню")

            # Получаем оригинальные индексы всех строк, которые были сопоставлены
            matched_price_indices = set()

            # Добавляем точные совпадения
            for _, row in exact_df.iterrows():
                matched_price_indices.add(row['original_index'])

            # Добавляем возможные совпадения
            for _, row in possible_df.iterrows():
                if 'original_index' in row:
                    matched_price_indices.add(row['original_index'])

            # Ищем строки из файла цен, которые не нашли в базе
            not_found_in_menu = []
            for _, price_row in price_df.iterrows():
                if price_row['original_index'] not in matched_price_indices:
                    not_found_in_menu.append({
                        'Строка_в_файле': price_row['original_index'],
                        'Название_в_файле': price_row['original_name'],
                        'Нормализованное_название': price_row['normalized_name'],
                        'Тип_в_файле': price_row['type'],
                        'Цена_продажи': price_row['price'],
                        'Маржа_в_файле': price_row['margin'],
                        'Себестоимость_в_файле': price_row['cost'],
                        'Статус': 'Не найден в меню'
                    })

            if not_found_in_menu:
                not_in_menu_df = pd.DataFrame(not_found_in_menu)
                not_in_menu_df.to_excel(
                    writer, sheet_name='Не_найдено_в_меню', index=False
                )
                print(f"      ✓ Записей: {len(not_in_menu_df)}")
            else:
                pd.DataFrame([{'Сообщение': 'Все строки из файла цен найдены в меню'}]).to_excel(
                    writer, sheet_name='Не_найдено_в_меню', index=False
                )
                print(f"      ✓ Все строки найдены в меню")

            # 3. Что было соотнесено (все успешные сопоставления)
            print("   3. Лист: Соотнесенные_блюда")

            correlated_data = []

            # Добавляем точные совпадения
            for _, exact_row in exact_df.iterrows():
                # Находим соответствующую запись из базы
                db_match = db_df[db_df['id'] == exact_row['db_id']]
                if not db_match.empty:
                    db_item = db_match.iloc[0]

                    correlated_data.append({
                        'ID_меню': db_item['id'],
                        'Тип_меню': db_item['type'],
                        'Название_меню': db_item['name'],
                        'Себестоимость_меню': db_item['cost'],
                        'Маржа_меню_до': db_item['marge'],  # Маржа до обновления
                        'Маржа_меню_после': exact_row['margin'],  # Маржа после обновления
                        'Вес_меню': db_item['weight'],
                        'Основной_ингредиент': db_item['main_ingredient'],
                        'Строка_в_файле': exact_row['original_index'],
                        'Название_в_файле': exact_row['original_name'],
                        'Тип_в_файле': exact_row['type'],
                        'Цена_продажи': exact_row['price'],
                        'Маржа_в_файле': exact_row['margin'],
                        'Себестоимость_в_файле': exact_row['cost'],
                        'Уверенность': exact_row['confidence'],
                        'Тип_совпадения': exact_row['match_type'],
                        'Статус': 'ТОЧНОЕ СООТВЕТСТВИЕ'
                    })

            # Добавляем возможные совпадения (требуют проверки)
            for _, possible_row in possible_df.iterrows():
                if 'possible_db_matches' in possible_row and possible_row['possible_db_matches']:
                    for match in possible_row['possible_db_matches']:
                        db_match = db_df[db_df['id'] == match['id']]
                        if not db_match.empty:
                            db_item = db_match.iloc[0]

                            correlated_data.append({
                                'ID_меню': db_item['id'],
                                'Тип_меню': db_item['type'],
                                'Название_меню': db_item['name'],
                                'Себестоимость_меню': db_item['cost'],
                                'Маржа_меню_до': db_item['marge'],
                                'Маржа_меню_после': possible_row.get('margin'),
                                'Вес_меню': db_item['weight'],
                                'Основной_ингредиент': db_item['main_ingredient'],
                                'Строка_в_файле': possible_row.get('original_index', ''),
                                'Название_в_файле': possible_row.get('original_name', ''),
                                'Тип_в_файле': possible_row.get('type', ''),
                                'Цена_продажи': possible_row.get('price'),
                                'Маржа_в_файле': possible_row.get('margin'),
                                'Себестоимость_в_файле': possible_row.get('cost'),
                                'Уверенность': possible_row.get('confidence', 0),
                                'Тип_совпадения': possible_row.get('match_type', ''),
                                'Статус': 'ВОЗМОЖНОЕ СООТВЕТСТВИЕ'
                            })

            if correlated_data:
                correlated_df = pd.DataFrame(correlated_data)
                # Сортируем по статусу и уверенности
                correlated_df['sort_order'] = correlated_df['Статус'].map({
                    'ТОЧНОЕ СООТВЕТСТВИЕ': 1,
                    'ВОЗМОЖНОЕ СООТВЕТСТВИЕ': 2
                })
                correlated_df = correlated_df.sort_values(['sort_order', 'Уверенность'], ascending=[True, False])
                correlated_df = correlated_df.drop('sort_order', axis=1)

                correlated_df.to_excel(
                    writer, sheet_name='Соотнесенные_блюда', index=False
                )
                print(f"      ✓ Записей: {len(correlated_df)}")
            else:
                pd.DataFrame([{'Сообщение': 'Нет соотнесенных блюд'}]).to_excel(
                    writer, sheet_name='Соотнесенные_блюда', index=False
                )
                print(f"      ✓ Нет соотнесенных блюд")

            # 4. Статистика
            print("   4. Лист: Статистика")

            # Подсчитываем статистику
            total_in_menu = len(db_df)
            total_in_prices = len(price_df)
            exact_matches_count = len(exact_df)
            possible_matches_count = len(possible_df)
            problems_count = len(problems_df)

            # Блюда без маржи в меню
            without_margin = len(db_df[db_df['marge'].isna()])

            # Процент покрытия
            coverage_menu = (exact_matches_count / total_in_menu * 100) if total_in_menu > 0 else 0
            coverage_prices = (exact_matches_count / total_in_prices * 100) if total_in_prices > 0 else 0

            stats_data = {
                'Показатель': [
                    'Всего блюд в меню (БД)',
                    'Всего строк в файле цен',
                    'Точные соответствия',
                    'Возможные соответствия (требуют проверки)',
                    'Проблемные строки',
                    'Блюд в меню без маржи (до синхронизации)',
                    'Блюд в меню без маржи (после синхронизации)',
                    'Покрытие меню (точные соответствия)',
                    'Покрытие файла цен (точные соответствия)',
                    'Обновлено записей в БД',
                    'Дата и время синхронизации'
                ],
                'Значение': [
                    total_in_menu,
                    total_in_prices,
                    exact_matches_count,
                    possible_matches_count,
                    problems_count,
                    without_margin,
                    len(not_found_in_prices),  # Блюда без маржи после синхронизации
                    f"{coverage_menu:.1f}%",
                    f"{coverage_prices:.1f}%",
                    exact_matches_count,  # Все точные соответствия обновляются
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
            }

            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Статистика', index=False)
            print(f"      ✓ Статистика сформирована")

        print(f"\n✅ ОТЧЕТ СОХРАНЕН: {main_report_path}")
        print(f"   Файл будет перезаписан при следующей синхронизации")

        # Также выводим краткую сводку в консоль
        print(f"\n📊 КРАТКАЯ СВОДКА:")
        print(f"   ===================")
        print(f"   Не найдено в ценах: {len(not_found_in_prices)} блюд из меню")
        print(f"   Не найдено в меню: {len(not_found_in_menu)} строк из файла цен")
        print(f"   Соотнесено: {len(correlated_data)} записей")
        print(f"   ===================")

        return main_report_path

    except Exception as e:
        print(f"❌ Ошибка создания отчета: {e}")
        import traceback
        traceback.print_exc()
        return None


def sync_prices_and_margin(price_file_path, db_path="canteen.db", similarity_threshold=0.90):
    """
    Основная функция для синхронизации цен и маржи с высокой точностью
    """
    print("=" * 70)
    print("🔗 СИНХРОНИЗАЦИЯ ЦЕН И МАРЖИ С ВЫСОКОЙ ТОЧНОСТЬЮ")
    print("=" * 70)

    # 1. Загружаем данные из файла цен
    print("\n📥 ЗАГРУЗКА ФАЙЛА С ЦЕНАМИ И МАРЖЕЙ:")
    price_df = load_price_margin_file(price_file_path)

    if price_df is None or price_df.empty:
        print("❌ Не удалось загрузить файл с ценами")
        return

    print(f"   Обработано строк: {len(price_df)}")

    # 2. Загружаем данные из базы
    print("\n📊 ЗАГРУЗКА ДАННЫХ ИЗ БАЗЫ:")
    db_df = load_database_dishes(db_path)

    if db_df is None or db_df.empty:
        print("❌ Не удалось загрузить данные из базы")
        return

    print(f"   Загружено блюд из БД: {len(db_df)}")

    # 3. Сопоставляем блюда
    print("\n🔍 СРАВНЕНИЕ И СОВПАДЕНИЕ БЛЮД:")
    print(f"   Порог уверенности: {similarity_threshold:.0%}")

    exact_df, possible_df, problems_df = match_dishes_with_high_confidence(
        price_df, db_df, similarity_threshold
    )

    print(f"   ✓ Точные совпадения: {len(exact_df)}")
    print(f"   ⚠️  Возможные совпадения (требуют проверки): {len(possible_df)}")
    print(f"   ❌ Проблемные строки: {len(problems_df)}")

    # 4. Обновляем базу данных точными совпадениями
    updated_count = 0
    if not exact_df.empty:
        print("\n💾 ОБНОВЛЕНИЕ БАЗЫ ДАННЫХ:")
        updated_count = update_database_with_matches(exact_df, db_path)
        print(f"   Успешно обновлено: {updated_count} записей")
    else:
        print("\n⚠️  Нет точных совпадений для обновления базы")

    # 5. Создаем отчет
    print("\n📋 СОЗДАНИЕ ОТЧЕТА:")
    report_path = create_clear_report(
        price_df, db_df, exact_df, possible_df, problems_df
    )

    # 6. Статистика
    print("\n📊 ИТОГОВАЯ СТАТИСТИКА:")
    total_processed = len(price_df)
    exact_percent = (len(exact_df) / total_processed * 100) if total_processed > 0 else 0
    possible_percent = (len(possible_df) / total_processed * 100) if total_processed > 0 else 0

    print(f"   Всего обработано строк: {total_processed}")
    print(f"   Точные совпадения: {len(exact_df)} ({exact_percent:.1f}%)")
    print(f"   Требуют проверки: {len(possible_df)} ({possible_percent:.1f}%)")
    print(f"   Обновлено в БД: {updated_count}")

    print("\n" + "=" * 70)
    print("✅ СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА")
    print("=" * 70)

    return {
        'total': total_processed,
        'exact': len(exact_df),
        'possible': len(possible_df),
        'problems': len(problems_df),
        'updated': updated_count,
        'report_path': report_path
    }


def validate_margin_update(db_path="canteen.db"):
    """
    Валидация обновления маржи
    """
    try:
        conn = sqlite3.connect(db_path)

        # Получаем статистику
        query_stats = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN marge IS NOT NULL THEN 1 END) as with_margin,
                COUNT(CASE WHEN marge IS NULL THEN 1 END) as without_margin,
                AVG(marge) as avg_margin
            FROM dishes
            WHERE is_using = 1
        """

        stats_df = pd.read_sql_query(query_stats, conn)

        # Получаем несколько обновленных записей
        query_recent = """
            SELECT id, name, type, cost, marge, date_last_used
            FROM dishes
            WHERE marge IS NOT NULL
            ORDER BY date_last_used DESC
            LIMIT 5
        """

        recent_df = pd.read_sql_query(query_recent, conn)
        conn.close()

        print("\n🔍 ВАЛИДАЦИЯ ОБНОВЛЕНИЯ МАРЖИ:")
        print(f"   Всего блюд в БД: {stats_df.iloc[0]['total']}")
        print(f"   С маржей: {stats_df.iloc[0]['with_margin']}")
        print(f"   Без маржи: {stats_df.iloc[0]['without_margin']}")
        print(f"   Средняя маржа: {stats_df.iloc[0]['avg_margin']:.2f}%")

        print("\n📝 НЕДАВНО ОБНОВЛЕННЫЕ ЗАПИСИ:")
        for _, row in recent_df.iterrows():
            print(f"   ID {row['id']}: {row['name'][:30]:30} - маржа {row['marge']}%")

    except Exception as e:
        print(f"❌ Ошибка валидации: {e}")


# Для запуска вручную
if __name__ == "__main__":
    # Укажите путь к файлу с ценами
    price_file = "путь_к_вашему_файлу_с_ценами.xlsx"

    result = sync_prices_and_margin(price_file)

    if result:
        print(f"\nОтчет сохранен: {result['report_path']}")