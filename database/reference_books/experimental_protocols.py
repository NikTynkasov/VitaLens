# database/reference_books/experimental_protocols.py
""" основной модуль для справочника экспериментальных протоколов. """
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
from datetime import datetime

class ExperimentalProtocolsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Экспериментальные протоколы")
        self.parent.geometry("1100x750")
        
        # Подключение к базе данных
        self.conn = sqlite3.connect('data/microbiology.db')
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.purpose_var = tk.StringVar()
        self.protocol_var = tk.StringVar()
        self.current_purpose = None
        self.current_protocol_id = None
        
        self.create_widgets()
        self.load_purpose_list()
        
    def create_widgets(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка веса строк и столбцов
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=2)
        main_frame.rowconfigure(1, weight=1)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Справочник экспериментальных протоколов", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Цель эксперимента (объединяющий параметр)
        frame1 = ttk.LabelFrame(main_frame, text="1. Цель эксперимента", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для цели
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        purpose_search_var = tk.StringVar()
        purpose_search_var.trace('w', lambda *args: self.filter_purpose_list(purpose_search_var.get()))
        purpose_search = ttk.Entry(search_frame, textvariable=purpose_search_var, width=20)
        purpose_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список целей
        self.purpose_listbox = tk.Listbox(frame1, width=25)
        self.purpose_index_to_id = {}
        self.purpose_listbox.pack(fill=tk.BOTH, expand=True)
        self.purpose_listbox.bind('<<ListboxSelect>>', self.on_purpose_select)
        
        # Кнопки для целей
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_purpose).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_purpose).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Протоколы выбранной цели
        frame2 = ttk.LabelFrame(main_frame, text="2. Протоколы", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для протоколов
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        protocol_search_var = tk.StringVar()
        protocol_search_var.trace('w', lambda *args: self.filter_protocol_list(protocol_search_var.get()))
        protocol_search = ttk.Entry(search_frame2, textvariable=protocol_search_var, width=20)
        protocol_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список протоколов
        self.protocol_listbox = tk.Listbox(frame2)
        self.protocol_index_to_id = {}
        self.protocol_listbox.pack(fill=tk.BOTH, expand=True)
        self.protocol_listbox.bind('<<ListboxSelect>>', self.on_protocol_select)
        
        # Кнопки для протоколов
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_protocol).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_protocol).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранном протоколе
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация о протоколе", padding="10")
        frame3.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # Прокручиваемый фрейм для детальной информации
        detail_canvas = tk.Canvas(frame3)
        scrollbar = ttk.Scrollbar(frame3, orient="vertical", command=detail_canvas.yview)
        self.detail_frame = ttk.Frame(detail_canvas)
        
        detail_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        detail_canvas.pack(side="left", fill="both", expand=True)
        detail_canvas.create_window((0, 0), window=self.detail_frame, anchor="nw")
        
        self.detail_frame.bind("<Configure>", lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")))
        
        # Поля для детальной информации
        self.create_detail_fields()
        
        # Кнопки управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))
        
        ttk.Button(control_frame, text="Сохранить изменения", command=self.save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Очистить форму", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Обновить списки", command=self.refresh_lists).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Закрыть", command=self.parent.destroy).pack(side=tk.RIGHT, padx=5)
        
    def create_detail_fields(self):
        """Создание полей для детальной информации"""
        row = 0
        
        # Цель эксперимента
        ttk.Label(self.detail_frame, text="Цель эксперимента:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.purpose_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.purpose_var)
        self.purpose_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Название протокола
        ttk.Label(self.detail_frame, text="Название протокола:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.protocol_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.protocol_var)
        self.protocol_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Продолжительность
        ttk.Label(self.detail_frame, text="Продолжительность (мин):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.duration_var = tk.IntVar(value=60)
        self.duration_spinbox = ttk.Spinbox(self.detail_frame, from_=1, to=10080, increment=5, 
                                          textvariable=self.duration_var, width=27)
        self.duration_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Уровень сложности
        ttk.Label(self.detail_frame, text="Уровень сложности:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.difficulty_var = tk.StringVar()
        self.difficulty_combo = ttk.Combobox(self.detail_frame, textvariable=self.difficulty_var, width=27,
                                           values=["Начинающий", "Средний", "Продвинутый", "Эксперт"])
        self.difficulty_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Метод разделительной линии
        ttk.Separator(self.detail_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        row += 1
        
        # Пошаговое описание (многострочное)
        ttk.Label(self.detail_frame, text="Пошаговое описание:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(5, 2))
        row += 1
        
        self.steps_text = scrolledtext.ScrolledText(self.detail_frame, width=50, height=8, wrap=tk.WORD)
        self.steps_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        row += 1
        
        # Материалы
        ttk.Label(self.detail_frame, text="Материалы и оборудование:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        row += 1
        
        self.materials_text = scrolledtext.ScrolledText(self.detail_frame, width=50, height=4, wrap=tk.WORD)
        self.materials_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        row += 1
        
        # Формулы расчета
        ttk.Label(self.detail_frame, text="Формулы расчета:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        row += 1
        
        self.formulas_text = scrolledtext.ScrolledText(self.detail_frame, width=50, height=3, wrap=tk.WORD)
        self.formulas_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        row += 1
        
        # Ссылки
        ttk.Label(self.detail_frame, text="Ссылки и примечания:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(10, 2))
        row += 1
        
        self.references_text = scrolledtext.ScrolledText(self.detail_frame, width=50, height=3, wrap=tk.WORD)
        self.references_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_purpose_list(self):
        """Загрузка списка целей экспериментов из базы данных"""
        self.purpose_listbox.delete(0, tk.END)
        self.purpose_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT experiment_purpose FROM experimental_protocols ORDER BY experiment_purpose")
        purposes = self.cursor.fetchall()
        
        for purpose in purposes:
            self.purpose_listbox.insert(tk.END, purpose[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(purposes)} целей экспериментов")
    
    def filter_purpose_list(self, search_text):
        """Фильтрация списка целей"""
        self.purpose_listbox.delete(0, tk.END)
        self.purpose_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT experiment_purpose FROM experimental_protocols WHERE experiment_purpose LIKE ? ORDER BY experiment_purpose", 
                          (f'%{search_text}%',))
        purposes = self.cursor.fetchall()
        
        for purpose in purposes:
            self.purpose_listbox.insert(tk.END, purpose[0])
    
    def on_purpose_select(self, event):
        """Обработка выбора цели"""
        selection = self.purpose_listbox.curselection()
        if not selection:
            return
            
        self.current_purpose = self.purpose_listbox.get(selection[0])
        self.purpose_var.set(self.current_purpose)
        self.load_protocol_list()
    
    def load_protocol_list(self):
        """Загрузка списка протоколов для выбранной цели"""
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if not self.current_purpose:
            return
            
        self.cursor.execute("""
            SELECT id, protocol_name 
            FROM experimental_protocols 
            WHERE experiment_purpose = ? 
            ORDER BY protocol_name
        """, (self.current_purpose,))
        
        protocols = self.cursor.fetchall()
        
        for protocol_id, protocol_name in protocols:
            self.protocol_listbox.insert(tk.END, protocol_name)
            # Сохраняем ID в атрибуте элемента списка
            self.protocol_index_to_id[self.protocol_listbox.size() - 1] = protocol_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(protocols)} протоколов для цели: {self.current_purpose}")
    
    def filter_protocol_list(self, search_text):
        """Фильтрация списка протоколов"""
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if not self.current_purpose:
            return
            
        self.cursor.execute("""
            SELECT id, protocol_name 
            FROM experimental_protocols 
            WHERE experiment_purpose = ? AND protocol_name LIKE ?
            ORDER BY protocol_name
        """, (self.current_purpose, f'%{search_text}%'))
        
        protocols = self.cursor.fetchall()
        
        for protocol_id, protocol_name in protocols:
            self.protocol_listbox.insert(tk.END, protocol_name)
            self.protocol_index_to_id[self.protocol_listbox.size() - 1] = protocol_id
    
    def on_protocol_select(self, event):
        """Обработка выбора протокола"""
        selection = self.protocol_listbox.curselection()
        if not selection:
            return
            
        protocol_id = self.protocol_index_to_id.get(selection[0])
            
        if protocol_id is None:
            
            return
        self.current_protocol_id = protocol_id
        self.load_protocol_details(protocol_id)
    
    def load_protocol_details(self, protocol_id):
        """Загрузка детальной информации о протоколе"""
        self.cursor.execute("""
            SELECT experiment_purpose, protocol_name, step_by_step, materials,
                   calculation_formulas, references, duration_minutes, difficulty_level
            FROM experimental_protocols 
            WHERE id = ?
        """, (protocol_id,))
        
        result = self.cursor.fetchone()
        if result:
            (experiment_purpose, protocol_name, step_by_step, materials,
             calculation_formulas, references, duration_minutes, difficulty_level) = result
            
            self.purpose_var.set(experiment_purpose)
            self.protocol_var.set(protocol_name)
            
            # Очищаем и заполняем текстовые поля
            self.steps_text.delete('1.0', tk.END)
            self.steps_text.insert('1.0', step_by_step if step_by_step else "")
            
            self.materials_text.delete('1.0', tk.END)
            self.materials_text.insert('1.0', materials if materials else "")
            
            self.formulas_text.delete('1.0', tk.END)
            self.formulas_text.insert('1.0', calculation_formulas if calculation_formulas else "")
            
            self.references_text.delete('1.0', tk.END)
            self.references_text.insert('1.0', references if references else "")
            
            self.duration_var.set(duration_minutes if duration_minutes else 60)
            self.difficulty_var.set(difficulty_level if difficulty_level else "Средний")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для протокола: {protocol_name}")
    
    def add_purpose(self):
        """Добавление новой цели эксперимента"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новую цель эксперимента")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название цели эксперимента:").pack(pady=(20, 5))
        purpose_entry = ttk.Entry(dialog, width=40)
        purpose_entry.pack(pady=5)
        purpose_entry.focus_set()
        
        def save_purpose():
            purpose_name = purpose_entry.get().strip()
            if purpose_name:
                # Проверяем, существует ли уже такая цель
                self.cursor.execute("SELECT COUNT(*) FROM experimental_protocols WHERE experiment_purpose = ?", (purpose_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Цель '{purpose_name}' уже существует!")
                else:
                    # Добавляем пример протокола для новой цели
                    self.cursor.execute("""
                        INSERT INTO experimental_protocols (experiment_purpose, protocol_name, step_by_step, duration_minutes, difficulty_level)
                        VALUES (?, 'Новый протокол', '1. Шаг 1\n2. Шаг 2\n3. Шаг 3', 60, 'Средний')
                    """, (purpose_name,))
                    self.conn.commit()
                    self.load_purpose_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название цели эксперимента!")
        
        ttk.Button(dialog, text="Сохранить", command=save_purpose).pack(pady=10)
        
    def delete_purpose(self):
        """Удаление выбранной цели эксперимента"""
        selection = self.purpose_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите цель эксперимента для удаления!")
            return
            
        purpose_name = self.purpose_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить цель '{purpose_name}' и все связанные протоколы?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM experimental_protocols WHERE experiment_purpose = ?", (purpose_name,))
            self.conn.commit()
            self.load_purpose_list()
            self.protocol_listbox.delete(0, tk.END)
            self.protocol_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Цель эксперимента '{purpose_name}' удалена")
    
    def add_protocol(self):
        """Добавление нового протокола"""
        if not self.current_purpose:
            messagebox.showwarning("Внимание", "Сначала выберите цель эксперимента!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новый протокол для цели: {self.current_purpose}")
        dialog.geometry("500x200")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Название протокола:").grid(row=0, column=0, sticky=tk.W, pady=5)
        protocol_entry = ttk.Entry(frame, width=40)
        protocol_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        ttk.Label(frame, text="Уровень сложности:").grid(row=1, column=0, sticky=tk.W, pady=5)
        difficulty_combo = ttk.Combobox(frame, width=37, values=["Начинающий", "Средний", "Продвинутый"])
        difficulty_combo.set("Средний")
        difficulty_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        protocol_entry.focus_set()
        
        def save_protocol():
            protocol_name = protocol_entry.get().strip()
            difficulty = difficulty_combo.get()
            
            if protocol_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO experimental_protocols (experiment_purpose, protocol_name, step_by_step, 
                                                       duration_minutes, difficulty_level)
                    VALUES (?, ?, '1. Опишите шаги протокола\n2. Укажите необходимые материалы\n3. Добавьте формулы расчета', 
                            60, ?)
                """, (self.current_purpose, protocol_name, difficulty))
                
                self.conn.commit()
                self.load_protocol_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлен новый протокол: {protocol_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название протокола!")
        
        ttk.Button(frame, text="Сохранить", command=save_protocol).grid(row=2, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_protocol(self):
        """Удаление выбранного протокола"""
        selection = self.protocol_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите протокол для удаления!")
            return
            
        protocol_id = self.protocol_index_to_id.get(selection[0])
            
        if protocol_id is None:
            
            return
        # Получаем информацию о протоколе для сообщения
        self.cursor.execute("SELECT experiment_purpose, protocol_name FROM experimental_protocols WHERE id = ?", (protocol_id,))
        purpose, protocol_name = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить протокол '{protocol_name}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM experimental_protocols WHERE id = ?", (protocol_id,))
            self.conn.commit()
            self.load_protocol_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Протокол '{protocol_name}' удален")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_protocol_id:
            messagebox.showwarning("Внимание", "Сначала выберите протокол для редактирования!")
            return
            
        # Получаем данные из полей
        purpose = self.purpose_var.get().strip()
        protocol_name = self.protocol_var.get().strip()
        
        if not purpose or not protocol_name:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Цель и Название протокола!")
            return
        
        try:
            # Получаем текст из текстовых полей
            step_by_step = self.steps_text.get('1.0', tk.END).strip()
            materials = self.materials_text.get('1.0', tk.END).strip()
            calculation_formulas = self.formulas_text.get('1.0', tk.END).strip()
            references = self.references_text.get('1.0', tk.END).strip()
            
            # Обновляем запись
            self.cursor.execute("""
                UPDATE experimental_protocols 
                SET experiment_purpose = ?, protocol_name = ?, step_by_step = ?, materials = ?,
                    calculation_formulas = ?, references = ?, duration_minutes = ?, 
                    difficulty_level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                purpose, protocol_name, step_by_step, materials,
                calculation_formulas, references, self.duration_var.get(),
                self.difficulty_var.get(), self.current_protocol_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if purpose != self.current_purpose:
                self.current_purpose = purpose
                self.load_purpose_list()
                # Выделяем обновленную цель в списке
                index = self.purpose_listbox.get(0, tk.END).index(purpose)
                self.purpose_listbox.selection_clear(0, tk.END)
                self.purpose_listbox.selection_set(index)
                self.purpose_listbox.see(index)
            
            self.load_protocol_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для протокола '{protocol_name}' сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.purpose_var.set("")
        self.protocol_var.set("")
        self.duration_var.set(60)
        self.difficulty_var.set("")
        
        # Очищаем текстовые поля
        self.steps_text.delete('1.0', tk.END)
        self.materials_text.delete('1.0', tk.END)
        self.formulas_text.delete('1.0', tk.END)
        self.references_text.delete('1.0', tk.END)
        
        self.current_protocol_id = None
        
        # Снимаем выделение в списках
        self.purpose_listbox.selection_clear(0, tk.END)
        self.protocol_listbox.selection_clear(0, tk.END)
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_purpose_list()
        if self.current_purpose:
            self.load_protocol_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}