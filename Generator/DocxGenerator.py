# docx_generator.py
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
import sqlite3


def generate_menu_docx(menu_dict, filename='menu.docx', preview=True, date_str=None):
    """
    Генерирует меню в формате, похожем на пример
    menu_dict: {'Салаты': [('Название', 'цена', 'вес'), ...], ...}
    """
    doc = Document()

    # Настройка стилей
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(11)

    # Заголовок с датой
    if date_str is None:
        from datetime import datetime
        date_str = datetime.now().strftime('%d.%m.%Y')

    # ===== ПЕРВАЯ СТРАНИЦА =====
    # Добавляем дату
    date_para = doc.add_paragraph(date_str)
    date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    date_run = date_para.runs[0]
    date_run.bold = True
    date_run.font.size = Pt(12)

    # Добавляем заголовок МЕНЮ (обычный текст, не Heading)
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run('МЕНЮ')
    title_run.bold = True
    title_run.font.size = Pt(16)
    title_para.paragraph_format.space_after = Pt(12)  # Отступ после заголовка

    # Разделы для первой страницы
    first_page_sections = ['Салаты', 'Первые блюда', 'Вторые блюда', 'Гарниры']

    for section in first_page_sections:
        if section in menu_dict:
            dishes = menu_dict[section]
            if dishes:
                # Добавляем заголовок раздела
                heading = doc.add_paragraph(section)
                heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                heading.runs[0].bold = True
                heading.runs[0].font.size = Pt(12)
                heading.paragraph_format.space_after = Pt(4)

                # Создаем таблицу с 3 колонками
                table = doc.add_table(rows=len(dishes), cols=3)
                table.style = 'Table Grid'
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                table.autofit = False

                # Настройка ширины колонок
                for row in table.rows:
                    row.cells[0].width = Inches(4.5)  # Название
                    row.cells[1].width = Inches(1.2)  # Цена
                    row.cells[2].width = Inches(0.8)  # Вес

                # Устанавливаем отступы внутри ячеек
                for row in table.rows:
                    for cell in row.cells:
                        cell.paragraphs[0].paragraph_format.space_before = Pt(2)
                        cell.paragraphs[0].paragraph_format.space_after = Pt(2)

                for i, (name, cost, weight) in enumerate(dishes):
                    row = table.rows[i]

                    # Название блюда (левая колонка)
                    name_cell = row.cells[0]
                    name_para = name_cell.paragraphs[0]
                    name_run = name_para.add_run(name)
                    name_run.font.size = Pt(10)
                    name_para.alignment = WD_ALIGN_PARAGRAPH.LEFT

                    # Цена (средняя колонка)
                    price_cell = row.cells[1]
                    price_para = price_cell.paragraphs[0]
                    price_run = price_para.add_run(cost)
                    price_run.font.size = Pt(10)
                    price_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

                    # Вес/объем (правая колонка)
                    weight_cell = row.cells[2]
                    weight_para = weight_cell.paragraphs[0]
                    weight_text = str(weight) if weight and str(weight).lower() != 'nan' else ""
                    weight_run = weight_para.add_run(weight_text)
                    weight_run.font.size = Pt(10)
                    weight_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # Отступ после таблицы

    # ===== ВТОРАЯ СТРАНИЦА =====
    # Разрыв страницы
    doc.add_page_break()

    # Второй заголовок МЕНЮ на второй странице
    title2_para = doc.add_paragraph()
    title2_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title2_run = title2_para.add_run('МЕНЮ')
    title2_run.bold = True
    title2_run.font.size = Pt(16)
    title2_para.paragraph_format.space_after = Pt(12)

    # Разделы для второй страницы
    second_page_sections = ['Напитки', 'Выпечка']

    for section in second_page_sections:
        if section in menu_dict:
            dishes = menu_dict[section]
            if dishes:
                # Добавляем заголовок раздела
                heading = doc.add_paragraph(section)
                heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
                heading.runs[0].bold = True
                heading.runs[0].font.size = Pt(12)
                heading.paragraph_format.space_after = Pt(4)

                # Создаем таблицу с 3 колонками
                table = doc.add_table(rows=len(dishes), cols=3)
                table.style = 'Table Grid'
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                table.autofit = False

                # Настройка ширины колонок
                for row in table.rows:
                    row.cells[0].width = Inches(4.5)
                    row.cells[1].width = Inches(1.2)
                    row.cells[2].width = Inches(0.8)

                # Устанавливаем отступы внутри ячеек
                for row in table.rows:
                    for cell in row.cells:
                        cell.paragraphs[0].paragraph_format.space_before = Pt(2)
                        cell.paragraphs[0].paragraph_format.space_after = Pt(2)

                for i, (name, cost, weight) in enumerate(dishes):
                    row = table.rows[i]

                    # Название блюда
                    name_cell = row.cells[0]
                    name_para = name_cell.paragraphs[0]
                    name_run = name_para.add_run(name)
                    name_run.font.size = Pt(10)
                    name_para.alignment = WD_ALIGN_PARAGRAPH.LEFT

                    # Цена
                    price_cell = row.cells[1]
                    price_para = price_cell.paragraphs[0]
                    price_run = price_para.add_run(cost)
                    price_run.font.size = Pt(10)
                    price_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

                    # Вес/объем
                    weight_cell = row.cells[2]
                    weight_para = weight_cell.paragraphs[0]
                    weight_text = str(weight) if weight and str(weight).lower() != 'nan' else ""
                    weight_run = weight_para.add_run(weight_text)
                    weight_run.font.size = Pt(10)
                    weight_para.alignment = WD_ALIGN_PARAGRAPH.CENTER


    # Добавляем "Приятного аппетита!" на второй странице
    footer = doc.add_paragraph('Приятного аппетита!')
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.runs[0].bold = True
    footer.runs[0].font.size = Pt(13)
    footer.paragraph_format.space_before = Pt(12)  # Отступ перед футером

    # Сохраняем документ
    doc.save(filename)

    if preview:
        print(f"✅ DOCX сгенерирован: {filename}")
        print("Содержимое меню:")
        for sec, dishes in menu_dict.items():
            print(f"\n{sec}:")
            for name, cost, weight in dishes:
                print(f"  {name} - {cost} - {weight}")

    return filename


def format_menu_for_docx(generated_menu, date_str=None):
    """
    Преобразует сгенерированное меню из MenuGenerator в формат для DOCX
    БЕЗ ИЗМЕНЕНИЯ ФОРМАТА - просто копирует как есть
    """
    category_names = {
        'salads': 'Салаты',
        'soups': 'Первые блюда',
        'main_courses': 'Вторые блюда',
        'garnishes': 'Гарниры',
        'bakery': 'Выпечка',
        'drinks': 'Напитки'
    }

    menu_dict = {}

    for internal_key, display_key in category_names.items():
        dishes = generated_menu.get(internal_key, [])

        if not isinstance(dishes, list):
            print(f"⚠️ Внимание: {internal_key} не список, а {type(dishes)}")
            dishes = []

        formatted_dishes = []

        for dish in dishes:
            try:
                # Обрабатываем sqlite3.Row
                if isinstance(dish, sqlite3.Row):
                    # Преобразуем в словарь
                    dish_dict = dict(dish)
                    name = dish_dict.get('name', '')
                    description = dish_dict.get('description', '')  # Берем описание
                    cost = dish_dict.get('cost', '')
                    weight = dish_dict.get('weight', '')

                    # ===== ВАЖНО: объединяем название и описание =====
                    # Если есть описание, добавляем его через пробел к названию
                    if description and description.strip():
                        # Очищаем описание от лишних пробелов
                        desc_clean = description.strip()
                        # Объединяем название и описание через пробел
                        full_name = f"{name} {desc_clean}"
                    else:
                        full_name = name

                elif isinstance(dish, dict):
                    name = dish.get('name', '')
                    description = dish.get('description', '')  # Берем описание
                    cost = dish.get('cost', '')
                    weight = dish.get('weight', '')

                    # То же самое объединение
                    if description and description.strip():
                        full_name = f"{name} {description.strip()}"
                    else:
                        full_name = name

                elif isinstance(dish, (tuple, list)) and len(dish) >= 3:
                    # Если приходит уже сформированный кортеж
                    if len(dish) >= 4:  # Есть описание
                        full_name = dish[0]  # Предполагаем, что описание уже в названии
                        cost = dish[2] if len(dish) > 2 else dish[1]
                        weight = dish[3] if len(dish) > 3 else dish[2] if len(dish) > 2 else ''
                    else:
                        full_name = dish[0]
                        cost = dish[1]
                        weight = dish[2] if len(dish) > 2 else ''
                else:
                    print(f"⚠️ Неизвестный формат блюда: {type(dish)}")
                    continue

                # ===== ВАЖНО: НИЧЕГО НЕ ИЗМЕНЯЕМ! =====
                # Просто копируем как есть, но чистим от nan

                # Обработка стоимости
                if cost is None:
                    cost_str = ""
                elif isinstance(cost, float):
                    # Проверка на NaN для float
                    if cost != cost:  # Это специальная проверка для float NaN
                        cost_str = ""
                    else:
                        cost_str = str(cost)
                else:
                    cost_str = str(cost)

                # Обработка веса
                if weight is None:
                    weight_str = ""
                elif isinstance(weight, float):
                    # Проверка на NaN для float
                    if weight != weight:  # Это специальная проверка для float NaN
                        weight_str = ""
                    else:
                        weight_str = str(weight)
                else:
                    weight_str = str(weight)

                # Дополнительная очистка от текстовых "nan"
                if cost_str and cost_str.lower() == 'nan':
                    cost_str = ""
                if weight_str and weight_str.lower() == 'nan':
                    weight_str = ""

                # Убираем лишние пробелы
                cost_str = cost_str.strip() if cost_str else ""
                weight_str = weight_str.strip() if weight_str else ""

                formatted_dishes.append((full_name, cost_str, weight_str))

            except Exception as e:
                print(f"Ошибка при обработке блюда: {e}")
                import traceback
                traceback.print_exc()
                continue


        menu_dict[display_key] = formatted_dishes

    return menu_dict


def update_used_dishes(menu_dict, date_str):
    """Обновляет date_last_used для подтвержденных блюд"""
    try:
        from data.DB_Worker import get_connection

        conn = get_connection()
        cur = conn.cursor()

        updated_count = 0
        for section, dishes in menu_dict.items():
            for name, _, _ in dishes:
                clean_name = name.strip()

                # Поиск блюда в БД
                cur.execute("""
                    SELECT id FROM dishes 
                    WHERE LOWER(TRIM(name)) LIKE LOWER(?) 
                    LIMIT 1
                """, (f"%{clean_name}%",))

                result = cur.fetchone()
                if result:
                    dish_id = result[0]
                    cur.execute("""
                        UPDATE dishes SET date_last_used = ? 
                        WHERE id = ?
                    """, (date_str, dish_id))
                    updated_count += 1

        conn.commit()
        conn.close()
        return updated_count
    except Exception as e:
        print(f"Ошибка при обновлении БД: {e}")
        return 0


# Тестовая функция
def test_generator():
    """Тестовая функция для проверки генерации"""
    sample_menu = {
        'Салаты': [
            ('Салат сырный с чесноком (сыр "Российский", яйцо, майонез, чеснок)', '120 руб.', '130 г'),
            ('Салат "Синчу" (морковь по-корейски, свиные ушки)', '122 руб.', '130 г'),
        ],
        'Первые блюда': [
            ('Лапша с курицей', '100 руб.', '300 г'),
            ('Суп грибной', '122 руб.', '300 г'),
        ],
        'Вторые блюда': [
            ('Котлета мясная (свинина, говядина, лук, чеснок, перец чер., соль)', '132 руб.', '100 г'),
            ('Котлета рыбная', '146 руб.', '90 г'),
        ],
        'Гарниры': [
            ('Пюре картофельное', '50 руб.', '200 г'),
            ('Каша гречневая', '70 руб.', '150 г'),
        ],
        'Напитки': [
            ('Компот', '30 руб.', '200 мл'),
            ('Чай (черный, зеленый)', '6 руб.', '200 мл'),
        ],
        'Выпечка': [
            ('Хлеб (черный, белый)', '6 руб.', '1 кусок'),
            ('Блины - 3 шт.', '50 руб.', '150 г'),
        ]
    }

    return generate_menu_docx(sample_menu, 'test_menu.docx', preview=True)


if __name__ == "__main__":
    # Запуск теста
    test_generator()