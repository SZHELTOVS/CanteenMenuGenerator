import sqlite3
import re
import unicodedata
from difflib import SequenceMatcher

DB_NAME = "canteen.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            cost TEXT NOT NULL,
            weight TEXT,
            main_ingredient TEXT,
            marge REAL,
            date_last_used TEXT DEFAULT 20260101 ,
            is_using INTEGER DEFAULT 1,
            is_mandatory INTEGER DEFAULT 0  -- Новое поле: 1 = обязательное, 0 = не обязательное
        );
    """)

    conn.commit()
    conn.close()


# ---------- INSERT ----------
def insert_dish(
        dish_id,
        type_,
        name,
        description,
        cost,
        weight,
        main_ingredient,
        marge=None,
        date_last_used=None,
        is_using=1,
        is_mandatory=0  # Новый параметр
):
    if date_last_used is None:
        date_last_used = "2026-01-01 00:00:00"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO dishes (
            id, type, name, description, cost, weight,
            main_ingredient, marge, date_last_used, is_using, is_mandatory
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dish_id, type_, name, description, cost, weight,
        main_ingredient, marge, date_last_used, is_using, is_mandatory
    ))
    conn.commit()
    conn.close()


# ---------- UPDATE ----------
def update_dish(
        dish_id,
        type_=None,
        name=None,
        description=None,
        cost=None,
        weight=None,
        main_ingredient=None,
        marge=None,
        date_last_used=None,
        is_using=None,
        is_mandatory=None  # Новый параметр
):
    fields = []
    params = []

    if type_ is not None:
        fields.append("type = ?")
        params.append(type_)
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if cost is not None:
        fields.append("cost = ?")
        params.append(cost)
    if weight is not None:
        fields.append("weight = ?")
        params.append(weight)
    if main_ingredient is not None:
        fields.append("main_ingredient = ?")
        params.append(main_ingredient)
    if marge is not None:
        fields.append("marge = ?")
        params.append(marge)
    if date_last_used is not None:
        fields.append("date_last_used = ?")
        params.append(date_last_used)
    if is_using is not None:
        fields.append("is_using = ?")
        params.append(is_using)
    if is_mandatory is not None:  # Новое поле
        fields.append("is_mandatory = ?")
        params.append(is_mandatory)

    if not fields:
        return

    params.append(dish_id)

    conn = get_connection()
    cur = conn.cursor()
    sql = "UPDATE dishes SET " + ", ".join(fields) + " WHERE id = ?"
    cur.execute(sql, params)
    conn.commit()
    conn.close()


# ---------- DELETE ----------
def delete_dish(dish_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    conn.commit()
    conn.close()


# ---------- SELECT ALL ----------
def get_all_dishes(include_disabled=False):
    """Получить все блюда, можно включить неиспользуемые"""
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes")
    else:
        cur.execute("SELECT * FROM dishes WHERE is_using = 1")

    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- SEARCHES ----------
def search_by_name(name, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes WHERE name LIKE ?", (f"%{name}%",))
    else:
        cur.execute("SELECT * FROM dishes WHERE name LIKE ? AND is_using = 1", (f"%{name}%",))

    rows = cur.fetchall()
    conn.close()
    return rows


def search_by_main_ingredient(ingredient, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute(
            "SELECT * FROM dishes WHERE main_ingredient LIKE ?",
            (f"%{ingredient}%",)
        )
    else:
        cur.execute(
            "SELECT * FROM dishes WHERE main_ingredient LIKE ? AND is_using = 1",
            (f"%{ingredient}%",)
        )

    rows = cur.fetchall()
    conn.close()
    return rows


def search_by_type(type_, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes WHERE type = ?", (type_,))
    else:
        cur.execute("SELECT * FROM dishes WHERE type = ? AND is_using = 1", (type_,))

    rows = cur.fetchall()
    conn.close()
    return rows


def search_by_marge(min_marge=None, max_marge=None, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    base_sql = "SELECT * FROM dishes"
    where_clauses = []
    params = []

    if not include_disabled:
        where_clauses.append("is_using = 1")

    if min_marge is not None and max_marge is not None:
        where_clauses.append("marge BETWEEN ? AND ?")
        params.extend([min_marge, max_marge])
    elif min_marge is not None:
        where_clauses.append("marge >= ?")
        params.append(min_marge)
    elif max_marge is not None:
        where_clauses.append("marge <= ?")
        params.append(max_marge)
    else:
        where_clauses.append("marge IS NOT NULL")

    if where_clauses:
        base_sql += " WHERE " + " AND ".join(where_clauses)

    cur.execute(base_sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def search_by_date_last_used(from_date=None, to_date=None, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    base_sql = "SELECT * FROM dishes"
    where_clauses = []
    params = []

    if not include_disabled:
        where_clauses.append("is_using = 1")

    if from_date and to_date:
        where_clauses.append("date_last_used BETWEEN ? AND ?")
        params.extend([from_date, to_date])
    elif from_date:
        where_clauses.append("date_last_used >= ?")
        params.append(from_date)
    elif to_date:
        where_clauses.append("date_last_used <= ?")
        params.append(to_date)
    else:
        where_clauses.append("date_last_used IS NOT NULL")

    if where_clauses:
        base_sql += " WHERE " + " AND ".join(where_clauses)

    cur.execute(base_sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- КОМБИНИРОВАННЫЙ ПОИСК ----------
def search_dishes(
        name=None,
        main_ingredient=None,
        type_=None,
        min_marge=None,
        max_marge=None,
        from_date=None,
        to_date=None,
        is_using=None,
        is_mandatory=None,  # Новый параметр
        include_disabled=False,
        case_sensitive=False
):
    sql = "SELECT * FROM dishes WHERE 1=1"
    params = []

    if not include_disabled:
        sql += " AND is_using = 1"

    if is_using is not None:
        sql += " AND is_using = ?"
        params.append(is_using)

    if is_mandatory is not None:  # Новый фильтр
        sql += " AND is_mandatory = ?"
        params.append(is_mandatory)

    if name:
        if case_sensitive:
            # С учетом регистра
            sql += " AND name LIKE ?"
            params.append(f"%{name}%")
        else:
            # Без учета регистра - несколько вариантов для надежности
            sql += """ AND (
                    name LIKE ? COLLATE NOCASE OR
                    LOWER(name) LIKE LOWER(?) OR
                    UPPER(name) LIKE UPPER(?)
                )"""
            params.extend([f"%{name}%", f"%{name}%", f"%{name}%"])

    if main_ingredient:
        sql += " AND UPPER(main_ingredient) LIKE UPPER(?)"
        params.append(f"%{main_ingredient}%")

    if type_:
        sql += " AND UPPER(type) = UPPER(?)"
        params.append(type_)
    if min_marge is not None:
        sql += " AND marge >= ?"
        params.append(min_marge)
    if max_marge is not None:
        sql += " AND marge <= ?"
        params.append(max_marge)
    if from_date:
        sql += " AND date_last_used >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND date_last_used <= ?"
        params.append(to_date)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------- ПРОСТОЙ ПОИСК ПО НАЗВАНИЮ ----------
def search_dishes_by_name(
        search_text,
        include_disabled=False,
        exact_match=False,
        case_sensitive=False
):
    """
    Упрощенный поиск только по названию

    Args:
        search_text: текст для поиска
        exact_match: если True - точное совпадение
                    если False - частичное совпадение (содержит)
        case_sensitive: чувствительность к регистру
    """
    # Если пустой поиск - возвращаем всё или ничего
    if not search_text or not search_text.strip():
        if exact_match:
            return []
        else:
            return get_all_dishes(include_disabled)

    search_text = search_text.strip()

    if exact_match:
        # Точное совпадение
        if case_sensitive:
            sql = "SELECT * FROM dishes WHERE name = ?"
        else:
            # Для неточного регистра пробуем все варианты
            sql = """SELECT * FROM dishes WHERE 
                  (name = ? COLLATE NOCASE OR 
                   LOWER(name) = LOWER(?) OR 
                   UPPER(name) = UPPER(?))"""
            params = [search_text, search_text, search_text]
    else:
        # Частичное совпадение (содержит)
        if case_sensitive:
            sql = "SELECT * FROM dishes WHERE name LIKE ?"
            params = [f"%{search_text}%"]
        else:
            # Самый надежный вариант для SQLite с кириллицей
            sql = """SELECT * FROM dishes WHERE 
                  (name LIKE ? COLLATE NOCASE OR
                   name LIKE ? COLLATE NOCASE OR
                   name LIKE ? COLLATE NOCASE)"""
            params = [
                f"%{search_text}%",
                f"%{search_text.lower()}%",
                f"%{search_text.upper()}%"
            ]

    if not include_disabled:
        sql += " AND is_using = 1"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return rows


def normalize_text(text):
    """Приводит текст к максимально нормализованному виду"""
    if not text:
        return ""

    # 1. Приводим к строке
    text = str(text)

    # 2. Удаляем все лишние символы и пробелы
    text = ' '.join(text.split())  # Удаляем лишние пробелы

    # 3. Убираем знаки пунктуации для поиска
    # (но сохраняем их в оригинальном тексте)
    text_clean = re.sub(r'[^\w\s]', ' ', text)

    # 4. Приводим к NFKD форме и убираем диакритики (для английского)
    text_normalized = unicodedata.normalize('NFKD', text_clean)
    text_normalized = ''.join([c for c in text_normalized if not unicodedata.combining(c)])

    return text, text_clean, text_normalized


def ultra_search_dishes(
        search_text,
        include_disabled=False,
        min_similarity=0.5,
        use_regex=True
):
    """
    УЛЬТРА-НАДЕЖНЫЙ поиск блюд
    Использует 10+ методов для гарантированного нахождения
    """
    if not search_text:
        return get_all_dishes(include_disabled)

    search_text = search_text.strip()

    # Получаем ВСЕ блюда
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes")
    else:
        cur.execute("SELECT * FROM dishes WHERE is_using = 1")

    all_dishes = cur.fetchall()
    conn.close()

    # Подготовка поискового запроса
    search_original = search_text
    search_lower = search_text.lower()
    search_upper = search_text.upper()

    # Создаем РАЗНЫЕ варианты поискового запроса
    search_variants = [
        search_original,
        search_lower,
        search_upper,
        search_original.title(),
        search_original.capitalize(),
        search_original.replace('ё', 'е'),
        search_original.replace('е', 'ё'),
        search_original.replace('"', ''),
        search_original.replace("'", ''),
        search_original.replace('«', '').replace('»', ''),
    ]

    # Добавляем варианты без пробелов
    search_variants.extend([
        search_original.replace(' ', ''),
        search_lower.replace(' ', ''),
        search_upper.replace(' ', ''),
    ])

    # Регулярные выражения для поиска
    regex_patterns = []
    if use_regex:
        # Базовый паттерн
        base_pattern = re.escape(search_original)
        regex_patterns.extend([
            rf'(?i){base_pattern}',  # case-insensitive
            rf'{search_lower}',
            rf'{search_upper}',
            rf'{base_pattern.replace(" ", "s*")}',  # игнорируем пробелы
            rf'{re.escape(search_lower)}',
            rf'{re.escape(search_upper)}',
        ])

    # Функция для получения названия блюда
    def get_dish_name(dish):
        """Извлекает название блюда из кортежа"""
        # Порядок полей: id, type, name, description, cost, weight, main_ingredient, marge, date_last_used, is_using, is_mandatory
        if len(dish) > 2:
            name = dish[2]  # name находится по индексу 2
            if name and isinstance(name, str):
                return str(name)
        return ""

    results = []

    for dish in all_dishes:
        dish_name = get_dish_name(dish)
        if not dish_name:
            continue

        # Нормализуем название блюда
        dish_original, dish_clean, dish_normalized = normalize_text(dish_name)
        dish_lower = dish_original.lower()
        dish_upper = dish_original.upper()

        # МЕТОД 1: Простое прямое вхождение (основной)
        found = False
        score = 0

        # Проверяем ВСЕ варианты поиска
        for variant in search_variants:
            if variant and variant in dish_original:
                score = max(score, 100)
                found = True
                break
            if variant and variant in dish_lower:
                score = max(score, 90)
                found = True
                break
            if variant and variant in dish_upper:
                score = max(score, 90)
                found = True
                break

        # МЕТОД 2: Регулярные выражения
        if not found and use_regex:
            for pattern in regex_patterns:
                try:
                    if re.search(pattern, dish_original):
                        score = max(score, 85)
                        found = True
                        break
                except:
                    continue

        # МЕТОД 3: Поиск без учета пробелов и пунктуации
        if not found:
            search_no_spaces = search_original.replace(' ', '').lower()
            dish_no_spaces = dish_original.replace(' ', '').lower()

            if search_no_spaces in dish_no_spaces:
                score = max(score, 80)
                found = True

        # МЕТОД 4: Поиск слов по отдельности
        if not found:
            search_words = re.findall(r'\w+', search_original.lower())
            dish_words = re.findall(r'\w+', dish_original.lower())

            match_count = sum(1 for word in search_words if any(word in dw for dw in dish_words))
            if match_count >= len(search_words) * 0.7:  # 70% совпадение слов
                score = max(score, 70 + match_count * 10)
                found = True

        # МЕТОД 5: Fuzzy поиск (резервный)
        if not found:
            similarity = SequenceMatcher(None, search_lower, dish_lower).ratio()
            if similarity >= min_similarity:
                score = max(score, int(similarity * 100))
                found = True

        # МЕТОД 6: Поиск по транслитерации (если есть английские буквы)
        if not found and any(c.isascii() for c in search_original):
            # Простая транслитерация кириллицы
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
                'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
                'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
                'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
                'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
                'ш': 'sh', 'щ': 'shch', 'ы': 'y', 'э': 'e', 'ю': 'yu',
                'я': 'ya'
            }

            # Транслитерируем поиск
            search_translit = ''
            for char in search_lower:
                search_translit += translit_map.get(char, char)

            # Транслитерируем название блюда
            dish_translit = ''
            for char in dish_lower:
                dish_translit += translit_map.get(char, char)

            if search_translit in dish_translit:
                score = max(score, 60)
                found = True

        # Если нашли - добавляем в результаты
        if found and score > 0:
            results.append((dish, score))

    # Сортируем по релевантности
    results.sort(key=lambda x: x[1], reverse=True)

    # Отладочный вывод
    if results:
        print(f"\n🔍 УЛЬТРА-ПОИСК '{search_text}':")
        print(f"   Найдено: {len(results)} результатов")
        for i, (dish, score) in enumerate(results[:3]):
            dish_name = get_dish_name(dish)
            print(f"   {i + 1}. '{dish_name}' (score: {score})")

    return [dish for dish, score in results]

# ---------- ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_next_available_id():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT MAX(id) FROM dishes")
    max_id = cur.fetchone()[0]

    if max_id is None:
        return 1
    else:
        cur.execute("""
            WITH RECURSIVE seq(n) AS (
                SELECT 1
                UNION ALL
                SELECT n+1 FROM seq WHERE n < ?
            )
            SELECT seq.n FROM seq
            LEFT JOIN dishes ON seq.n = dishes.id
            WHERE dishes.id IS NULL
            ORDER BY seq.n
            LIMIT 1
        """, (max_id + 10,))

        gap_id = cur.fetchone()
        if gap_id:
            return gap_id[0]
        else:
            return max_id + 1


# ---------- ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ----------
def insert_dish_with_auto_id(type_, name, description, cost, weight, main_ingredient, marge, date_last_used=None):
    dish_id = get_next_available_id()
    if date_last_used is None:
        date_last_used = "2026-01-01 00:00:00"

    insert_dish(dish_id, type_, name, description, cost, weight, main_ingredient, marge, date_last_used, 1, 0)
    return dish_id


def search_by_status(is_using, include_disabled=False):
    conn = get_connection()
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes WHERE is_using = ?", (is_using,))
    else:
        cur.execute("SELECT * FROM dishes WHERE is_using = ? AND is_using = 1", (is_using,))

    rows = cur.fetchall()
    conn.close()
    return rows


def disable_dish(dish_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE dishes SET is_using = 0 WHERE id = ?", (dish_id,))

    conn.commit()
    conn.close()


def enable_dish(dish_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE dishes SET is_using = 1 WHERE id = ?", (dish_id,))

    conn.commit()
    conn.close()


def search_by_status_v2(status="active", date_filter=None):
    conn = get_connection()
    cur = conn.cursor()

    sql = "SELECT * FROM dishes WHERE 1=1"
    params = []

    if status == "active":
        sql += " AND is_using = 1"
    elif status == "inactive":
        sql += " AND is_using = 0"

    if date_filter:
        from_date, to_date = date_filter
        if from_date:
            sql += " AND date_last_used >= ?"
            params.append(from_date)
        if to_date:
            sql += " AND date_last_used <= ?"
            params.append(to_date)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return rows


def get_active_dishes_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM dishes WHERE is_using = 1")
    count = cur.fetchone()[0]

    conn.close()
    return count


def get_inactive_dishes_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM dishes WHERE is_using = 0")
    count = cur.fetchone()[0]

    conn.close()
    return count


def toggle_dish_status(dish_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_using FROM dishes WHERE id = ?", (dish_id,))
    result = cur.fetchone()

    if result is None:
        conn.close()
        raise ValueError(f"Блюдо с ID {dish_id} не найдено")

    current_status = result[0]
    new_status = 0 if current_status == 1 else 1

    cur.execute("UPDATE dishes SET is_using = ? WHERE id = ?", (new_status, dish_id))

    conn.commit()
    conn.close()

    return new_status


def get_dish_status(dish_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_using FROM dishes WHERE id = ?", (dish_id,))
    result = cur.fetchone()

    conn.close()

    return result[0] if result else None


def bulk_disable_dishes(dish_ids):
    if not dish_ids:
        return

    conn = get_connection()
    cur = conn.cursor()

    placeholders = ','.join(['?'] * len(dish_ids))
    sql = f"UPDATE dishes SET is_using = 0 WHERE id IN ({placeholders})"

    cur.execute(sql, dish_ids)
    conn.commit()
    conn.close()


def bulk_enable_dishes(dish_ids):
    if not dish_ids:
        return

    conn = get_connection()
    cur = conn.cursor()

    placeholders = ','.join(['?'] * len(dish_ids))
    sql = f"UPDATE dishes SET is_using = 1 WHERE id IN ({placeholders})"

    cur.execute(sql, dish_ids)
    conn.commit()
    conn.close()


def get_all_dishes_as_dicts(include_disabled=False):
    """Получить все блюда в виде словарей"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row  # Временно меняем фабрику
    cur = conn.cursor()

    if include_disabled:
        cur.execute("SELECT * FROM dishes")
    else:
        cur.execute("SELECT * FROM dishes WHERE is_using = 1")

    rows = cur.fetchall()
    conn.close()

    # Преобразуем Row в dict
    return [dict(row) for row in rows]


