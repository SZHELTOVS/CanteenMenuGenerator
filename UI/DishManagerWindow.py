import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
from data.DBWorker import get_all_dishes, get_connection, ultra_search_dishes


class DishManagerWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Управление блюдами")
        self.window.geometry("1300x600")  # Увеличил ширину для новой колонки
        self.window.minsize(1100, 400)

        self.window.transient(parent)
        self.window.grab_set()

        self.setup_ui()
        self.load_dishes()

    def setup_ui(self):
        self.frame = tk.Frame(self.window)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Настройка сетки
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        # === ЗАГОЛОВОК ===
        tk.Label(self.frame, text="УПРАВЛЕНИЕ БЛЮДАМИ",
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=10, sticky="w")

        # === ФИЛЬТРЫ И ПОИСК ===
        filters_frame = tk.Frame(self.frame)
        filters_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Тип блюда
        tk.Label(filters_frame, text="Тип:").pack(side=tk.LEFT, padx=(0, 5))
        self.type_var = tk.StringVar(value="Все")
        self.type_combo = ttk.Combobox(filters_frame, textvariable=self.type_var,
                                       width=15, state="readonly")
        self.type_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Статус активности
        tk.Label(filters_frame, text="Статус:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_var = tk.StringVar(value="Все")
        self.status_combo = ttk.Combobox(filters_frame, textvariable=self.status_var,
                                         values=["Все", "Активные", "Неактивные"],
                                         width=12, state="readonly")
        self.status_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Обязательные
        tk.Label(filters_frame, text="Обязательные:").pack(side=tk.LEFT, padx=(0, 5))
        self.mandatory_var = tk.StringVar(value="Все")
        self.mandatory_combo = ttk.Combobox(filters_frame, textvariable=self.mandatory_var,
                                            values=["Все", "Обязательные", "Не обязательные"],
                                            width=15, state="readonly")
        self.mandatory_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Фильтр по дате последнего использования
        tk.Label(filters_frame, text="Последнее использование:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_filter_var = tk.StringVar(value="Все")
        self.date_filter_combo = ttk.Combobox(filters_frame, textvariable=self.date_filter_var,
                                              values=["Все", "Сегодня", "На этой неделе",
                                                      "В этом месяце", "Больше месяца", "Никогда"],
                                              width=15, state="readonly")
        self.date_filter_combo.pack(side=tk.LEFT, padx=(0, 20))

        # Поиск
        tk.Label(filters_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(filters_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry.bind('<Return>', lambda e: self.apply_filters())

        tk.Button(filters_frame, text="Применить",
                  command=self.apply_filters).pack(side=tk.LEFT)

        # === ТАБЛИЦА БЛЮД ===
        table_frame = tk.Frame(self.frame)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.setup_dishes_table(table_frame)

        # === КНОПКИ МАССОВЫХ ДЕЙСТВИЙ ===
        actions_frame = tk.Frame(self.frame)
        actions_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        tk.Button(actions_frame, text="✅ Включить выбранные",
                  command=lambda: self.bulk_change_status(True)).pack(side=tk.LEFT, padx=2)
        tk.Button(actions_frame, text="❌ Выключить выбранные",
                  command=lambda: self.bulk_change_status(False)).pack(side=tk.LEFT, padx=2)

        tk.Button(actions_frame, text="⭐ Обязательные",
                  command=lambda: self.bulk_change_mandatory(True)).pack(side=tk.LEFT, padx=2)
        tk.Button(actions_frame, text="○ Не обязательные",
                  command=lambda: self.bulk_change_mandatory(False)).pack(side=tk.LEFT, padx=2)

        # Кнопка очистки дат использования
        tk.Button(actions_frame, text="🗑️ Очистить даты использования",
                  command=self.clear_dates_usage).pack(side=tk.LEFT, padx=2)

        # Кнопка установки сегодняшней даты
        tk.Button(actions_frame, text="📅 Установить сегодня",
                  command=self.set_today_date).pack(side=tk.LEFT, padx=2)

    def setup_dishes_table(self, parent):
        """Создает таблицу для блюд"""
        columns = (
            'ID', 'Тип', 'Название', 'Описание', 'Стоимость', 'Вес',
            'Основной ингредиент', 'Маржа', 'Последнее использование',
            'Статус', 'Обязат.'
        )

        self.tree = ttk.Treeview(
            parent,
            columns=columns,
            show='headings',
            height=20
        )

        # Настройка колонок
        col_widths = {
            'ID': 50, 'Тип': 100, 'Название': 250, 'Описание': 150,
            'Стоимость': 80, 'Вес': 70, 'Основной ингредиент': 120,
            'Маржа': 70, 'Последнее использование': 120,
            'Статус': 80, 'Обязат.': 70
        }

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 100))

        # Скроллбары
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Привязка событий
        self.tree.bind('<Button-1>', self.on_tree_click)

    def load_dishes(self):
        """Загружает все блюда и обновляет список типов"""
        dishes = get_all_dishes(include_disabled=True)

        # Собираем уникальные типы
        types = set()
        self.all_dishes = []

        for dish in dishes:
            if isinstance(dish, tuple):
                if len(dish) >= 11:
                    dish_dict = {
                        'id': dish[0],
                        'type': dish[1],
                        'name': dish[2],
                        'description': dish[3],
                        'cost': dish[4],
                        'weight': dish[5],
                        'main_ingredient': dish[6],
                        'marge': dish[7],
                        'date_last_used': dish[8],
                        'is_using': dish[9],
                        'is_mandatory': dish[10]
                    }
                else:
                    continue
            else:
                continue

            self.all_dishes.append(dish_dict)
            dish_type = dish_dict.get('type')
            if dish_type:
                types.add(dish_type)

        # Обновляем комбобокс типов
        type_list = ["Все"] + sorted([t for t in types if t])
        self.type_combo['values'] = type_list

        self.apply_filters()

    def apply_filters(self):
        """Применяет фильтры и отображает блюда"""
        # Очищаем таблицу
        for item in self.tree.get_children():
            self.tree.delete(item)

        selected_type = self.type_var.get()
        selected_status = self.status_var.get()
        selected_mandatory = self.mandatory_var.get()
        selected_date_filter = self.date_filter_var.get()
        search_text = self.search_var.get().strip()

        # Если есть текст поиска - используем ультра-поиск
        if search_text:
            try:
                results = ultra_search_dishes(
                    search_text=search_text,
                    include_disabled=True,
                    min_similarity=0.3,
                    use_regex=True
                )

                filtered_dishes = []
                for dish in results:
                    if len(dish) >= 11:
                        dish_dict = {
                            'id': dish[0],
                            'type': dish[1],
                            'name': dish[2],
                            'description': dish[3],
                            'cost': dish[4],
                            'weight': dish[5],
                            'main_ingredient': dish[6],
                            'marge': dish[7],
                            'date_last_used': dish[8],
                            'is_using': dish[9],
                            'is_mandatory': dish[10]
                        }
                        filtered_dishes.append(dish_dict)
            except:
                filtered_dishes = self.all_dishes
        else:
            filtered_dishes = self.all_dishes

        # Применяем остальные фильтры
        final_dishes = []
        today = datetime.now().date()

        for dish in filtered_dishes:
            # Фильтр по типу
            dish_type = dish.get('type')
            if selected_type != "Все" and dish_type != selected_type:
                continue

            # Фильтр по статусу активности
            is_using = dish.get('is_using')
            if is_using is None:
                is_active = True
            else:
                is_active = int(is_using) == 1 if isinstance(is_using, (int, str)) else bool(is_using)

            if selected_status == "Активные" and not is_active:
                continue
            if selected_status == "Неактивные" and is_active:
                continue

            # Фильтр по обязательности
            is_mandatory = dish.get('is_mandatory', 0)
            if selected_mandatory == "Обязательные" and is_mandatory != 1:
                continue
            if selected_mandatory == "Не обязательные" and is_mandatory == 1:
                continue

            # Фильтр по дате последнего использования
            date_last_used = dish.get('date_last_used')
            if selected_date_filter != "Все":
                if not date_last_used or date_last_used.strip() == "":
                    if selected_date_filter != "Никогда":
                        continue
                else:
                    try:
                        # Парсим дату в формате YYYY-MM-DD
                        use_date = datetime.strptime(date_last_used, "%Y-%m-%d").date()

                        if selected_date_filter == "Сегодня":
                            if use_date != today:
                                continue
                        elif selected_date_filter == "На этой неделе":
                            # Находим понедельник текущей недели
                            monday = today - datetime.timedelta(days=today.weekday())
                            if use_date < monday:
                                continue
                        elif selected_date_filter == "В этом месяце":
                            if use_date.year != today.year or use_date.month != today.month:
                                continue
                        elif selected_date_filter == "Больше месяца":
                            # Проверяем, что прошло больше 30 дней
                            days_diff = (today - use_date).days
                            if days_diff <= 30:
                                continue
                        elif selected_date_filter == "Никогда":
                            # Пропускаем, так как у блюда есть дата использования
                            continue
                    except:
                        # Если дата в неправильном формате, пропускаем фильтр
                        pass

            final_dishes.append(dish)

        # Заполняем таблицу
        for dish in final_dishes:
            is_using = dish.get('is_using')
            if is_using is None:
                is_active = True
            else:
                is_active = int(is_using) == 1 if isinstance(is_using, (int, str)) else bool(is_using)

            status = "✅ Активно" if is_active else "❌ Неактивно"

            is_mandatory = dish.get('is_mandatory', 0)
            mandatory = "⭐" if is_mandatory == 1 else "○"

            marge = dish.get('marge')
            if marge in (None, '', '0', 0):
                margin = "нет"
            else:
                try:
                    margin = f"{float(marge):.1f}%"
                except:
                    margin = str(marge)

            # Форматируем дату последнего использования
            date_last_used = dish.get('date_last_used', '')
            if date_last_used and date_last_used.strip():
                try:
                    # Преобразуем из YYYY-MM-DD в DD.MM.YYYY
                    use_date = datetime.strptime(date_last_used, "%Y-%m-%d")
                    formatted_date = use_date.strftime("%d.%m.%Y")

                    # Добавляем подсчет дней с последнего использования
                    days_ago = (datetime.now().date() - use_date.date()).days
                    if days_ago == 0:
                        date_display = f"Сегодня"
                    elif days_ago == 1:
                        date_display = f"Вчера"
                    else:
                        date_display = f"{formatted_date} ({days_ago} дн.)"
                except:
                    date_display = date_last_used
            else:
                date_display = "Никогда"

            self.tree.insert("", tk.END, values=(
                dish.get('id', ''),
                dish.get('type', ''),
                dish.get('name', ''),
                dish.get('description', '') or '',
                f"{dish.get('cost', 0)}" if dish.get('cost') else "",
                dish.get('weight', ''),
                dish.get('main_ingredient', '') or '-',
                margin,
                date_display,  # Новая колонка с датой
                status,
                mandatory
            ))

    def on_tree_click(self, event):
        """Обрабатывает клик по ячейкам таблицы"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)

            if not item:
                return

            values = list(self.tree.item(item, 'values'))
            dish_id = values[0]

            conn = get_connection()
            cur = conn.cursor()

            # Колонка "Статус" (10-я колонка, индекс 9)
            if column == "#10":
                current_status = values[9]
                new_active = 0 if current_status == "✅ Активно" else 1

                # Обновляем в базе данных
                cur.execute("UPDATE dishes SET is_using = ? WHERE id = ?", (new_active, dish_id))

                # Обновляем в локальном списке блюд
                for dish in self.all_dishes:
                    if dish.get('id') == int(dish_id):
                        dish['is_using'] = new_active
                        break

                # Обновляем отображение
                values[9] = "✅ Активно" if new_active == 1 else "❌ Неактивно"
                self.tree.item(item, values=values)

            # Колонка "Обязат." (11-я колонка, индекс 10)
            elif column == "#11":
                current_mandatory = values[10]
                new_mandatory = 0 if current_mandatory == "⭐" else 1

                # Обновляем в базе данных
                cur.execute("UPDATE dishes SET is_mandatory = ? WHERE id = ?", (new_mandatory, dish_id))

                # Обновляем в локальном списке блюд
                for dish in self.all_dishes:
                    if dish.get('id') == int(dish_id):
                        dish['is_mandatory'] = new_mandatory
                        break

                # Обновляем отображение
                values[10] = "⭐" if new_mandatory == 1 else "○"
                self.tree.item(item, values=values)

            # Колонка "Последнее использование" (9-я колонка, индекс 8)
            elif column == "#9":
                # При клике на дату можно установить сегодняшнюю дату
                if messagebox.askyesno("Обновить дату",
                                       "Установить сегодняшнюю дату как дату последнего использования?"):
                    today_str = datetime.now().strftime("%Y-%m-%d")

                    # Обновляем в базе данных
                    cur.execute("UPDATE dishes SET date_last_used = ? WHERE id = ?",
                                (today_str, dish_id))

                    # Обновляем в локальном списке блюд
                    for dish in self.all_dishes:
                        if dish.get('id') == int(dish_id):
                            dish['date_last_used'] = today_str
                            break

                    # Обновляем отображение
                    values[8] = "Сегодня"
                    self.tree.item(item, values=values)

            conn.commit()
            conn.close()

    def get_selected_dishes(self):
        """Возвращает список ID выбранных блюд"""
        selected_ids = []
        for item in self.tree.selection():
            values = self.tree.item(item, 'values')
            if values:
                selected_ids.append(values[0])
        return selected_ids

    def bulk_change_status(self, enable):
        """Массовое изменение статуса активности"""
        selected_ids = self.get_selected_dishes()

        if not selected_ids:
            messagebox.showwarning("Нет выбора", "Выберите блюда для изменения статуса")
            return

        action = "включить" if enable else "выключить"
        if not messagebox.askyesno("Подтверждение",
                                   f"Вы уверены, что хотите {action} {len(selected_ids)} блюд?"):
            return

        conn = get_connection()
        cur = conn.cursor()

        for dish_id in selected_ids:
            cur.execute("UPDATE dishes SET is_using = ? WHERE id = ?", (1 if enable else 0, dish_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Успех", f"Статус активности обновлен для {len(selected_ids)} блюд")
        self.apply_filters()

    def bulk_change_mandatory(self, make_mandatory):
        """Массовое изменение статуса обязательности"""
        selected_ids = self.get_selected_dishes()

        if not selected_ids:
            messagebox.showwarning("Нет выбора", "Выберите блюда для изменения обязательности")
            return

        action = "сделать обязательными" if make_mandatory else "убрать обязательность"
        if not messagebox.askyesno("Подтверждение",
                                   f"Вы уверены, что хотите {action} {len(selected_ids)} блюд?"):
            return

        conn = get_connection()
        cur = conn.cursor()

        for dish_id in selected_ids:
            cur.execute("UPDATE dishes SET is_mandatory = ? WHERE id = ?",
                        (1 if make_mandatory else 0, dish_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Успех", f"Статус обязательности обновлен для {len(selected_ids)} блюд")
        self.apply_filters()

    def clear_dates_usage(self):
        """Очищает даты последнего использования у выбранных блюд"""
        selected_ids = self.get_selected_dishes()

        if not selected_ids:
            messagebox.showwarning("Нет выбора", "Выберите блюда для очистки дат использования")
            return

        if not messagebox.askyesno("Подтверждение",
                                   f"Очистить даты последнего использования у {len(selected_ids)} блюд?"):
            return

        conn = get_connection()
        cur = conn.cursor()

        for dish_id in selected_ids:
            cur.execute("UPDATE dishes SET date_last_used = NULL WHERE id = ?", (dish_id,))

        conn.commit()
        conn.close()

        messagebox.showinfo("Успех", f"Даты использования очищены для {len(selected_ids)} блюд")
        self.apply_filters()

    def set_today_date(self):
        """Устанавливает сегодняшнюю дату как дату последнего использования"""
        selected_ids = self.get_selected_dishes()

        if not selected_ids:
            messagebox.showwarning("Нет выбора", "Выберите блюда для установки даты")
            return

        today_str = datetime.now().strftime("%Y-%m-%d")

        if not messagebox.askyesno("Подтверждение",
                                   f"Установить сегодняшнюю дату ({today_str}) как дату последнего "
                                   f"использования для {len(selected_ids)} блюд?"):
            return

        conn = get_connection()
        cur = conn.cursor()

        for dish_id in selected_ids:
            cur.execute("UPDATE dishes SET date_last_used = ? WHERE id = ?", (today_str, dish_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Успех", f"Дата использования обновлена для {len(selected_ids)} блюд")
        self.apply_filters()