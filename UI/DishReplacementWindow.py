import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime


class DishReplacementWindow:
    def __init__(self, parent, current_dish_info, category_key, callback):
        """
        Окно замены блюда

        Args:
            parent: родительское окно
            current_dish_info: информация о текущем блюде (dict)
            category_key: ключ категории ('salads', 'soups', etc.)
            callback: функция обратного вызова при выборе блюда
        """
        self.parent = parent
        self.current_dish = current_dish_info
        self.category_key = category_key
        self.callback = callback
        self.selected_dish = None

        # Создаем окно
        self.window = tk.Toplevel(parent)
        self.window.title("Замена блюда")
        self.window.geometry("1000x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.setup_ui()
        self.load_replacement_dishes()

    def setup_ui(self):
        """Настройка интерфейса окна"""
        # Главный контейнер
        main_frame = tk.Frame(self.window, padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Заголовок с информацией о текущем блюде
        header_frame = tk.Frame(main_frame, relief=tk.RIDGE, borderwidth=2, padx=10, pady=10)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(header_frame,
                 text=f"Замена блюда: {self.current_dish.get('name', 'Неизвестно')}",
                 font=('Arial', 14, 'bold')).pack(anchor=tk.W)

        # Информация о текущем блюде
        info_frame = tk.Frame(header_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))

        info_text = f"""
Категория: {self.get_category_name(self.category_key)}
Стоимость: {self.current_dish.get('cost', '-')}
Вес: {self.current_dish.get('weight', '-')}
Маржа: {self.current_dish.get('marge', 0)}%
Последнее использование: {self.current_dish.get('date_last_used', 'Не использовалось')}
        """.strip()

        tk.Label(info_frame, text=info_text,
                 justify=tk.LEFT, font=('Arial', 10)).pack(anchor=tk.W)

        # Инструкция
        tk.Label(main_frame,
                 text="Выберите новое блюдо из списка (отсортировано по марже и давности использования):",
                 font=('Arial', 11)).pack(anchor=tk.W, pady=(0, 10))

        # Таблица доступных блюд
        table_frame = tk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Создаем Treeview
        columns = ('ID', 'Название', 'Описание', 'Стоимость', 'Вес',
                   'Основной ингредиент', 'Маржа', 'Последнее использование')
        self.dish_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Настройка колонок
        col_widths = {
            'ID': 50,
            'Название': 200,
            'Описание': 250,
            'Стоимость': 80,
            'Вес': 60,
            'Основной ингредиент': 120,
            'Маржа': 70,
            'Последнее использование': 120
        }

        for col in columns:
            self.dish_tree.heading(col, text=col)
            self.dish_tree.column(col, width=col_widths.get(col, 100))

        # Скроллбары
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.dish_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.dish_tree.xview)
        self.dish_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.dish_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Привязываем двойной клик для выбора
        self.dish_tree.bind('<Double-1>', self.on_dish_select)

        # Панель кнопок
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        tk.Button(button_frame, text="Отмена",
                  command=self.window.destroy).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(button_frame, text="Заменить выбранное",
                  command=self.confirm_replacement).pack(side=tk.RIGHT)

    def get_category_name(self, category_key):
        """Получить русское название категории"""
        category_names = {
            'salads': 'Салаты',
            'soups': 'Первые блюда',
            'main_courses': 'Вторые блюда',
            'garnishes': 'Гарниры',
            'bakery': 'Выпечка',
            'drinks': 'Напитки'
        }
        return category_names.get(category_key, category_key)

    def get_category_db_name(self, category_key):
        """Получить название категории для БД"""
        category_mapping = {
            'salads': 'Салат',
            'soups': 'Первое',
            'main_courses': 'Второе',
            'garnishes': 'Гарнир',
            'bakery': 'Выпечка',
            'drinks': 'Напиток'
        }
        return category_mapping.get(category_key, category_key)

    def get_actual_category_from_db(self):
        """Получить реальный тип категории из БД для текущего блюда"""
        try:
            if self.current_dish.get('id'):
                conn = sqlite3.connect('canteen.db')
                cur = conn.cursor()
                cur.execute("SELECT type FROM dishes WHERE id = ?", (self.current_dish['id'],))
                result = cur.fetchone()
                conn.close()
                if result:
                    return result[0]
        except:
            pass

        return self.get_category_db_name(self.category_key)

    def load_replacement_dishes(self):
        """Загрузить доступные блюда для замены"""
        try:
            # Получаем реальное название категории из БД
            actual_category = self.get_actual_category_from_db()

            # Подключаемся к БД
            conn = sqlite3.connect('canteen.db')
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Ищем блюда той же категории, которые активны
            current_dish_id = self.current_dish.get('id')

            if current_dish_id:
                query = """
                    SELECT 
                        id, name, description, cost, weight, 
                        main_ingredient, marge, 
                        COALESCE(date_last_used, 'Не использовалось') as date_last_used
                    FROM dishes 
                    WHERE type = ? 
                    AND is_using = 1 
                    AND id != ?
                    ORDER BY 
                        CASE 
                            WHEN date_last_used IS NULL OR date_last_used = '' THEN '9999-12-31'
                            ELSE date_last_used 
                        END ASC,
                        CASE WHEN marge IS NULL THEN 0 ELSE marge END DESC,
                        name ASC
                """
                cur.execute(query, (actual_category, current_dish_id))
            else:
                query = """
                    SELECT 
                        id, name, description, cost, weight, 
                        main_ingredient, marge, 
                        COALESCE(date_last_used, 'Не использовалось') as date_last_used
                    FROM dishes 
                    WHERE type = ? 
                    AND is_using = 1
                    ORDER BY 
                        CASE 
                            WHEN date_last_used IS NULL OR date_last_used = '' THEN '9999-12-31'
                            ELSE date_last_used 
                        END ASC,
                        CASE WHEN marge IS NULL THEN 0 ELSE marge END DESC,
                        name ASC
                """
                cur.execute(query, (actual_category,))

            dishes = cur.fetchall()
            conn.close()

            # Отображаем в таблице
            for dish_row in dishes:
                try:
                    dish_dict = dict(dish_row)

                    # Форматируем маржу
                    marge = dish_dict.get('marge')
                    marge_str = f"{marge}%" if marge and marge != 0 else "нет"

                    # Форматируем дату
                    date_str = dish_dict.get('date_last_used', '')
                    if date_str in ('', 'Не использовалось', None):
                        date_display = 'Никогда'
                    else:
                        try:
                            date_formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d.%m.%Y']
                            date_obj = None
                            for fmt in date_formats:
                                try:
                                    date_obj = datetime.strptime(date_str, fmt)
                                    break
                                except:
                                    continue

                            if date_obj:
                                date_display = date_obj.strftime('%d.%m.%Y')
                            else:
                                date_display = str(date_str)[:10]
                        except:
                            date_display = str(date_str)[:10]

                    self.dish_tree.insert("", tk.END, values=(
                        dish_dict.get('id', ''),
                        dish_dict.get('name', ''),
                        dish_dict.get('description', '') or '-',
                        dish_dict.get('cost', '') or '-',
                        dish_dict.get('weight', '') or '-',
                        dish_dict.get('main_ingredient', '') or '-',
                        marge_str,
                        date_display
                    ))

                except Exception as e:
                    continue

            # Если нет доступных блюд
            if not dishes:
                tk.Label(self.window,
                         text="Нет доступных блюд для замены в этой категории",
                         font=('Arial', 11)).pack()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить блюда: {str(e)}")

    def on_dish_select(self, event):
        """Обработка выбора блюда по двойному клику"""
        selection = self.dish_tree.selection()
        if selection:
            self.confirm_replacement()

    def confirm_replacement(self):
        """Подтверждение замены выбранного блюда"""
        selection = self.dish_tree.selection()
        if not selection:
            messagebox.showwarning("Не выбрано", "Пожалуйста, выберите блюдо для замены!")
            return

        # Получаем данные выбранного блюда
        selected_item = self.dish_tree.item(selection[0])
        values = selected_item['values']

        try:
            # Создаем словарь с данными нового блюда
            new_dish = {
                'id': values[0],
                'name': values[1],
                'description': values[2],
                'cost': values[3],
                'weight': values[4],
                'main_ingredient': values[5],
                'marge': float(values[6].replace('%', '').replace('нет', '0')) if values[6] != 'нет' else 0,
                'date_last_used': values[7]
            }

            # Вызываем callback функцию с данными
            if self.callback:
                self.callback(self.current_dish, new_dish, self.category_key)

            # Закрываем окно
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при выборе блюда: {str(e)}")