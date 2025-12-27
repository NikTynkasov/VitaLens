# [file name database/reference_books/culture_media.py ]
# Справочник «Типы взаимодействий»
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
from pathlib import Path

def _project_root() -> Path:
    # database/reference_books/<file>.py -> reference_books -> database -> project root
    return Path(__file__).resolve().parents[2]

def _list_tables(db_path: Path) -> set[str]:
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return {r[0] for r in cur.fetchall()}
        finally:
            conn.close()
    except Exception:
        return set()

def _score_db(db_path: Path, required_table: str) -> int:
    if not db_path.exists() or not db_path.is_file():
        return -1
    tables = _list_tables(db_path)
    if not tables:
        return 0
    score = 0
    if required_table in tables:
        score += 1000
    # бонусы за соседние таблицы
    for t in ("microorganisms", "culture_media", "substances", "interactions"):
        if t in tables:
            score += 50
    return score

def get_db_path(required_table: str) -> str:
    """Выбирает microbiology.db с нужной таблицей; иначе возвращает <root>/data/microbiology.db."""
    env = os.getenv("MICROBIOLOGY_DB_PATH")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))

    root = _project_root()
    candidates.extend([
        root / "data" / "microbiology.db",
        root / "microbiology.db",
        root / "database" / "data" / "microbiology.db",
        root / "data" / "db" / "microbiology.db",
    ])

    try:
        for p in root.rglob("microbiology.db"):
            candidates.append(p)
    except Exception:
        pass

    # дедуп
    uniq: list[Path] = []
    seen = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)

    best = None
    best_score = -1
    for p in uniq:
        s = _score_db(p, required_table)
        if s > best_score:
            best_score = s
            best = p

    if best is not None and best_score > 0:
        return str(best)

    # default
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "microbiology.db")


def _ensure_db_initialized(db_path: str) -> None:
    """Безопасно инициализирует БД перед чтением/записью."""
    try:
        # если модуль в пакете database.reference_books
        from ..database import ensure_database
    except Exception:
        try:
            from database.database import ensure_database
        except Exception:
            try:
                from database import ensure_database
            except Exception:
                ensure_database = None  # type: ignore

    if ensure_database:
        try:
            ensure_database(db_path)
        except Exception:
            # Не блокируем UI, если инициализация не удалась здесь.
            pass




class InteractionsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Типы взаимодействий")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('interactions')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.base_type_var = tk.StringVar()
        self.mechanism_var = tk.StringVar()
        self.current_base_type = None
        self.current_interaction_id = None
        
        self.create_widgets()
        self.load_base_type_list()
        
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
        title_label = ttk.Label(main_frame, text="Справочник типов взаимодействий", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Базовый тип
        frame1 = ttk.LabelFrame(main_frame, text="1. Базовый тип", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для базового типа
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        base_type_search_var = tk.StringVar()
        base_type_search_var.trace('w', lambda *args: self.filter_base_type_list(base_type_search_var.get()))
        base_type_search = ttk.Entry(search_frame, textvariable=base_type_search_var, width=20)
        base_type_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список базовых типов
        self.base_type_listbox = tk.Listbox(frame1, width=25)
        self.base_type_index_to_id = {}
        self.base_type_listbox.pack(fill=tk.BOTH, expand=True)
        self.base_type_listbox.bind('<<ListboxSelect>>', self.on_base_type_select)
        
        # Кнопки для базового типа
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_base_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_base_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Механизмы выбранного типа
        frame2 = ttk.LabelFrame(main_frame, text="2. Механизмы", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для механизмов
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        mechanism_search_var = tk.StringVar()
        mechanism_search_var.trace('w', lambda *args: self.filter_mechanism_list(mechanism_search_var.get()))
        mechanism_search = ttk.Entry(search_frame2, textvariable=mechanism_search_var, width=20)
        mechanism_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список механизмов
        self.mechanism_listbox = tk.Listbox(frame2)
        self.mechanism_index_to_id = {}
        self.mechanism_listbox.pack(fill=tk.BOTH, expand=True)
        self.mechanism_listbox.bind('<<ListboxSelect>>', self.on_mechanism_select)
        
        # Кнопки для механизмов
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_mechanism).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_mechanism).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранном механизме
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация о механизме", padding="10")
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
        
        # Базовый тип
        ttk.Label(self.detail_frame, text="Базовый тип:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.base_type_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.base_type_var)
        self.base_type_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Механизм
        ttk.Label(self.detail_frame, text="Механизм:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.mechanism_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.mechanism_var)
        self.mechanism_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Описание
        ttk.Label(self.detail_frame, text="Описание:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.description_text = tk.Text(self.detail_frame, width=30, height=5)
        self.description_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Математическая модель
        ttk.Label(self.detail_frame, text="Математическая модель:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.mathematical_model_text = tk.Text(self.detail_frame, width=30, height=5)
        self.mathematical_model_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Коэффициент альфа
        ttk.Label(self.detail_frame, text="Коэффициент α:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.alpha_coefficient_var = tk.DoubleVar(value=0.0)
        self.alpha_coefficient_spinbox = ttk.Spinbox(self.detail_frame, from_=-10, to=10, increment=0.01, 
                                                     textvariable=self.alpha_coefficient_var, width=27)
        self.alpha_coefficient_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Коэффициент бета
        ttk.Label(self.detail_frame, text="Коэффициент β:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.beta_coefficient_var = tk.DoubleVar(value=0.0)
        self.beta_coefficient_spinbox = ttk.Spinbox(self.detail_frame, from_=-10, to=10, increment=0.01, 
                                                    textvariable=self.beta_coefficient_var, width=27)
        self.beta_coefficient_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Эффект расстояния
        ttk.Label(self.detail_frame, text="Эффект расстояния:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.distance_effect_text = tk.Text(self.detail_frame, width=30, height=3)
        self.distance_effect_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_base_type_list(self):
        """Загрузка списка базовых типов из базы данных"""
        self.base_type_listbox.delete(0, tk.END)
        self.base_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT base_type FROM interactions ORDER BY base_type")
        base_types = self.cursor.fetchall()
        
        for base_type in base_types:
            self.base_type_listbox.insert(tk.END, base_type[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(base_types)} базовых типов взаимодействий")
    
    def filter_base_type_list(self, search_text):
        """Фильтрация списка базовых типов"""
        self.base_type_listbox.delete(0, tk.END)
        self.base_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT base_type FROM interactions WHERE base_type LIKE ? ORDER BY base_type", 
                          (f'%{search_text}%',))
        base_types = self.cursor.fetchall()
        
        for base_type in base_types:
            self.base_type_listbox.insert(tk.END, base_type[0])
    
    def on_base_type_select(self, event):
        """Обработка выбора базового типа"""
        selection = self.base_type_listbox.curselection()
        if not selection:
            return
            
        self.current_base_type = self.base_type_listbox.get(selection[0])
        self.base_type_var.set(self.current_base_type)
        self.load_mechanism_list()
    
    def load_mechanism_list(self):
        """Загрузка списка механизмов для выбранного типа"""
        self.mechanism_listbox.delete(0, tk.END)
        self.mechanism_index_to_id.clear()
        if not self.current_base_type:
            return
            
        self.cursor.execute("""
            SELECT id, mechanism 
            FROM interactions 
            WHERE base_type = ? 
            ORDER BY mechanism
        """, (self.current_base_type,))
        
        mechanism_list = self.cursor.fetchall()
        
        for mechanism_id, mechanism in mechanism_list:
            self.mechanism_listbox.insert(tk.END, mechanism)
            # Сохраняем ID в атрибуте элемента списка
            self.mechanism_index_to_id[self.mechanism_listbox.size() - 1] = mechanism_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(mechanism_list)} механизмов для типа {self.current_base_type}")
    
    def filter_mechanism_list(self, search_text):
        """Фильтрация списка механизмов"""
        self.mechanism_listbox.delete(0, tk.END)
        self.mechanism_index_to_id.clear()
        if not self.current_base_type:
            return
            
        self.cursor.execute("""
            SELECT id, mechanism 
            FROM interactions 
            WHERE base_type = ? AND mechanism LIKE ?
            ORDER BY mechanism
        """, (self.current_base_type, f'%{search_text}%'))
        
        mechanism_list = self.cursor.fetchall()
        
        for mechanism_id, mechanism in mechanism_list:
            self.mechanism_listbox.insert(tk.END, mechanism)
            self.mechanism_index_to_id[self.mechanism_listbox.size() - 1] = mechanism_id
    
    def on_mechanism_select(self, event):
        """Обработка выбора механизма"""
        selection = self.mechanism_listbox.curselection()
        if not selection:
            return
            
        mechanism_id = self.mechanism_index_to_id.get(selection[0])
            
        if mechanism_id is None:
            
            return
        self.current_interaction_id = mechanism_id
        self.load_interaction_details(mechanism_id)
    
    def load_interaction_details(self, interaction_id):
        """Загрузка детальной информации о взаимодействии"""
        self.cursor.execute("""
            SELECT base_type, mechanism, description, mathematical_model, 
                   alpha_coefficient, beta_coefficient, distance_effect
            FROM interactions 
            WHERE id = ?
        """, (interaction_id,))
        
        result = self.cursor.fetchone()
        if result:
            (base_type, mechanism, description, mathematical_model, 
             alpha_coefficient, beta_coefficient, distance_effect) = result
            
            self.base_type_var.set(base_type)
            self.mechanism_var.set(mechanism)
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, description if description else "")
            self.mathematical_model_text.delete(1.0, tk.END)
            self.mathematical_model_text.insert(1.0, mathematical_model if mathematical_model else "")
            self.alpha_coefficient_var.set(alpha_coefficient if alpha_coefficient else 0.0)
            self.beta_coefficient_var.set(beta_coefficient if beta_coefficient else 0.0)
            self.distance_effect_text.delete(1.0, tk.END)
            self.distance_effect_text.insert(1.0, distance_effect if distance_effect else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для механизма: {mechanism}")
    
    def add_base_type(self):
        """Добавление нового базового типа"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый базовый тип")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название базового типа:").pack(pady=(20, 5))
        base_type_entry = ttk.Entry(dialog, width=30)
        base_type_entry.pack(pady=5)
        base_type_entry.focus_set()
        
        def save_base_type():
            base_type_name = base_type_entry.get().strip()
            if base_type_name:
                # Проверяем, существует ли уже такой тип
                self.cursor.execute("SELECT COUNT(*) FROM interactions WHERE base_type = ?", (base_type_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Базовый тип '{base_type_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового типа
                    self.cursor.execute("""
                        INSERT INTO interactions (base_type, mechanism, description)
                        VALUES (?, 'Пример механизма', 'Описание примера')
                    """, (base_type_name,))
                    self.conn.commit()
                    self.load_base_type_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название базового типа!")
        
        ttk.Button(dialog, text="Сохранить", command=save_base_type).pack(pady=10)
        
    def delete_base_type(self):
        """Удаление выбранного базового типа"""
        selection = self.base_type_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите базовый тип для удаления!")
            return
            
        base_type_name = self.base_type_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить базовый тип '{base_type_name}' и все связанные механизмы?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM interactions WHERE base_type = ?", (base_type_name,))
            self.conn.commit()
            self.load_base_type_list()
            self.mechanism_listbox.delete(0, tk.END)
            self.mechanism_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Базовый тип '{base_type_name}' удален")
    
    def add_mechanism(self):
        """Добавление нового механизма"""
        if not self.current_base_type:
            messagebox.showwarning("Внимание", "Сначала выберите базовый тип!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новый механизм для типа {self.current_base_type}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Механизм:").grid(row=0, column=0, sticky=tk.W, pady=5)
        mechanism_entry = ttk.Entry(frame, width=30)
        mechanism_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        mechanism_entry.focus_set()
        
        def save_mechanism():
            mechanism_name = mechanism_entry.get().strip()
            
            if mechanism_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO interactions (base_type, mechanism, description, alpha_coefficient, beta_coefficient)
                    VALUES (?, ?, 'Описание механизма', 0.0, 0.0)
                """, (self.current_base_type, mechanism_name))
                
                self.conn.commit()
                self.load_mechanism_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлен новый механизм: {mechanism_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название механизма!")
        
        ttk.Button(frame, text="Сохранить", command=save_mechanism).grid(row=1, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_mechanism(self):
        """Удаление выбранного механизма"""
        selection = self.mechanism_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите механизм для удаления!")
            return
            
        mechanism_id = self.mechanism_index_to_id.get(selection[0])
            
        if mechanism_id is None:
            
            return
        # Получаем информацию о механизме для сообщения
        self.cursor.execute("SELECT base_type, mechanism FROM interactions WHERE id = ?", (mechanism_id,))
        base_type, mechanism = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить механизм '{mechanism}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM interactions WHERE id = ?", (mechanism_id,))
            self.conn.commit()
            self.load_mechanism_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Механизм '{mechanism}' удален")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_interaction_id:
            messagebox.showwarning("Внимание", "Сначала выберите механизм для редактирования!")
            return
            
        # Получаем данные из полей
        base_type = self.base_type_var.get().strip()
        mechanism = self.mechanism_var.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        mathematical_model = self.mathematical_model_text.get(1.0, tk.END).strip()
        alpha_coefficient = self.alpha_coefficient_var.get()
        beta_coefficient = self.beta_coefficient_var.get()
        distance_effect = self.distance_effect_text.get(1.0, tk.END).strip()
        
        if not base_type or not mechanism:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Базовый тип и Механизм!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE interactions 
                SET base_type = ?, mechanism = ?, description = ?, mathematical_model = ?, 
                    alpha_coefficient = ?, beta_coefficient = ?, distance_effect = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                base_type, mechanism, description, mathematical_model,
                alpha_coefficient, beta_coefficient, distance_effect,
                self.current_interaction_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if base_type != self.current_base_type:
                self.current_base_type = base_type
                self.load_base_type_list()
                # Выделяем обновленный тип в списке
                index = self.base_type_listbox.get(0, tk.END).index(base_type)
                self.base_type_listbox.selection_clear(0, tk.END)
                self.base_type_listbox.selection_set(index)
                self.base_type_listbox.see(index)
            
            self.load_mechanism_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для механизма {mechanism} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.base_type_var.set("")
        self.mechanism_var.set("")
        self.description_text.delete(1.0, tk.END)
        self.mathematical_model_text.delete(1.0, tk.END)
        self.alpha_coefficient_var.set(0.0)
        self.beta_coefficient_var.set(0.0)
        self.distance_effect_text.delete(1.0, tk.END)
        
        self.current_interaction_id = None
        
        # Снимаем выделение в списках
        self.base_type_listbox.selection_clear(0, tk.END)
        self.mechanism_listbox.selection_clear(0, tk.END)
        self.mechanism_listbox.delete(0, tk.END)
        self.mechanism_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_base_type_list()
        if self.current_base_type:
            self.load_mechanism_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}