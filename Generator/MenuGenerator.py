import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random
from collections import defaultdict


class MenuGenerator:
    def __init__(self, db_path: str, target_date: datetime = None):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.target_date = target_date or datetime.now()
        self.menu_date_str = self.target_date.strftime('%Y-%m-%d')

        # Целевое распределение по марже (зеркально FoodCost)
        self.target_distribution = {
            'ultra_high': 0.5,  # 50% - Маржа ≥70% (FoodCost ≤30%)
            'high': 0.2,  # 20% - Маржа 65-70% (FoodCost 30-35%)
            'medium': 0.2,  # 20% - Маржа 60-65% (FoodCost 35-40%)
            'low': 0.1  # 10% - Маржа <60% (FoodCost >40%)
        }

        # Словарь для хранения сгенерированного меню
        self.generated_menu = {
            'salads': [],
            'soups': [],
            'main_courses': [],
            'garnishes': [],
            'bakery': [],
            'drinks': []
        }

        # Счетчики для распределения по марже
        self.margin_counters = {
            'ultra_high': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'unknown': 0
        }

        # Общее количество необязательных блюд (для расчета процентов)
        self.non_mandatory_total = 0

    def get_row_value(self, row, field_name, default=None):
        """Безопасное получение значения из sqlite3.Row"""
        if isinstance(row, sqlite3.Row):
            try:
                return row[field_name]
            except (KeyError, IndexError):
                return default
        elif isinstance(row, dict) and field_name in row:
            return row[field_name]
        return default

    def calculate_margin_group(self, marge: float) -> str:
        """Определяет маржинальную группу на основе маржи"""
        if marge is None:
            return 'unknown'

        try:
            marge_value = float(marge)
            if marge_value >= 70:
                return 'ultra_high'  # Маржа ≥70%
            elif marge_value >= 65:
                return 'high'  # Маржа 65-70%
            elif marge_value >= 60:
                return 'medium'  # Маржа 60-65%
            else:
                return 'low'  # Маржа <60%
        except (ValueError, TypeError):
            return 'unknown'

    def get_needed_distribution(self, total_to_add: int) -> Dict[str, int]:
        """Рассчитывает сколько блюд каждой группы нужно добавить"""
        needed = {}

        for group, target_percent in self.target_distribution.items():
            current = self.margin_counters.get(group, 0)
            target_total = int((self.non_mandatory_total + total_to_add) * target_percent)
            needed_in_group = max(0, target_total - current)
            needed[group] = needed_in_group

        return needed

    def add_dish_to_menu(self, category: str, dish, is_mandatory: bool = False):
        """Добавляет блюдо в меню и обновляет счетчики распределения"""
        self.generated_menu[category].append(dish)

        # Обновляем счетчики только для необязательных блюд
        if not is_mandatory:
            self.non_mandatory_total += 1
            marge = self.get_row_value(dish, 'marge')
            margin_group = self.calculate_margin_group(marge)
            self.margin_counters[margin_group] += 1

    def get_available_dishes(self, dish_type: str, exclude_ids: List[int] = None,
                             min_days_since_use: int = 3, must_have_margin: bool = False,
                             category_filter: Optional[str] = None) -> List:
        """Получает доступные блюда с учетом даты последнего использования"""
        if exclude_ids is None:
            exclude_ids = []

        # Рассчитываем минимальную дату для использования
        min_date = (self.target_date - timedelta(days=min_days_since_use)).strftime('%Y-%m-%d')

        query = """
            SELECT * FROM dishes 
            WHERE type = ? 
            AND is_using = 1
        """
        params = [dish_type]

        # Фильтр по марже
        if must_have_margin:
            query += " AND marge IS NOT NULL"

        # Фильтр по категории (основному ингредиенту)
        if category_filter:
            if dish_type == 'Салат':
                query += " AND main_ingredient LIKE ?"
                params.append(f'%{category_filter}%')
            elif dish_type == 'Второе':
                # Для вторых блюд категории определяются по-разному
                if category_filter == 'Свинина':
                    query += " AND (name LIKE '%свин%' OR main_ingredient LIKE '%свин%')"
                elif category_filter == 'Говядина':
                    query += " AND (name LIKE '%говяд%' OR main_ingredient LIKE '%говяд%')"
                elif category_filter == 'Рыба':
                    query += " AND (name LIKE '%рыб%' OR main_ingredient LIKE '%рыб%' OR name LIKE '%горбуш%')"
                elif category_filter == 'Курица':
                    query += " AND (name LIKE '%кури%' OR main_ingredient LIKE '%кури%')"
                elif category_filter == 'Другое':
                    query += " AND (name NOT LIKE '%свин%' AND name NOT LIKE '%говяд%' "
                    query += " AND name NOT LIKE '%рыб%' AND name NOT LIKE '%кури%')"

        # Исключаем ID
        if exclude_ids:
            placeholders = ','.join(['?' for _ in exclude_ids])
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        # Правило дней для необязательных блюд
        query += " AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)"
        params.append(min_date)

        # Сортируем: сначала те, которые давно не использовались, потом по марже
        query += " ORDER BY date_last_used ASC, marge DESC, RANDOM()"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_dish_by_pattern(self, dish_type: str, pattern: str, exclude_ids: List[int] = None) -> List:
        """Получить блюдо по паттерну названия"""
        if exclude_ids is None:
            exclude_ids = []

        query = """
            SELECT * FROM dishes 
            WHERE type = ? 
            AND is_using = 1
            AND (LOWER(name) LIKE LOWER(?) OR LOWER(main_ingredient) LIKE LOWER(?))
        """
        params = [dish_type, f'%{pattern}%', f'%{pattern}%']

        if exclude_ids:
            placeholders = ','.join(['?' for _ in exclude_ids])
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        # Правило 3 дней
        min_date = (self.target_date - timedelta(days=3)).strftime('%Y-%m-%d')
        query += " AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)"
        params.append(min_date)

        query += " ORDER BY date_last_used ASC, RANDOM() LIMIT 1"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()

        # Если не нашли с учетом правила 3 дней, ищем любые
        if not result:
            query2 = """
                SELECT * FROM dishes 
                WHERE type = ? 
                AND is_using = 1
                AND (LOWER(name) LIKE LOWER(?) OR LOWER(main_ingredient) LIKE LOWER(?))
            """
            params2 = [dish_type, f'%{pattern}%', f'%{pattern}%']

            if exclude_ids:
                placeholders = ','.join(['?' for _ in exclude_ids])
                query2 += f" AND id NOT IN ({placeholders})"
                params2.extend(exclude_ids)

            query2 += " ORDER BY RANDOM() LIMIT 1"

            cursor.execute(query2, params2)
            result = cursor.fetchone()

        return [result] if result else []

    def get_mandatory_dishes(self, dish_type: str, exclude_ids: List[int] = None) -> List:
        """Получает обязательные блюда по типу"""
        if exclude_ids is None:
            exclude_ids = []

        query = """
            SELECT * FROM dishes 
            WHERE type = ? 
            AND is_using = 1
            AND is_mandatory = 1
        """
        params = [dish_type]

        if exclude_ids:
            placeholders = ','.join(['?' for _ in exclude_ids])
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        query += " ORDER BY RANDOM()"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def should_include_colbasa_salad(self) -> bool:
        """Определяет, нужно ли сегодня включать салат с колбасой"""
        # Проверяем когда последний раз использовался салат с колбасой
        query = """
            SELECT MAX(date_last_used) as last_used 
            FROM dishes 
            WHERE type = 'Салат' 
            AND is_using = 1
            AND main_ingredient LIKE '%Колбаса%'
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()

        if not result or not result['last_used']:
            return True  # Никогда не использовался или нет записей

        try:
            last_used = datetime.strptime(result['last_used'], '%Y-%m-%d').date()
            days_diff = (self.target_date.date() - last_used).days
            return days_diff >= 2  # Через день (минимум 2 дня разницы)
        except (ValueError, KeyError):
            return True

    def should_include_meat_salad(self) -> bool:
        """Определяет, нужно ли сегодня мясо или рыбу в салатах"""
        # Проверяем когда последний раз использовались мясо и рыба
        query = """
            SELECT main_ingredient, MAX(date_last_used) as last_used 
            FROM dishes 
            WHERE type = 'Салат' 
            AND is_using = 1
            AND (main_ingredient = 'Мясо' OR main_ingredient = 'Рыба и морепродукты')
            GROUP BY main_ingredient
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()

        meat_last_used = None
        fish_last_used = None

        for row in results:
            ingredient = self.get_row_value(row, 'main_ingredient')
            last_used_str = self.get_row_value(row, 'last_used')

            if last_used_str:
                try:
                    last_used = datetime.strptime(last_used_str, '%Y-%m-%d').date()
                    if ingredient == 'Мясо':
                        meat_last_used = last_used
                    elif ingredient == 'Рыба и морепродукты':
                        fish_last_used = last_used
                except ValueError:
                    continue

        # Если один из них никогда не использовался, выбираем его
        if meat_last_used is None:
            return True  # Мясо
        if fish_last_used is None:
            return False  # Рыба

        # Иначе выбираем тот, который использовался раньше
        return meat_last_used <= fish_last_used

    def should_include_pancakes(self) -> bool:
        """Определяет, нужно ли сегодня блины или драники"""
        # Проверяем когда последний раз использовались блины и драники
        query = """
            SELECT name, MAX(date_last_used) as last_used 
            FROM dishes 
            WHERE type = 'Выпечка' 
            AND is_using = 1
            AND (LOWER(name) LIKE '%блин%' OR LOWER(name) LIKE '%драник%')
            GROUP BY CASE 
                WHEN LOWER(name) LIKE '%блин%' THEN 'блины'
                WHEN LOWER(name) LIKE '%драник%' THEN 'драники'
            END
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()

        pancakes_last_used = None
        draniki_last_used = None

        for row in results:
            name = self.get_row_value(row, 'name', '').lower()
            last_used_str = self.get_row_value(row, 'last_used')

            if last_used_str:
                try:
                    last_used = datetime.strptime(last_used_str, '%Y-%m-%d').date()
                    if 'блин' in name:
                        pancakes_last_used = last_used
                    elif 'драник' in name:
                        draniki_last_used = last_used
                except ValueError:
                    continue

        # Если один из них никогда не использовался, выбираем его
        if pancakes_last_used is None:
            return True  # Блины
        if draniki_last_used is None:
            return False  # Драники

        # Иначе выбираем тот, который использовался раньше
        return pancakes_last_used <= draniki_last_used

    def generate_salads(self) -> List:
        """Генерирует 5 салатов"""
        print("Генерация салатов...")
        selected = []
        used_ids = []

        # 1. Обязательные салаты по флагу
        mandatory_salads = self.get_mandatory_dishes('Салат', used_ids)
        for salad in mandatory_salads:
            selected.append(salad)
            used_ids.append(self.get_row_value(salad, 'id'))
            self.add_dish_to_menu('salads', salad, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(salad, 'name')}")

        # 2. Курица (минимум 1)
        chicken_needed = 1
        chicken_count = 0

        # Проверяем сколько уже есть курицы
        for salad in selected:
            if self.get_row_value(salad, 'main_ingredient') == 'Курица':
                chicken_count += 1

        while chicken_count < chicken_needed and len(selected) < 5:
            chicken_salads = self.get_available_dishes('Салат', used_ids, 3, False, 'Курица')
            if chicken_salads:
                salad = chicken_salads[0]
                selected.append(salad)
                used_ids.append(self.get_row_value(salad, 'id'))
                self.add_dish_to_menu('salads', salad, is_mandatory=True)
                chicken_count += 1
                print(f"  ✓ Курица: {self.get_row_value(salad, 'name')}")
            else:
                break

        # 3. Овощи (минимум 2)
        vegetables_needed = 2
        vegetables_count = 0

        # Проверяем сколько уже есть овощей
        for salad in selected:
            if 'Овощи' in str(self.get_row_value(salad, 'main_ingredient', '')):
                vegetables_count += 1

        while vegetables_count < vegetables_needed and len(selected) < 5:
            veg_salads = self.get_available_dishes('Салат', used_ids, 3, False, 'Овощи')
            if veg_salads:
                salad = veg_salads[0]
                selected.append(salad)
                used_ids.append(self.get_row_value(salad, 'id'))
                self.add_dish_to_menu('salads', salad, is_mandatory=True)
                vegetables_count += 1
                print(f"  ✓ Овощи: {self.get_row_value(salad, 'name')}")
            else:
                break

        # 4. Мясо или рыба (чередуем по дате использования)
        if len(selected) < 5:
            need_meat = self.should_include_meat_salad()
            category = 'Мясо' if need_meat else 'Рыба и морепродукты'

            meat_fish_salads = self.get_available_dishes('Салат', used_ids, 3, False, category)
            if meat_fish_salads:
                salad = meat_fish_salads[0]
                selected.append(salad)
                used_ids.append(self.get_row_value(salad, 'id'))
                self.add_dish_to_menu('salads', salad, is_mandatory=True)
                print(f"  ✓ {category}: {self.get_row_value(salad, 'name')}")

        # 5. Колбаса (через день по дате использования)
        if len(selected) < 5 and self.should_include_colbasa_salad():
            colbasa_salads = self.get_available_dishes('Салат', used_ids, 3, False, 'Колбаса')
            if colbasa_salads:
                salad = colbasa_salads[0]
                selected.append(salad)
                used_ids.append(self.get_row_value(salad, 'id'))
                self.add_dish_to_menu('salads', salad, is_mandatory=True)
                print(f"  ✓ Колбаса: {self.get_row_value(salad, 'name')}")

        # 6. Добираем до 5 с учетом распределения по марже
        if len(selected) < 5:
            needed = 5 - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= 5:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Салат' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge <= ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 1
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('salads', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")
                    else:
                        break

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < 5:
                remaining_needed = 5 - len(selected)
                available = self.get_available_dishes('Салат', used_ids, 3, False)

                for i in range(min(remaining_needed, len(available))):
                    salad = available[i]
                    selected.append(salad)
                    used_ids.append(self.get_row_value(salad, 'id'))
                    self.add_dish_to_menu('salads', salad, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(salad, 'name')}")

        print(f"  Итого салатов: {len(selected)}")
        return selected[:5]

    def generate_soups(self) -> List:
        """Генерирует 3 супа"""
        print("Генерация супов...")
        selected = []
        used_ids = []

        # 1. Суп Лапша каждый день
        noodle_soups = self.get_dish_by_pattern('Первое', 'Лапша', used_ids)
        if noodle_soups:
            soup = noodle_soups[0]
            selected.append(soup)
            used_ids.append(self.get_row_value(soup, 'id'))
            self.add_dish_to_menu('soups', soup, is_mandatory=True)
            print(f"  ★ Суп Лапша: {self.get_row_value(soup, 'name')}")

        # 2. Обязательные супы по флагу
        mandatory_soups = self.get_mandatory_dishes('Первое', used_ids)
        for soup in mandatory_soups:
            selected.append(soup)
            used_ids.append(self.get_row_value(soup, 'id'))
            self.add_dish_to_menu('soups', soup, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(soup, 'name')}")

        # 3. Добираем до 3 с учетом распределения по марже
        if len(selected) < 3:
            needed = 3 - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= 3:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Первое' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge <= ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 1
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('soups', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < 3:
                remaining_needed = 3 - len(selected)
                available = self.get_available_dishes('Первое', used_ids, 3, False)

                for i in range(min(remaining_needed, len(available))):
                    soup = available[i]
                    selected.append(soup)
                    used_ids.append(self.get_row_value(soup, 'id'))
                    self.add_dish_to_menu('soups', soup, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(soup, 'name')}")

        print(f"  Итого супов: {len(selected)}")
        return selected[:3]

    def generate_main_courses(self) -> List:
        """Генерирует 9-10 вторых блюд с улучшенным алгоритмом"""
        print("Генерация вторых блюд...")
        selected = []
        used_ids = []
        target_count = random.randint(9, 10)

        # 1. Котлета мясная каждый день
        cutlet_dishes = self.get_dish_by_pattern('Второе', 'котлета мясная', used_ids)
        if cutlet_dishes:
            dish = cutlet_dishes[0]
            selected.append(dish)
            used_ids.append(self.get_row_value(dish, 'id'))
            self.add_dish_to_menu('main_courses', dish, is_mandatory=True)
            print(f"  ★ Котлета мясная: {self.get_row_value(dish, 'name')}")

        # 2. Блюдо с горбушей каждый день (случайный выбор из доступных)
        pink_salmon_dishes = self.get_dishes_by_pattern_list('Второе', 'орбуш', used_ids)

        # Также ищем по основному ингредиенту
        query = """
            SELECT * FROM dishes 
            WHERE type = 'Второе' 
            AND is_using = 1
            AND (main_ingredient LIKE '%горбуш%' OR main_ingredient LIKE '%рыб%')
            AND id NOT IN ({})
            ORDER BY RANDOM()
            LIMIT 10
        """.format(','.join(['?' for _ in used_ids]))

        cursor = self.conn.cursor()
        cursor.execute(query, used_ids)
        additional_salmon_dishes = cursor.fetchall()

        # Объединяем все блюда с горбушей
        all_salmon_dishes = list(pink_salmon_dishes) + list(additional_salmon_dishes)

        if all_salmon_dishes:
            # Сортируем по дате использования (старые вперед)
            all_salmon_dishes.sort(key=lambda x: self.get_row_value(x, 'date_last_used', '2000-01-01'))

            # Фильтруем те, что не использовались в последние 3 дня
            three_days_ago = (self.target_date - timedelta(days=3)).strftime('%Y-%m-%d')
            fresh_salmon_dishes = [
                d for d in all_salmon_dishes
                if self.get_row_value(d, 'date_last_used', '2000-01-01') < three_days_ago
            ]

            # Выбираем самое старое из тех, что не использовались 3 дня, или самое старое вообще
            dish = fresh_salmon_dishes[0] if fresh_salmon_dishes else all_salmon_dishes[0]

            selected.append(dish)
            used_ids.append(self.get_row_value(dish, 'id'))
            self.add_dish_to_menu('main_courses', dish, is_mandatory=True)
            print(f"  ★ Блюдо с горбушей: {self.get_row_value(dish, 'name')}")

        # 3. Поджарка или гуляш каждый день (случайный выбор)
        # Ищем поджарку
        podzharka_dishes = self.get_dishes_by_pattern_list('Второе', 'оджарка', used_ids)

        # Ищем гуляш
        goulash_dishes = self.get_dishes_by_pattern_list('Второе', 'уляш', used_ids)

        # Собираем все подходящие блюда
        meat_dishes = []
        if podzharka_dishes:
            meat_dishes.extend(podzharka_dishes)
        if goulash_dishes:
            meat_dishes.extend(goulash_dishes)

        # Также ищем по основному ингредиенту (свинина или говядина)
        query = """
            SELECT * FROM dishes 
            WHERE type = 'Второе' 
            AND is_using = 1
            AND (name LIKE '%уляш%' OR name LIKE '%оджарк%' 
                 OR main_ingredient IN ('Свинина', 'Говядина'))
            AND id NOT IN ({})
            AND (date_last_used IS NULL OR date_last_used < ?)
            ORDER BY RANDOM()
            LIMIT 10
        """.format(','.join(['?' for _ in used_ids]))

        cursor = self.conn.cursor()
        params = used_ids.copy()
        params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))
        cursor.execute(query, params)
        additional_meat_dishes = cursor.fetchall()

        meat_dishes.extend(additional_meat_dishes)

        if meat_dishes:
            # Удаляем дубликаты по ID
            unique_meat_dishes = []
            seen_ids = set()
            for dish in meat_dishes:
                dish_id = self.get_row_value(dish, 'id')
                if dish_id not in seen_ids:
                    seen_ids.add(dish_id)
                    unique_meat_dishes.append(dish)

            # Сортируем по дате использования
            unique_meat_dishes.sort(key=lambda x: self.get_row_value(x, 'date_last_used', '2000-01-01'))

            # Фильтруем те, что не использовались в последние 3 дня
            fresh_meat_dishes = [
                d for d in unique_meat_dishes
                if self.get_row_value(d, 'date_last_used', '2000-01-01') < three_days_ago
            ]

            # Выбираем самое старое из тех, что не использовались 3 дня, или самое старое вообще
            dish = fresh_meat_dishes[0] if fresh_meat_dishes else unique_meat_dishes[0]

            selected.append(dish)
            used_ids.append(self.get_row_value(dish, 'id'))
            self.add_dish_to_menu('main_courses', dish, is_mandatory=True)
            print(f"  ★ Поджарка/Гуляш: {self.get_row_value(dish, 'name')}")

        # 4. Обязательные вторые блюда по флагу
        mandatory_courses = self.get_mandatory_dishes('Второе', used_ids)
        for course in mandatory_courses:
            selected.append(course)
            used_ids.append(self.get_row_value(course, 'id'))
            self.add_dish_to_menu('main_courses', course, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(course, 'name')}")

        # 5. КАТЕГОРИИ: В каждой категории ≥ 1
        categories = ['Свинина', 'Говядина', 'Курица', 'Другое']

        # Для каждой категории находим блюдо, которое не использовалось дольше всех
        for category in categories:
            if len(selected) >= target_count:
                break

            if category == 'Свинина':
                query = """
                    SELECT * FROM dishes 
                    WHERE type = 'Второе' 
                    AND is_using = 1
                    AND main_ingredient = 'Свинина'
                    AND id NOT IN ({})
                    AND (date_last_used IS NULL OR date_last_used < ?)
                    ORDER BY date_last_used ASC, RANDOM()
                    LIMIT 5
                """.format(','.join(['?' for _ in used_ids]))
            elif category == 'Говядина':
                query = """
                    SELECT * FROM dishes 
                    WHERE type = 'Второе' 
                    AND is_using = 1
                    AND main_ingredient = 'Говядина'
                    AND id NOT IN ({})
                    AND (date_last_used IS NULL OR date_last_used < ?)
                    ORDER BY date_last_used ASC, RANDOM()
                    LIMIT 5
                """.format(','.join(['?' for _ in used_ids]))
            elif category == 'Курица':
                query = """
                    SELECT * FROM dishes 
                    WHERE type = 'Второе' 
                    AND is_using = 1
                    AND main_ingredient = 'Курица'
                    AND id NOT IN ({})
                    AND (date_last_used IS NULL OR date_last_used < ?)
                    ORDER BY date_last_used ASC, RANDOM()
                    LIMIT 5
                """.format(','.join(['?' for _ in used_ids]))
            elif category == 'Другое':
                query = """
                    SELECT * FROM dishes 
                    WHERE type = 'Второе' 
                    AND is_using = 1
                    AND (main_ingredient = 'Другое' OR main_ingredient IS NULL OR main_ingredient = '')
                    AND id NOT IN ({})
                    AND (date_last_used IS NULL OR date_last_used < ?)
                    ORDER BY date_last_used ASC, RANDOM()
                    LIMIT 5
                """.format(','.join(['?' for _ in used_ids]))

            cursor = self.conn.cursor()
            params = used_ids.copy()
            params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))
            cursor.execute(query, params)
            category_dishes = cursor.fetchall()

            if category_dishes:
                # Берем самое "старое" блюдо
                dish = category_dishes[0]
                selected.append(dish)
                used_ids.append(self.get_row_value(dish, 'id'))
                self.add_dish_to_menu('main_courses', dish, is_mandatory=True)
                print(f"  ✓ {category}: {self.get_row_value(dish, 'name')}")
            else:
                # Если не нашли по правилу 3 дней, ищем любые
                if category == 'Свинина':
                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Второе' 
                        AND is_using = 1
                        AND main_ingredient = 'Свинина'
                        AND id NOT IN ({})
                        ORDER BY RANDOM()
                        LIMIT 5
                    """.format(','.join(['?' for _ in used_ids]))
                elif category == 'Говядина':
                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Второе' 
                        AND is_using = 1
                        AND main_ingredient = 'Говядина'
                        AND id NOT IN ({})
                        ORDER BY RANDOM()
                        LIMIT 5
                    """.format(','.join(['?' for _ in used_ids]))
                elif category == 'Курица':
                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Второе' 
                        AND is_using = 1
                        AND main_ingredient = 'Курица'
                        AND id NOT IN ({})
                        ORDER BY RANDOM()
                        LIMIT 5
                    """.format(','.join(['?' for _ in used_ids]))
                elif category == 'Другое':
                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Второе' 
                        AND is_using = 1
                        AND (main_ingredient = 'Другое' OR main_ingredient IS NULL OR main_ingredient = '')
                        AND id NOT IN ({})
                        ORDER BY RANDOM()
                        LIMIT 5
                    """.format(','.join(['?' for _ in used_ids]))

                cursor.execute(query, used_ids)
                category_dishes = cursor.fetchall()

                if category_dishes:
                    dish = category_dishes[0]
                    selected.append(dish)
                    used_ids.append(self.get_row_value(dish, 'id'))
                    self.add_dish_to_menu('main_courses', dish, is_mandatory=True)
                    print(f"  ✓ {category} (любое): {self.get_row_value(dish, 'name')}")

        # 6. Добираем до target_count с учетом распределения по марже
        if len(selected) < target_count:
            needed = target_count - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= target_count:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Второе' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge < ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ?)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 5
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('main_courses', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")
                    else:
                        # Если не нашли блюдо этой группы, пробуем найти без ограничения по дате
                        query = """
                            SELECT * FROM dishes 
                            WHERE type = 'Второе' 
                            AND is_using = 1
                            AND marge IS NOT NULL
                            AND marge >= ?
                            AND marge < ?
                            AND id NOT IN ({})
                            ORDER BY RANDOM()
                            LIMIT 5
                        """.format(','.join(['?' for _ in used_ids]))

                        params = [min_margin, max_margin]
                        params.extend(used_ids)

                        cursor.execute(query, params)
                        result = cursor.fetchone()

                        if result:
                            selected.append(result)
                            used_ids.append(self.get_row_value(result, 'id'))
                            self.add_dish_to_menu('main_courses', result, is_mandatory=False)
                            needed -= 1

                            margin = self.get_row_value(result, 'marge')
                            group_name = {
                                'ultra_high': 'СВЕРХмарж',
                                'high': 'ВЫСОКОмарж',
                                'medium': 'СРЕДНЕмарж',
                                'low': 'НИЗКОмарж'
                            }.get(group, 'неизвестно')
                            print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < target_count:
                remaining_needed = target_count - len(selected)

                # Ищем любые доступные блюда, которые не использовались 3 дня
                query = """
                    SELECT * FROM dishes 
                    WHERE type = 'Второе' 
                    AND is_using = 1
                    AND id NOT IN ({})
                    AND (date_last_used IS NULL OR date_last_used < ?)
                    ORDER BY RANDOM()
                    LIMIT ?
                """.format(','.join(['?' for _ in used_ids]))

                cursor = self.conn.cursor()
                params = used_ids.copy()
                params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))
                params.append(remaining_needed * 2)  # Берем немного больше на случай дубликатов

                cursor.execute(query, params)
                available = cursor.fetchall()

                for i in range(min(remaining_needed, len(available))):
                    course = available[i]
                    selected.append(course)
                    used_ids.append(self.get_row_value(course, 'id'))
                    self.add_dish_to_menu('main_courses', course, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(course, 'name')}")

        print(f"  Итого вторых блюд: {len(selected)}")
        return selected[:target_count]

    def get_dishes_by_pattern_list(self, dish_type: str, pattern: str, exclude_ids: List[int] = None) -> List:
        """Получить список блюд по паттерну названия"""
        if exclude_ids is None:
            exclude_ids = []

        query = """
            SELECT * FROM dishes 
            WHERE type = ? 
            AND is_using = 1
            AND (LOWER(name) LIKE LOWER(?) OR LOWER(main_ingredient) LIKE LOWER(?))
        """
        params = [dish_type, f'%{pattern}%', f'%{pattern}%']

        if exclude_ids:
            placeholders = ','.join(['?' for _ in exclude_ids])
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        # Правило 3 дней
        min_date = (self.target_date - timedelta(days=3)).strftime('%Y-%m-%d')
        query += " AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)"
        params.append(min_date)

        query += " ORDER BY date_last_used ASC, RANDOM()"

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        dishes = cursor.fetchall()

        # Если не нашли с учетом правила 3 дней, ищем любые
        if not dishes:
            query2 = """
                SELECT * FROM dishes 
                WHERE type = ? 
                AND is_using = 1
                AND (LOWER(name) LIKE LOWER(?) OR LOWER(main_ingredient) LIKE LOWER(?))
            """
            params2 = [dish_type, f'%{pattern}%', f'%{pattern}%']

            if exclude_ids:
                placeholders = ','.join(['?' for _ in exclude_ids])
                query2 += f" AND id NOT IN ({placeholders})"
                params2.extend(exclude_ids)

            query2 += " ORDER BY RANDOM()"

            cursor.execute(query2, params2)
            dishes = cursor.fetchall()

        return dishes

    def generate_garnishes(self) -> List:
        """Генерирует 5 гарниров"""
        print("Генерация гарниров...")
        selected = []
        used_ids = []

        # 1. Пюре картофельное обязательно каждый день
        mashed_potato_dishes = self.get_dish_by_pattern('Гарнир', 'пюре', used_ids)
        if mashed_potato_dishes:
            dish = mashed_potato_dishes[0]
            selected.append(dish)
            used_ids.append(self.get_row_value(dish, 'id'))
            self.add_dish_to_menu('garnishes', dish, is_mandatory=True)
            print(f"  ★ Пюре картофельное: {self.get_row_value(dish, 'name')}")

        # 2. Обязательные гарниры по флагу
        mandatory_garnishes = self.get_mandatory_dishes('Гарнир', used_ids)
        for garnish in mandatory_garnishes:
            selected.append(garnish)
            used_ids.append(self.get_row_value(garnish, 'id'))
            self.add_dish_to_menu('garnishes', garnish, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(garnish, 'name')}")

        # 3. Добираем до 5 с учетом распределения по марже
        if len(selected) < 5:
            needed = 5 - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= 5:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Гарнир' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge <= ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 1
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('garnishes', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < 5:
                remaining_needed = 5 - len(selected)
                available = self.get_available_dishes('Гарнир', used_ids, 3, False)

                for i in range(min(remaining_needed, len(available))):
                    garnish = available[i]
                    selected.append(garnish)
                    used_ids.append(self.get_row_value(garnish, 'id'))
                    self.add_dish_to_menu('garnishes', garnish, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(garnish, 'name')}")

        print(f"  Итого гарниров: {len(selected)}")
        return selected[:5]

    def generate_bakery(self) -> List:
        """Генерирует 9 видов выпечки"""
        print("Генерация выпечки...")
        selected = []
        used_ids = []

        # 1. Хлеб каждый день обязательно
        bread_dishes = self.get_dish_by_pattern('Выпечка', 'хлеб', used_ids)
        if bread_dishes:
            dish = bread_dishes[0]
            selected.append(dish)
            used_ids.append(self.get_row_value(dish, 'id'))
            self.add_dish_to_menu('bakery', dish, is_mandatory=True)
            print(f"  ★ Хлеб: {self.get_row_value(dish, 'name')}")

        # 2. Два вида пирожков должны быть каждый день
        pie_dishes = self.get_dish_by_pattern('Выпечка', 'пирож', used_ids)
        pies_added = 0
        for pie in pie_dishes:
            if pies_added >= 2:
                break
            selected.append(pie)
            used_ids.append(self.get_row_value(pie, 'id'))
            self.add_dish_to_menu('bakery', pie, is_mandatory=True)
            pies_added += 1
            print(f"  ★ Пирожок: {self.get_row_value(pie, 'name')}")

        # 3. Блины или драники (чередуем по дате использования)
        need_pancakes = self.should_include_pancakes()
        pattern = 'блин' if need_pancakes else 'драник'

        pancake_dishes = self.get_dish_by_pattern('Выпечка', pattern, used_ids)
        if pancake_dishes:
            pancake = pancake_dishes[0]
            selected.append(pancake)
            used_ids.append(self.get_row_value(pancake, 'id'))
            self.add_dish_to_menu('bakery', pancake, is_mandatory=True)
            print(f"  ★ {'Блины' if need_pancakes else 'Драники'}: {self.get_row_value(pancake, 'name')}")

        # 4. Обязательная выпечка по флагу
        mandatory_bakery = self.get_mandatory_dishes('Выпечка', used_ids)
        for bakery in mandatory_bakery:
            selected.append(bakery)
            used_ids.append(self.get_row_value(bakery, 'id'))
            self.add_dish_to_menu('bakery', bakery, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(bakery, 'name')}")

        # 5. Добираем до 9 с учетом распределения по марже
        if len(selected) < 9:
            needed = 9 - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= 9:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Выпечка' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge <= ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 1
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('bakery', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < 9:
                remaining_needed = 9 - len(selected)
                available = self.get_available_dishes('Выпечка', used_ids, 3, False)

                for i in range(min(remaining_needed, len(available))):
                    bakery = available[i]
                    selected.append(bakery)
                    used_ids.append(self.get_row_value(bakery, 'id'))
                    self.add_dish_to_menu('bakery', bakery, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(bakery, 'name')}")

        print(f"  Итого выпечки: {len(selected)}")
        return selected[:9]

    def generate_drinks(self) -> List:
        """Генерирует 10 напитков"""
        print("Генерация напитков...")
        selected = []
        used_ids = []
        target_count = 10

        # 1. Обязательные напитки по флагу
        mandatory_drinks = self.get_mandatory_dishes('Напиток', used_ids)
        for drink in mandatory_drinks:
            selected.append(drink)
            used_ids.append(self.get_row_value(drink, 'id'))
            self.add_dish_to_menu('drinks', drink, is_mandatory=True)
            print(f"  ★ Обязательный: {self.get_row_value(drink, 'name')}")

        # 2. Добираем до target_count с учетом распределения по марже
        if len(selected) < target_count:
            needed = target_count - len(selected)

            # Рассчитываем сколько блюд каждой маржинальной группы нужно
            distribution_needed = self.get_needed_distribution(needed)

            # Пробуем добавить по целевым группам
            for group, count in distribution_needed.items():
                if count <= 0 or needed <= 0:
                    continue

                # Получаем диапазон маржи для группы
                margin_ranges = {
                    'ultra_high': (70, 100),
                    'high': (65, 70),
                    'medium': (60, 65),
                    'low': (0, 60)
                }

                min_margin, max_margin = margin_ranges.get(group, (0, 100))

                for _ in range(count):
                    if needed <= 0 or len(selected) >= target_count:
                        break

                    query = """
                        SELECT * FROM dishes 
                        WHERE type = 'Напиток' 
                        AND is_using = 1
                        AND marge IS NOT NULL
                        AND marge >= ?
                        AND marge <= ?
                        AND id NOT IN ({})
                        AND (date_last_used IS NULL OR date_last_used < ? OR is_mandatory = 1)
                        ORDER BY date_last_used ASC, RANDOM()
                        LIMIT 1
                    """.format(','.join(['?' for _ in used_ids]))

                    params = [min_margin, max_margin]
                    params.extend(used_ids)
                    params.append((self.target_date - timedelta(days=3)).strftime('%Y-%m-%d'))

                    cursor = self.conn.cursor()
                    cursor.execute(query, params)
                    result = cursor.fetchone()

                    if result:
                        selected.append(result)
                        used_ids.append(self.get_row_value(result, 'id'))
                        self.add_dish_to_menu('drinks', result, is_mandatory=False)
                        needed -= 1

                        margin = self.get_row_value(result, 'marge')
                        group_name = {
                            'ultra_high': 'СВЕРХмарж',
                            'high': 'ВЫСОКОмарж',
                            'medium': 'СРЕДНЕмарж',
                            'low': 'НИЗКОмарж'
                        }.get(group, 'неизвестно')
                        print(f"  📊 {group_name} ({margin}%): {self.get_row_value(result, 'name')}")

            # Если все еще не хватает, добавляем любые доступные
            if len(selected) < target_count:
                remaining_needed = target_count - len(selected)
                available = self.get_available_dishes('Напиток', used_ids, 3, False)

                for i in range(min(remaining_needed, len(available))):
                    drink = available[i]
                    selected.append(drink)
                    used_ids.append(self.get_row_value(drink, 'id'))
                    self.add_dish_to_menu('drinks', drink, is_mandatory=False)
                    print(f"  ✓ Любой доступный: {self.get_row_value(drink, 'name')}")

        print(f"  Итого напитков: {len(selected)}")
        return selected[:target_count]

    def generate_full_menu(self) -> Dict:
        """Генерирует полное меню"""
        print("\n" + "=" * 60)
        print(f"ГЕНЕРАЦИЯ МЕНЮ НА {self.menu_date_str}")
        print("Целевое распределение по марже:")
        print("  • Сверхмаржинальные (≥70%): 50%")
        print("  • Высокомаржинальные (65-70%): 20%")
        print("  • Среднемаржинальные (60-65%): 20%")
        print("  • Низкомаржинальные (<60%): 10%")
        print("=" * 60)

        # Сбрасываем счетчики
        self.margin_counters = {k: 0 for k in self.margin_counters}
        self.non_mandatory_total = 0

        # Генерируем каждую категорию
        self.generated_menu['salads'] = self.generate_salads()
        self.generated_menu['soups'] = self.generate_soups()
        self.generated_menu['main_courses'] = self.generate_main_courses()
        self.generated_menu['garnishes'] = self.generate_garnishes()
        self.generated_menu['bakery'] = self.generate_bakery()
        self.generated_menu['drinks'] = self.generate_drinks()

        # Выводим финальную статистику распределения
        self.print_final_distribution()

        return self.generated_menu

    def print_final_distribution(self):
        """Выводит финальную статистику распределения"""
        print("\n" + "=" * 60)
        print("ФИНАЛЬНОЕ РАСПРЕДЕЛЕНИЕ ПО МАРЖЕ:")
        print("=" * 60)

        if self.non_mandatory_total == 0:
            print("Нет необязательных блюд для анализа распределения")
            return

        print(f"Всего необязательных блюд: {self.non_mandatory_total}")
        print()

        group_names = {
            'ultra_high': 'Сверхмаржинальные (≥70%)',
            'high': 'Высокомаржинальные (65-70%)',
            'medium': 'Среднемаржинальные (60-65%)',
            'low': 'Низкомаржинальные (<60%)',
            'unknown': 'С неизвестной маржой'
        }

        total_percent = 0
        for group in ['ultra_high', 'high', 'medium', 'low']:
            count = self.margin_counters.get(group, 0)
            actual_percent = (count / self.non_mandatory_total * 100) if self.non_mandatory_total > 0 else 0
            target_percent = self.target_distribution.get(group, 0) * 100

            diff = actual_percent - target_percent
            sign = "+" if diff >= 0 else ""
            print(f"{group_names[group]}:")
            print(f"  Кол-во: {count} блюд")
            print(f"  Фактически: {actual_percent:.1f}%")
            print(f"  Целевое: {target_percent:.1f}%")
            print(f"  Отклонение: {sign}{diff:.1f}%")
            total_percent += actual_percent

        unknown_count = self.margin_counters.get('unknown', 0)
        if unknown_count > 0:
            unknown_percent = (unknown_count / self.non_mandatory_total * 100)
            print(f"\n{group_names['unknown']}: {unknown_count} блюд ({unknown_percent:.1f}%)")

        print(f"\nОбщий процент распределения: {total_percent:.1f}%")

    def get_menu_stats(self) -> Dict:
        """Возвращает статистику по сгенерированному меню"""
        all_dishes = []
        for category in self.generated_menu.values():
            all_dishes.extend(category)

        total = len(all_dishes)

        # Считаем распределение по FoodCost
        foodcost_distribution = {}
        total_with_margin = 0

        for dish in all_dishes:
            marge = self.get_row_value(dish, 'marge')
            if marge is not None:
                total_with_margin += 1
                group = self.calculate_margin_group(marge)
                foodcost_distribution[group] = foodcost_distribution.get(group, 0) + 1

        # Рассчитываем проценты
        stats = {}
        if total_with_margin > 0:
            for group, count in foodcost_distribution.items():
                stats[group] = round(count / total_with_margin * 100, 1)

        return {
            'total_dishes': total,
            'total_with_margin': total_with_margin,
            'foodcost_distribution': stats,
            'categories': {k: len(v) for k, v in self.generated_menu.items()},
            'distribution_counters': dict(self.margin_counters)
        }

    def update_menu_history(self):
        """Обновляет даты последнего использования для выбранных блюд"""
        cursor = self.conn.cursor()

        all_selected = []
        for category in self.generated_menu.values():
            all_selected.extend(category)

        for dish in all_selected:
            dish_id = self.get_row_value(dish, 'id')
            if dish_id:
                cursor.execute("""
                    UPDATE dishes 
                    SET date_last_used = ? 
                    WHERE id = ?
                """, (self.menu_date_str, dish_id))

        self.conn.commit()
        print(f"\n✓ Даты обновлены для {len(all_selected)} блюд")

    def print_menu_summary(self):
        """Выводит краткое резюме меню"""
        print("\n" + "=" * 60)
        print("ИТОГОВОЕ МЕНЮ:")
        print("=" * 60)

        category_names = {
            'salads': 'САЛАТЫ',
            'soups': 'СУПЫ',
            'main_courses': 'ВТОРЫЕ БЛЮДА',
            'garnishes': 'ГАРНИРЫ',
            'bakery': 'ВЫПЕЧКА',
            'drinks': 'НАПИТКИ'
        }

        for category_key, dishes in self.generated_menu.items():
            print(f"\n{category_names[category_key]} ({len(dishes)}):")

            for i, dish in enumerate(dishes, 1):
                name = self.get_row_value(dish, 'name', 'Без названия')
                marge = self.get_row_value(dish, 'marge')
                is_mandatory = self.get_row_value(dish, 'is_mandatory', 0)

                prefix = "★ " if is_mandatory == 1 else "  "
                margin_info = f" [{marge}%]" if marge is not None else ""

                print(f"  {prefix}{i}. {name}{margin_info}")

    def close(self):
        """Закрывает соединение с БД"""
        self.conn.close()


def initialize_database(db_path: str):
    """Создает необходимые таблицы для работы системы"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Проверяем существование таблиц и создаем их при необходимости
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            main_ingredient TEXT,
            marge REAL,
            is_using INTEGER DEFAULT 1,
            is_mandatory INTEGER DEFAULT 0,
            date_last_used TEXT
        )
    """)

    # Создаем индексы для ускорения поиска
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dishes_type ON dishes(type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dishes_using ON dishes(is_using)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dishes_mandatory ON dishes(is_mandatory)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dishes_date ON dishes(date_last_used)")

    conn.commit()
    conn.close()
    print("✓ База данных инициализирована")


# Пример использования
if __name__ == "__main__":
    # Инициализация БД
    initialize_database('menu.db')

    # Создание генератора меню
    generator = MenuGenerator('menu.db', datetime.now())

    # Генерация меню
    menu = generator.generate_full_menu()

    # Вывод меню
    generator.print_menu_summary()

    # Обновление истории
    generator.update_menu_history()

    generator.close()