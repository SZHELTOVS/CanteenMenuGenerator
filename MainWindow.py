import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import os
import sqlite3

from systemNeeds.TextLogger import TextLogger
from data.DBWorker import get_all_dishes, ultra_search_dishes, get_connection, init_db
from UI.DishManagerWindow import DishManagerWindow

# Импортируем модули для генерации меню
from Generator.MenuGenerator import MenuGenerator, initialize_database
from Generator.DocxGenerator import generate_menu_docx, update_used_dishes, format_menu_for_docx
from UI.DishReplacementWindow import DishReplacementWindow

from google.auth.exceptions import RefreshError
from drive.GoogleDriveWorker import execute_sinc


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Система управления меню")
        self.root.geometry("1500x800")

        # Инициализация базы данных
        init_db()
        initialize_database('canteen.db')

        # Переменные для генерации меню
        self.last_generated_menu = None
        self.last_generated_date = None
        self.generator = None

        # Словарь для маппинга блюд в меню
        self.menu_items_mapping = {}

        self.center_window(self.root)
        self.setup_ui()
        self.load_dishes()
        self.root.mainloop()

    def setup_ui(self):
        # Основной фрейм с двумя колонками
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Конфигурация сетки: левая часть - таблица, правая - управление
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # === ЛЕВАЯ ПАНЕЛЬ: ТАБЛИЦА И УПРАВЛЕНИЕ МЕНЮ ===
        left_panel = tk.Frame(main_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Вкладки для таблиц
        self.notebook = ttk.Notebook(left_panel)
        self.notebook.pack(fill="both", expand=True)

        # Вкладка 1: Все блюда
        self.dishes_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dishes_tab, text="Все блюда")
        self.setup_dishes_table(self.dishes_tab)

        # Вкладка 2: Сгенерированное меню
        self.menu_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.menu_tab, text="Сгенерированное меню")
        self.setup_menu_table(self.menu_tab)

        # === ПРАВАЯ ПАНЕЛЬ: УПРАВЛЕНИЕ ===
        right_panel = tk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew")

        # Заголовок управления
        tk.Label(right_panel, text="УПРАВЛЕНИЕ",
                 font=("Arial", 14, "bold")).pack(pady=(0, 15))

        # Секция генерации меню
        gen_frame = tk.LabelFrame(right_panel, text="Генерация меню", padx=10, pady=10)
        gen_frame.pack(fill="x", pady=(0, 15))

        # Поле для даты
        tk.Label(gen_frame, text="Дата меню:").pack(anchor="w")
        self.date_entry = tk.Entry(gen_frame, width=15)
        self.date_entry.pack(fill="x", pady=(5, 10))
        self.date_entry.insert(0, datetime.now().strftime("%d.%m.%Y"))

        # Кнопка установки сегодняшней даты
        tk.Button(gen_frame, text="Сегодня",
                  command=self.set_today_date).pack(fill="x", pady=(0, 10))

        # Кнопки генерации
        self.generate_btn = tk.Button(gen_frame, text="Сгенерировать меню",
                                      command=self.generate_menu)
        self.generate_btn.pack(fill="x", pady=5)

        self.view_menu_btn = tk.Button(gen_frame, text="Просмотреть меню",
                                       state="disabled",
                                       command=self.view_generated_menu)
        self.view_menu_btn.pack(fill="x", pady=5)

        self.save_docx_btn = tk.Button(gen_frame, text="Сохранить в DOCX",
                                       state="disabled",
                                       command=self.save_menu_to_docx)
        self.save_docx_btn.pack(fill="x", pady=5)

        self.confirm_btn = tk.Button(gen_frame, text="Подтвердить меню",
                                     state="disabled",
                                     command=self.confirm_menu)
        self.confirm_btn.pack(fill="x", pady=5)

        # Статистика меню
        self.menu_stats_label = tk.Label(gen_frame, text="Меню еще не сгенерировано",
                                         justify="left", relief="ridge",
                                         padx=5, pady=5)
        self.menu_stats_label.pack(fill="x", pady=(10, 0))

        # Секция поиска
        search_frame = tk.LabelFrame(right_panel, text="Поиск блюд", padx=10, pady=10)
        search_frame.pack(fill="x")

        self.search_entry = tk.Entry(search_frame, width=20)
        self.search_entry.pack(fill="x", pady=5)
        self.search_entry.bind('<Return>', lambda e: self.search_dishes())

        # Секция управления БД
        db_frame = tk.LabelFrame(right_panel, text="Управление базой", padx=10, pady=10)
        db_frame.pack(fill="x", pady=(0, 15))

        # Кнопка синхронизации
        tk.Button(db_frame, text="Синхронизация",
                  width=20, command=self.sync_handler).pack(fill="x", pady=5)

        # Кнопка управления блюдами
        tk.Button(db_frame, text="Управление блюдами",
                  width=20, command=self.dish_manager).pack(fill="x", pady=5)

        # Кнопка настроек
        tk.Button(db_frame, text="Настройки",
                  width=20, command=self.settings_handler).pack(fill="x", pady=5)

        tk.Button(search_frame, text="Найти",
                  command=self.search_dishes).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(search_frame, text="Показать все",
                  command=self.show_all).pack(side="right", fill="x", expand=True)

    def setup_dishes_table(self, parent):
        """Создает таблицу для блюд"""
        columns = ('ID', 'Тип', 'Название', 'Описание', 'Стоимость', 'Вес',
                   'Основной ингредиент', 'Маржа', 'Статус')

        self.dishes_tree = ttk.Treeview(
            parent,
            columns=columns,
            show='headings',
            height=25
        )

        col_widths = {
            'ID': 50, 'Тип': 100, 'Название': 250, 'Описание': 200,
            'Стоимость': 80, 'Вес': 70, 'Основной ингредиент': 150,
            'Маржа': 70, 'Статус': 80
        }

        for col in columns:
            self.dishes_tree.heading(col, text=col)
            self.dishes_tree.column(col, width=col_widths.get(col, 100))

        # Скроллбары
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.dishes_tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=self.dishes_tree.xview)

        self.dishes_tree.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )

        self.dishes_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

    def setup_menu_table(self, parent):
        """Создает таблицу для сгенерированного меню"""
        columns = ('Категория', 'Название', 'Стоимость', 'Вес', 'Основной ингредиент', 'Маржа')

        self.menu_tree = ttk.Treeview(
            parent,
            columns=columns,
            show='headings',
            height=25
        )

        col_widths = {
            'Категория': 100, 'Название': 300, 'Стоимость': 90,
            'Вес': 80, 'Основной ингредиент': 150, 'Маржа': 80
        }

        for col in columns:
            self.menu_tree.heading(col, text=col)
            self.menu_tree.column(col, width=col_widths.get(col, 100))

        # Скроллбары
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.menu_tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=self.menu_tree.xview)

        self.menu_tree.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )

        self.menu_tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # Контекстное меню для замены блюд
        self.menu_context_menu = tk.Menu(self.root, tearoff=0)
        self.menu_context_menu.add_command(label="Заменить блюдо",
                                           command=self.replace_selected_dish)

        self.menu_tree.bind('<Button-3>', self.show_menu_context_menu)
        self.menu_tree.bind('<Double-1>', self.on_menu_item_double_click)

    def load_dishes(self):
        """Загружает блюда из БД"""
        try:
            dishes = get_all_dishes(include_disabled=False)

            # Очищаем таблицу
            for item in self.dishes_tree.get_children():
                self.dishes_tree.delete(item)

            if not dishes:
                self.dishes_tree.insert("", tk.END, values=("", "", "Нет данных", "", "", "", "", "", ""))
                return

            # Определяем структуру данных
            first_dish = dishes[0]

            # Если это sqlite3.Row или словарь
            if hasattr(first_dish, 'keys') or isinstance(first_dish, dict):
                for dish in dishes:
                    if hasattr(dish, '_asdict'):
                        dish_dict = dish._asdict()
                    elif hasattr(dish, 'keys'):
                        dish_dict = dict(dish)
                    else:
                        dish_dict = dish

                    self.dishes_tree.insert("", tk.END, values=(
                        dish_dict.get('id', ''),
                        dish_dict.get('type', ''),
                        dish_dict.get('name', ''),
                        dish_dict.get('description', '') or '',
                        f"{dish_dict.get('cost', 0)}" if dish_dict.get('cost') else "",
                        dish_dict.get('weight', ''),
                        dish_dict.get('main_ingredient', '') or '-',
                        f"{dish_dict.get('marge', 0)}%" if dish_dict.get('marge') else "нет",
                        "Активно" if dish_dict.get('is_using', 1) else "Неактивно"
                    ))
            else:
                # Если это кортеж
                for dish in dishes:
                    try:
                        self.dishes_tree.insert("", tk.END, values=(
                            dish[0] if len(dish) > 0 else '',
                            dish[1] if len(dish) > 1 else '',
                            dish[2] if len(dish) > 2 else '',
                            dish[3] if len(dish) > 3 else '',
                            f"{dish[4]}" if len(dish) > 4 and dish[4] else "",
                            dish[5] if len(dish) > 5 else '',
                            dish[6] if len(dish) > 6 else '-' if not dish[6] else dish[6],
                            f"{dish[7]}%" if len(dish) > 7 and dish[7] else "нет",
                            "Активно" if (len(dish) > 10 and dish[10]) or (len(dish) > 9 and dish[9]) else "Неактивно"
                        ))
                    except IndexError:
                        continue

        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")

    def search_dishes(self):
        """Поиск блюд"""
        search_term = self.search_entry.get().strip()

        if not search_term:
            self.show_all()
            return

        try:
            results = ultra_search_dishes(
                search_text=search_term,
                include_disabled=False,
                min_similarity=0.3,
                use_regex=True
            )

            # Очищаем таблицу
            for item in self.dishes_tree.get_children():
                self.dishes_tree.delete(item)

            if not results:
                self.dishes_tree.insert("", tk.END, values=("", "", "Ничего не найдено", "", "", "", "", "", ""))
                return

            # Заполняем таблицу
            for dish in results:
                try:
                    self.dishes_tree.insert("", tk.END, values=(
                        dish[0] if len(dish) > 0 else '',
                        dish[1] if len(dish) > 1 else '',
                        dish[2] if len(dish) > 2 else '',
                        dish[3] if len(dish) > 3 else '',
                        f"{dish[4]}" if len(dish) > 4 and dish[4] else "",
                        dish[5] if len(dish) > 5 else '',
                        dish[6] if len(dish) > 6 else '-' if not dish[6] else dish[6],
                        f"{dish[7]}%" if len(dish) > 7 and dish[7] else "нет",
                        "Активно" if (len(dish) > 10 and dish[10]) or (len(dish) > 9 and dish[9]) else "Неактивно"
                    ))
                except IndexError:
                    continue

        except Exception as e:
            print(f"Ошибка поиска: {e}")

    def show_all(self):
        """Показать все блюда"""
        self.load_dishes()

    def set_today_date(self):
        """Устанавливает сегодняшнюю дату"""
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, datetime.now().strftime("%d.%m.%Y"))

    def generate_menu(self):
        """Генерирует меню по правилам"""
        try:
            # Получаем дату из поля ввода
            date_str = self.date_entry.get()
            try:
                menu_date = datetime.strptime(date_str, "%d.%m.%Y")
            except ValueError:
                messagebox.showwarning("Ошибка формата",
                                       f"Введите дату в формате dd.mm.YYYY")
                return

            # Создаем генератор
            generator = MenuGenerator('canteen.db', menu_date)

            # Генерируем меню
            self.generate_btn.config(state="disabled", text="Генерация...")
            self.root.update()

            menu_data = generator.generate_full_menu()

            # Сохраняем в переменные экземпляра
            self.last_generated_menu = menu_data
            self.last_generated_date = menu_date
            self.generator = generator

            # Получаем статистику
            stats = generator.get_menu_stats()

            # Форматируем статистику с акцентом на распределение по FoodCost
            stats_text = f"СТАТИСТИКА МЕНЮ на {date_str}\n"
            stats_text += f"Всего блюд: {stats['total_dishes']}\n"
            stats_text += f"Из них с известной маржой: {stats['total_with_margin']}\n\n"

            stats_text += "РАСПРЕДЕЛЕНИЕ ПО FOODCOST:\n"

            foodcost_stats = stats.get('foodcost_distribution', {})
            group_names = {
                'ultra_high': '• Сверхмаржинальные (FoodCost ≤30%):',
                'high': '• Высокомаржинальные (FoodCost 30-35%):',
                'medium': '• Среднемаржинальные (FoodCost 35-40%):',
                'low': '• Низкомаржинальные (FoodCost >40%):'
            }

            target_percentages = {
                'ultra_high': 50,
                'high': 20,
                'medium': 20,
                'low': 10
            }

            total_percentage = 0
            for group in ['ultra_high', 'high', 'medium', 'low']:
                actual_percent = foodcost_stats.get(group, 0)
                target_percent = target_percentages.get(group, 0)
                diff = actual_percent - target_percent
                sign = "+" if diff >= 0 else ""

                stats_text += f"{group_names[group]} {actual_percent:.1f}% "
                stats_text += f"(цель: {target_percent}%, отклонение: {sign}{diff:.1f}%)\n"
                total_percentage += actual_percent

            if 'unknown' in foodcost_stats:
                stats_text += f"\n• С неизвестной маржой: {foodcost_stats['unknown']:.1f}%\n"

            stats_text += f"\nКАТЕГОРИИ БЛЮД:\n"
            stats_text += f"• Салаты: {stats['categories'].get('salads', 0)} шт.\n"
            stats_text += f"• Супы: {stats['categories'].get('soups', 0)} шт.\n"
            stats_text += f"• Вторые блюда: {stats['categories'].get('main_courses', 0)} шт.\n"
            stats_text += f"• Гарниры: {stats['categories'].get('garnishes', 0)} шт.\n"
            stats_text += f"• Выпечка: {stats['categories'].get('bakery', 0)} шт.\n"
            stats_text += f"• Напитки: {stats['categories'].get('drinks', 0)} шт."

            self.menu_stats_label.config(text=stats_text)

            # Отображаем меню в таблице
            self.display_menu_in_table(menu_data)

            # Активируем кнопки
            self.generate_btn.config(state="normal", text="Сгенерировать меню")
            self.view_menu_btn.config(state="normal")
            self.save_docx_btn.config(state="normal")
            self.confirm_btn.config(state="normal")

            # Переключаем на вкладку меню
            self.notebook.select(1)

            messagebox.showinfo("Успех", "Меню успешно сгенерировано!")

        except Exception as e:
            self.generate_btn.config(state="normal", text="Сгенерировать меню")
            messagebox.showerror("Ошибка генерации", f"Ошибка: {str(e)}")

    def display_menu_in_table(self, menu_data):
        """Отображает сгенерированное меню в таблице"""
        # Очищаем таблицу
        for item in self.menu_tree.get_children():
            self.menu_tree.delete(item)

        # Очищаем маппинг
        self.menu_items_mapping.clear()

        # Маппинг внутренних ключей на отображаемые категории
        category_names = {
            'salads': 'Салаты',
            'soups': 'Первые блюда',
            'main_courses': 'Вторые блюда',
            'garnishes': 'Гарниры',
            'bakery': 'Выпечка',
            'drinks': 'Напитки'
        }

        total_dishes = 0

        # Заполняем таблицу
        for internal_key, display_name in category_names.items():
            dishes = menu_data.get(internal_key, [])

            for dish in dishes:
                total_dishes += 1
                try:
                    # Преобразуем в словарь
                    dish_dict = {}

                    if isinstance(dish, dict):
                        dish_dict = dish
                    elif isinstance(dish, sqlite3.Row):
                        dish_dict = dict(dish)
                    elif hasattr(dish, '_asdict'):
                        dish_dict = dish._asdict()
                    else:
                        continue

                    # Извлекаем данные
                    name = dish_dict.get('name', 'Неизвестно')
                    cost = dish_dict.get('cost', '')
                    weight = dish_dict.get('weight', '')
                    main_ingredient = dish_dict.get('main_ingredient', '-')
                    marge = dish_dict.get('marge', 0)

                    # Форматируем
                    cost_str = f"{int(cost)} руб." if cost and isinstance(cost, (int, float)) else str(cost)
                    weight_str = str(weight) if weight else ""
                    margin_str = f"{marge}%" if marge and marge > 0 else "нет"

                    # Вставляем в таблицу
                    item_id = self.menu_tree.insert("", tk.END, values=(
                        display_name,
                        name,
                        cost_str,
                        weight_str,
                        main_ingredient,
                        margin_str
                    ))

                    # Сохраняем полные данные блюда для замены
                    self.menu_items_mapping[item_id] = {
                        'dish': dish_dict,
                        'category': internal_key
                    }

                except Exception as e:
                    print(f"Ошибка при обработке блюда: {e}")

        if total_dishes == 0:
            self.menu_tree.insert("", tk.END, values=(
                "Нет данных", "Меню не сгенерировано", "", "", "", ""
            ))

    def show_menu_context_menu(self, event):
        """Показать контекстное меню для таблицы меню"""
        try:
            row_id = self.menu_tree.identify_row(event.y)
            if row_id:
                self.menu_tree.selection_set(row_id)
                self.menu_context_menu.post(event.x_root, event.y_root)
        finally:
            self.menu_context_menu.grab_release()

    def on_menu_item_double_click(self, event):
        """Обработка двойного клика по блюду в меню"""
        self.replace_selected_dish()

    def replace_selected_dish(self):
        """Заменить выбранное блюдо в меню"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showinfo("Не выбрано", "Пожалуйста, выберите блюдо для замены!")
            return

        item_id = selection[0]
        if item_id in self.menu_items_mapping:
            mapping_data = self.menu_items_mapping[item_id]
            current_dish = mapping_data['dish']
            category_key = mapping_data['category']

            # Убедимся, что есть ID
            if not current_dish.get('id'):
                dish_id = self.get_dish_id_from_db(current_dish.get('name'), category_key)
                current_dish['id'] = dish_id

            # Открываем окно замены
            replacement_window = DishReplacementWindow(
                parent=self.root,
                current_dish_info=current_dish,
                category_key=category_key,
                callback=self.apply_dish_replacement
            )
        else:
            messagebox.showerror("Ошибка", "Не удалось получить данные блюда.")

    def get_dish_id_from_db(self, dish_name, category_key):
        """Получить ID блюда из БД"""
        try:
            category_mapping = {
                'salads': 'Салат',
                'soups': 'Первое',
                'main_courses': 'Второе',
                'garnishes': 'Гарнир',
                'bakery': 'Выпечка',
                'drinks': 'Напиток'
            }

            db_category = category_mapping.get(category_key, category_key)

            conn = sqlite3.connect('canteen.db')
            cur = conn.cursor()

            cur.execute("""
                SELECT id FROM dishes 
                WHERE name = ? AND type = ? AND is_using = 1
                LIMIT 1
            """, (dish_name, db_category))

            result = cur.fetchone()
            conn.close()

            return result[0] if result else None

        except Exception as e:
            print(f"ERROR: Не удалось получить ID блюда: {str(e)}")
            return None

    def apply_dish_replacement(self, old_dish, new_dish, category_key):
        """Применить замену блюда"""
        try:
            if not self.last_generated_menu:
                messagebox.showerror("Ошибка", "Нет сгенерированного меню!")
                return

            # Получаем список блюд в категории
            category_dishes = self.last_generated_menu.get(category_key, [])

            # Находим индекс старого блюда
            old_dish_index = -1
            for i, dish in enumerate(category_dishes):
                dish_id = None
                if isinstance(dish, dict):
                    dish_id = dish.get('id')
                elif hasattr(dish, 'id'):
                    dish_id = dish.id
                elif isinstance(dish, sqlite3.Row):
                    dish_id = dish['id'] if 'id' in dish.keys() else None

                if dish_id and dish_id == old_dish.get('id'):
                    old_dish_index = i
                    break

            if old_dish_index == -1:
                messagebox.showerror("Ошибка", "Не удалось найти блюдо в меню!")
                return

            # Получаем полные данные нового блюда
            conn = sqlite3.connect('canteen.db')
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("SELECT * FROM dishes WHERE id = ? AND is_using = 1",
                        (new_dish['id'],))

            new_dish_full = cur.fetchone()
            conn.close()

            if not new_dish_full:
                messagebox.showerror("Ошибка", "Выбранное блюдо не найдено в БД!")
                return

            # Преобразуем в словарь
            new_dish_dict = dict(new_dish_full)

            # Заменяем блюдо
            category_dishes[old_dish_index] = new_dish_dict
            self.last_generated_menu[category_key] = category_dishes

            # Обновляем таблицу
            self.update_menu_table_after_replacement(old_dish, new_dish_dict, category_key)

            messagebox.showinfo("Успех",
                                f"Блюдо '{old_dish.get('name')}' заменено на '{new_dish_dict.get('name')}'")

            self.save_docx_btn.config(state="normal")
            self.confirm_btn.config(state="normal")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при замене блюда:\n{str(e)}")

    def update_menu_table_after_replacement(self, old_dish, new_dish, category_key):
        """Обновить таблицу меню после замены"""
        try:
            category_names = {
                'salads': 'Салаты',
                'soups': 'Первые блюда',
                'main_courses': 'Вторые блюда',
                'garnishes': 'Гарниры',
                'bakery': 'Выпечка',
                'drinks': 'Напитки'
            }
            category_display = category_names.get(category_key, category_key)

            # Находим и обновляем строку
            for item in self.menu_tree.get_children():
                values = self.menu_tree.item(item)['values']

                if values[0] == category_display and values[1] == old_dish.get('name'):
                    new_values = (
                        category_display,
                        new_dish.get('name', ''),
                        new_dish.get('cost', ''),
                        new_dish.get('weight', ''),
                        new_dish.get('main_ingredient', '') or '-',
                        f"{new_dish.get('marge', 0)}%" if new_dish.get('marge') else "нет"
                    )
                    self.menu_tree.item(item, values=new_values)
                    break

        except Exception as e:
            print(f"Ошибка при обновлении таблицы: {str(e)}")
            self.display_menu_in_table(self.last_generated_menu)

    def view_generated_menu(self):
        """Показывает сгенерированное меню"""
        if not self.last_generated_menu:
            messagebox.showwarning("Нет меню", "Сначала сгенерируйте меню!")
            return

        # Переключаем на вкладку меню
        self.notebook.select(1)

    def save_menu_to_docx(self):
        """Сохраняет меню в DOCX файл"""
        if not self.last_generated_menu:
            messagebox.showwarning("Нет меню", "Сначала сгенерируйте меню!")
            return

        try:
            # Используем функцию форматирования
            menu_dict = format_menu_for_docx(self.last_generated_menu)

            # Генерируем имя файла
            date_str = self.last_generated_date.strftime("%d.%m.%Y")
            filename = f"menu_{date_str.replace('.', '_')}.docx"

            # Сохраняем в DOCX
            generate_menu_docx(
                menu_dict,
                filename=filename,
                preview=False,
                date_str=date_str
            )

            # Показываем сообщение
            full_path = os.path.abspath(filename)
            messagebox.showinfo(
                "Сохранено",
                f"Меню успешно сохранено в файл:\n{filename}\n\n"
                f"Путь: {full_path}"
            )

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения:\n{str(e)}")

    def confirm_menu(self):
        """Подтверждает меню и обновляет даты использования"""
        if not self.last_generated_menu or not hasattr(self, 'generator'):
            messagebox.showwarning("Нет меню", "Сначала сгенерируйте меню!")
            return

        if messagebox.askyesno("Подтверждение",
                               "Подтвердить меню и обновить даты использования блюд?"):
            try:
                # Обновляем историю через генератор
                self.generator.update_menu_history()

                # Также обновляем через update_used_dishes
                menu_dict = format_menu_for_docx(self.last_generated_menu)
                date_str = self.last_generated_date.strftime('%Y-%m-%d')
                update_used_dishes(menu_dict, date_str)

                # Деактивируем кнопки
                self.confirm_btn.config(state="disabled")
                self.view_menu_btn.config(state="disabled")
                self.save_docx_btn.config(state="disabled")

                messagebox.showinfo("Успех", "Меню подтверждено!")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка подтверждения:\n{str(e)}")


    def sync_handler(self):
        print("Запущена синхронизация")
        try:
            execute_sinc()
        except RefreshError:
            messagebox.showerror(
                "Ошибка синхронизации",
                "Не удалось обновить доступ к Google Диску.\n"
                "Попробуйте войти в аккаунт заново — нажмите «Синхронизация» ещё раз."
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Синхронизация не удалась:\n{e}")
        finally:
            self.load_dishes()

    def settings_handler(self):
        self.open_settings()

    def center_window(self, window, width=None, height=None):
        window.update_idletasks()

        if width is None:
            width = window.winfo_width()
        if height is None:
            height = window.winfo_height()

        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        window.geometry(f"{width}x{height}+{x}+{y}")

    def open_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.geometry("400x600")
        self.center_window(self.settings_window)

        for i in range(3):
            self.settings_window.columnconfigure(i, weight=1)

        tk.Label(self.settings_window, text="Настройки",
                 font=("Arial", 16, "bold")).grid(row=1, column=0, columnspan=3)

        tk.Button(self.settings_window, text="Логи программы",
                  width=20, command=self.open_logs).grid(row=3, column=1, pady=10)
        tk.Button(self.settings_window, text="Очистка базы данных",
                  width=20, command=self.clear_db).grid(row=4, column=1, pady=10)

    def open_logs(self):
        if hasattr(self, 'log_window') and self.log_window.winfo_exists():
            self.log_window.lift()
            return

        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Логи программы")
        self.log_window.geometry("800x400")

        self.log_area = ScrolledText(self.log_window, state="disabled", height=20)
        self.log_area.pack(fill="both", expand=True, pady=5)

        import sys
        sys.stdout = TextLogger(self.log_area)

        print("Логовое окно открыто!")

    def dish_manager(self):
        dish_manager = DishManagerWindow(self.root)

    def clear_db(self):
        if messagebox.askyesno("Подтверждение", "Очистить всю базу данных?\nЭто действие нельзя отменить!"):
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM dishes")
                conn.commit()
                conn.close()
                self.load_dishes()
                messagebox.showinfo("Успех", "База данных очищена!")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка очистки: {str(e)}")


if __name__ == "__main__":
    MainWindow()