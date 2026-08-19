import pandas as pd
import sqlite3
from datetime import datetime


def load_excel_with_ids(file_path, db_path="canteen.db", update_prices=True):
    """
    Загружает Excel файл, добавляет ID и синхронизирует с БД
    Обновляет цены у существующих товаров
    """
    # Читаем Excel файл
    try:
        df = pd.read_excel(file_path)
        print(f"📥 Загружен файл: {file_path}")
        print(f"   Колонки: {list(df.columns)}")
        print(f"   Всего строк: {len(df)}")
        # Показываем первые несколько строк для отладки
        print(f"   Первые 5 строк:")
        print(df.head().to_string())
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return 0, None

    # Проверяем наличие нужных колонок
    required_columns = ['type', 'name', 'cost']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ Ошибка: отсутствуют колонки: {missing_columns}")
        print(f"   Доступные колонки: {list(df.columns)}")
        return 0, None

    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Получаем существующие блюда из БД для сравнения
    cur.execute("SELECT id, type, name, cost, description FROM dishes WHERE is_using = 1")
    existing_dishes = cur.fetchall()

    # Создаем несколько словарей для поиска разными способами
    existing_by_name_type = {}  # Основной поиск
    existing_by_id = {}  # Поиск по ID

    for dish in existing_dishes:
        dish_id, dish_type, dish_name, dish_cost, dish_desc = dish
        # Ключ 1: нормализованное название + тип
        key1 = (str(dish_name).strip().lower(), str(dish_type).strip().lower())
        existing_by_name_type[key1] = {
            'id': dish_id,
            'cost': dish_cost,
            'description': dish_desc,
            'name': dish_name,
            'type': dish_type
        }
        # Ключ 2: ID
        existing_by_id[dish_id] = {
            'name': dish_name,
            'type': dish_type,
            'cost': dish_cost
        }

    print(f"   В БД найдено {len(existing_dishes)} активных блюд")

    # Счетчики
    added_count = 0
    updated_count = 0
    unchanged_count = 0
    skipped_count = 0

    # Список для новых записей
    new_records = []

    # Список для обновления цен
    updates_to_apply = []

    # Обрабатываем каждую строку из файла
    for idx, row in df.iterrows():
        # Получаем данные из строки
        dish_name = str(row.get('name', '')).strip()
        dish_type = str(row.get('type', '')).strip()
        dish_cost = str(row.get('cost', '')).strip()

        # Проверяем обязательные поля
        if not dish_name or not dish_type or not dish_cost:
            print(f"   ⚠️  Строка {idx + 2}: пропуск - отсутствуют обязательные поля")
            skipped_count += 1
            continue

        # Создаем ключ для поиска
        search_key = (dish_name.lower(), dish_type.lower())

        # Проверяем, существует ли уже такое блюдо
        if search_key in existing_by_name_type:
            # Блюдо существует - проверяем цену
            existing_dish = existing_by_name_type[search_key]
            existing_cost = existing_dish['cost']

            if str(existing_cost) != str(dish_cost) and update_prices:
                # Цена изменилась - добавляем в список для обновления
                updates_to_apply.append({
                    'id': existing_dish['id'],
                    'old_cost': existing_cost,
                    'new_cost': dish_cost,
                    'name': dish_name
                })
            else:
                # Цена не изменилась или обновление цен отключено
                unchanged_count += 1
                if str(existing_cost) != str(dish_cost):
                    print(
                        f"   ℹ️  ID {existing_dish['id']}: цена отличается '{existing_cost}' != '{dish_cost}' (обновление отключено)")
                else:
                    print(f"   ✓ ID {existing_dish['id']}: цена не изменилась '{dish_cost}'")
        else:
            # Блюдо не существует - добавляем новое
            # Проверяем, указан ли ID в Excel
            dish_id = None
            if 'ID' in df.columns and pd.notna(row.get('ID')):
                try:
                    potential_id = int(row['ID'])
                    # Проверяем, свободен ли этот ID
                    if potential_id not in existing_by_id:
                        dish_id = potential_id
                        print(f"   📝 Строка {idx + 2}: используем указанный ID {dish_id}")
                    else:
                        print(f"   ⚠️  Строка {idx + 2}: ID {potential_id} уже занят, ищем свободный")
                except (ValueError, TypeError):
                    pass

            # Если ID не задан или занят - находим свободный
            if dish_id is None:
                # Находим максимальный ID
                cur.execute("SELECT MAX(id) FROM dishes")
                max_id = cur.fetchone()[0]
                new_id = 1 if max_id is None else max_id + 1

                # Проверяем свободные ID от 1 до new_id+100
                for i in range(1, new_id + 100):
                    if i not in existing_by_id:
                        dish_id = i
                        break
                else:
                    dish_id = new_id

            # Подготавливаем данные для вставки
            dish_data = {
                'id': dish_id,
                'type': dish_type,
                'name': dish_name,
                'description': str(row.get('info', row.get('description', ''))).strip()
                if pd.notna(row.get('info', row.get('description', ''))) else None,
                'cost': dish_cost,
                'weight': str(row.get('weight', '')).strip() if pd.notna(row.get('weight', '')) else None,
                'main_ingredient': str(row.get('main_ingredient', '')).strip()
                if pd.notna(row.get('main_ingredient', '')) else None,
                'marge': None,
                'date_last_used': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'is_using': 1,
                'is_mandatory': 0
            }

            new_records.append(dish_data)
            print(f"   ➕ Строка {idx + 2}: будет добавлено как ID {dish_id} - {dish_name}")

    # ОБНОВЛЯЕМ существующие записи (цены)
    if updates_to_apply:
        print(f"\n🔄 Обновление цен для {len(updates_to_apply)} блюд:")
        for update in updates_to_apply:
            try:
                cur.execute("""
                    UPDATE dishes 
                    SET cost = ?, date_last_used = ?
                    WHERE id = ?
                """, (
                    update['new_cost'],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    update['id']
                ))
                updated_count += 1
                print(f"   ✅ ID {update['id']}: цена обновлена с '{update['old_cost']}' на '{update['new_cost']}'")
            except Exception as e:
                print(f"   ❌ Ошибка обновления ID {update['id']}: {e}")

    # ДОБАВЛЯЕМ новые записи
    if new_records:
        print(f"\n➕ Добавление {len(new_records)} новых блюд:")
        insert_sql = """
            INSERT INTO dishes 
            (id, type, name, description, cost, weight, main_ingredient, 
             marge, date_last_used, is_using, is_mandatory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for record in new_records:
            try:
                cur.execute(insert_sql, (
                    record['id'],
                    record['type'],
                    record['name'],
                    record['description'],
                    record['cost'],
                    record['weight'],
                    record['main_ingredient'],
                    record['marge'],
                    record['date_last_used'],
                    record['is_using'],
                    record['is_mandatory']
                ))
                added_count += 1
                print(f"   ✅ Добавлено: ID {record['id']} - {record['name']} ({record['type']})")
            except sqlite3.IntegrityError as e:
                print(f"   ❌ Ошибка целостности для ID {record['id']}: {e}")
                # Пробуем с другим ID
                try:
                    # Находим новый свободный ID
                    cur.execute("SELECT MAX(id) FROM dishes")
                    max_id = cur.fetchone()[0]
                    new_id = max_id + 1 if max_id else 1

                    # Обновляем ID в записи
                    record['id'] = new_id
                    cur.execute(insert_sql, (
                        record['id'],
                        record['type'],
                        record['name'],
                        record['description'],
                        record['cost'],
                        record['weight'],
                        record['main_ingredient'],
                        record['marge'],
                        record['date_last_used'],
                        record['is_using'],
                        record['is_mandatory']
                    ))
                    added_count += 1
                    print(f"   ✅ Добавлено с новым ID {record['id']} - {record['name']}")
                except Exception as e2:
                    print(f"   ❌ Критическая ошибка добавления {record['name']}: {e2}")
                continue
            except Exception as e:
                print(f"   ❌ Ошибка добавления ID {record['id']}: {e}")
                continue

    # Коммитим все изменения
    conn.commit()

    # Проверяем итоговое количество записей
    cur.execute("SELECT COUNT(*) FROM dishes WHERE is_using = 1")
    total_in_db = cur.fetchone()[0]

    conn.close()

    # Выводим статистику
    print(f"\n📊 СТАТИСТИКА ОБНОВЛЕНИЯ МЕНЮ:")
    print(f"   Добавлено новых блюд: {added_count}")
    print(f"   Обновлено цен: {updated_count}")
    print(f"   Без изменений: {unchanged_count}")
    print(f"   Пропущено (нет данных): {skipped_count}")
    print(f"   Всего в файле: {len(df)} строк")
    print(f"   Всего активных блюд в БД: {total_in_db}")

    # Сохраняем обновленный файл с ID
    try:
        # Перечитываем данные для сохранения
        conn = sqlite3.connect(db_path)
        query = """
            SELECT id, type, name, cost, description, weight, main_ingredient 
            FROM dishes 
            WHERE is_using = 1 
            ORDER BY type, name
        """
        db_df = pd.read_sql_query(query, conn)
        conn.close()

        # Сохраняем в Excel
        output_path = file_path.replace('.xlsx', '_with_ids.xlsx')
        db_df.to_excel(output_path, index=False)
        print(f"\n💾 Обновленный файл сохранен: {output_path}")
        print(f"   Сохранено записей: {len(db_df)}")
        return added_count + updated_count, output_path
    except Exception as e:
        print(f"❌ Ошибка сохранения файла: {e}")
        return added_count + updated_count, None