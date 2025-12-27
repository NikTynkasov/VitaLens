# [file database/reference_books/substances.py]
# Справочник «Вещества-компоненты»
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




class SubstancesWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Вещества-компоненты")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('substances')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.substance_class_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.current_substance_class = None
        self.current_substance_id = None
        
        self.create_widgets()
        self.load_substance_class_list()
        
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
        title_label = ttk.Label(main_frame, text="Справочник веществ-компонентов", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Класс вещества
        frame1 = ttk.LabelFrame(main_frame, text="1. Класс вещества", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для класса вещества
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        class_search_var = tk.StringVar()
        class_search_var.trace('w', lambda *args: self.filter_substance_class_list(class_search_var.get()))
        class_search = ttk.Entry(search_frame, textvariable=class_search_var, width=20)
        class_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список классов веществ
        self.substance_class_listbox = tk.Listbox(frame1, width=25)
        self.substance_class_index_to_id = {}
        self.substance_class_listbox.pack(fill=tk.BOTH, expand=True)
        self.substance_class_listbox.bind('<<ListboxSelect>>', self.on_substance_class_select)
        
        # Кнопки для класса вещества
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_substance_class).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_substance_class).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Названия веществ выбранного класса
        frame2 = ttk.LabelFrame(main_frame, text="2. Названия веществ", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для названий веществ
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        name_search_var = tk.StringVar()
        name_search_var.trace('w', lambda *args: self.filter_substance_list(name_search_var.get()))
        name_search = ttk.Entry(search_frame2, textvariable=name_search_var, width=20)
        name_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список названий веществ
        self.substance_listbox = tk.Listbox(frame2)
        self.substance_index_to_id = {}
        self.substance_listbox.pack(fill=tk.BOTH, expand=True)
        self.substance_listbox.bind('<<ListboxSelect>>', self.on_substance_select)
        
        # Кнопки для названий веществ
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_substance).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_substance).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранном веществе
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация о веществе", padding="10")
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
        
        # Класс вещества
        ttk.Label(self.detail_frame, text="Класс вещества:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.substance_class_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.substance_class_var)
        self.substance_class_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Название вещества
        ttk.Label(self.detail_frame, text="Название:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.name_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.name_var)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Формула
        ttk.Label(self.detail_frame, text="Химическая формула:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.formula_var = tk.StringVar()
        self.formula_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.formula_var)
        self.formula_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Молекулярная масса
        ttk.Label(self.detail_frame, text="Молекулярная масса (г/моль):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.molecular_weight_var = tk.DoubleVar()
        self.molecular_weight_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=10000, increment=0.1, 
                                                   textvariable=self.molecular_weight_var, width=27)
        self.molecular_weight_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Растворимость
        ttk.Label(self.detail_frame, text="Растворимость (г/л):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.solubility_var = tk.DoubleVar()
        self.solubility_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.1, 
                                             textvariable=self.solubility_var, width=27)
        self.solubility_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Энергетическая ценность
        ttk.Label(self.detail_frame, text="Энергетическая ценность (кДж/г):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.energy_value_var = tk.DoubleVar()
        self.energy_value_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=100, increment=0.1, 
                                               textvariable=self.energy_value_var, width=27)
        self.energy_value_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Токсичная концентрация
        ttk.Label(self.detail_frame, text="Токсичная концентрация (г/л):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.toxic_concentration_var = tk.DoubleVar()
        self.toxic_concentration_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.1, 
                                                      textvariable=self.toxic_concentration_var, width=27)
        self.toxic_concentration_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Описание
        ttk.Label(self.detail_frame, text="Описание:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.description_text = tk.Text(self.detail_frame, width=30, height=5)
        self.description_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_substance_class_list(self):
        """Загрузка списка классов веществ из базы данных"""
        self.substance_class_listbox.delete(0, tk.END)
        self.substance_class_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT substance_class FROM substances ORDER BY substance_class")
        substance_classes = self.cursor.fetchall()
        
        for substance_class in substance_classes:
            self.substance_class_listbox.insert(tk.END, substance_class[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(substance_classes)} классов веществ")
    
    def filter_substance_class_list(self, search_text):
        """Фильтрация списка классов веществ"""
        self.substance_class_listbox.delete(0, tk.END)
        self.substance_class_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT substance_class FROM substances WHERE substance_class LIKE ? ORDER BY substance_class", 
                          (f'%{search_text}%',))
        substance_classes = self.cursor.fetchall()
        
        for substance_class in substance_classes:
            self.substance_class_listbox.insert(tk.END, substance_class[0])
    
    def on_substance_class_select(self, event):
        """Обработка выбора класса вещества"""
        selection = self.substance_class_listbox.curselection()
        if not selection:
            return
            
        self.current_substance_class = self.substance_class_listbox.get(selection[0])
        self.substance_class_var.set(self.current_substance_class)
        self.load_substance_list()
    
    def load_substance_list(self):
        """Загрузка списка веществ для выбранного класса"""
        self.substance_listbox.delete(0, tk.END)
        self.substance_index_to_id.clear()
        if not self.current_substance_class:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM substances 
            WHERE substance_class = ? 
            ORDER BY name
        """, (self.current_substance_class,))
        
        substance_list = self.cursor.fetchall()
        
        for substance_id, name in substance_list:
            self.substance_listbox.insert(tk.END, name)
            # Сохраняем ID в атрибуте элемента списка
            self.substance_index_to_id[self.substance_listbox.size() - 1] = substance_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(substance_list)} веществ для класса {self.current_substance_class}")
    
    def filter_substance_list(self, search_text):
        """Фильтрация списка веществ"""
        self.substance_listbox.delete(0, tk.END)
        self.substance_index_to_id.clear()
        if not self.current_substance_class:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM substances 
            WHERE substance_class = ? AND name LIKE ?
            ORDER BY name
        """, (self.current_substance_class, f'%{search_text}%'))
        
        substance_list = self.cursor.fetchall()
        
        for substance_id, name in substance_list:
            self.substance_listbox.insert(tk.END, name)
            self.substance_index_to_id[self.substance_listbox.size() - 1] = substance_id
    
    def on_substance_select(self, event):
        """Обработка выбора вещества"""
        selection = self.substance_listbox.curselection()
        if not selection:
            return
            
        substance_id = self.substance_index_to_id.get(selection[0])
            
        if substance_id is None:
            
            return
        self.current_substance_id = substance_id
        self.load_substance_details(substance_id)
    
    def load_substance_details(self, substance_id):
        """Загрузка детальной информации о веществе"""
        self.cursor.execute("""
            SELECT substance_class, name, formula, molecular_weight, solubility, 
                   energy_value, toxic_concentration, description
            FROM substances 
            WHERE id = ?
        """, (substance_id,))
        
        result = self.cursor.fetchone()
        if result:
            (substance_class, name, formula, molecular_weight, solubility, 
             energy_value, toxic_concentration, description) = result
            
            self.substance_class_var.set(substance_class)
            self.name_var.set(name)
            self.formula_var.set(formula if formula else "")
            self.molecular_weight_var.set(molecular_weight if molecular_weight else 0.0)
            self.solubility_var.set(solubility if solubility else 0.0)
            self.energy_value_var.set(energy_value if energy_value else 0.0)
            self.toxic_concentration_var.set(toxic_concentration if toxic_concentration else 0.0)
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, description if description else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для вещества: {name}")
    
    def add_substance_class(self):
        """Добавление нового класса вещества"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый класс вещества")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название класса вещества:").pack(pady=(20, 5))
        class_entry = ttk.Entry(dialog, width=30)
        class_entry.pack(pady=5)
        class_entry.focus_set()
        
        def save_substance_class():
            class_name = class_entry.get().strip()
            if class_name:
                # Проверяем, существует ли уже такой класс
                self.cursor.execute("SELECT COUNT(*) FROM substances WHERE substance_class = ?", (class_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Класс вещества '{class_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового класса
                    self.cursor.execute("""
                        INSERT INTO substances (substance_class, name, molecular_weight)
                        VALUES (?, 'Пример вещества', 100.0)
                    """, (class_name,))
                    self.conn.commit()
                    self.load_substance_class_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название класса вещества!")
        
        ttk.Button(dialog, text="Сохранить", command=save_substance_class).pack(pady=10)
        
    def delete_substance_class(self):
        """Удаление выбранного класса вещества"""
        selection = self.substance_class_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите класс вещества для удаления!")
            return
            
        class_name = self.substance_class_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить класс вещества '{class_name}' и все связанные вещества?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM substances WHERE substance_class = ?", (class_name,))
            self.conn.commit()
            self.load_substance_class_list()
            self.substance_listbox.delete(0, tk.END)
            self.substance_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Класс вещества '{class_name}' удален")
    
    def add_substance(self):
        """Добавление нового вещества"""
        if not self.current_substance_class:
            messagebox.showwarning("Внимание", "Сначала выберите класс вещества!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новое вещество для класса {self.current_substance_class}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Название вещества:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        name_entry.focus_set()
        
        def save_substance():
            substance_name = name_entry.get().strip()
            
            if substance_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO substances (substance_class, name, molecular_weight, solubility)
                    VALUES (?, ?, 100.0, 10.0)
                """, (self.current_substance_class, substance_name))
                
                self.conn.commit()
                self.load_substance_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлено новое вещество: {substance_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название вещества!")
        
        ttk.Button(frame, text="Сохранить", command=save_substance).grid(row=1, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_substance(self):
        """Удаление выбранного вещества"""
        selection = self.substance_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите вещество для удаления!")
            return
            
        substance_id = self.substance_index_to_id.get(selection[0])
            
        if substance_id is None:
            
            return
        # Получаем информацию о веществе для сообщения
        self.cursor.execute("SELECT substance_class, name FROM substances WHERE id = ?", (substance_id,))
        substance_class, name = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить вещество '{name}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM substances WHERE id = ?", (substance_id,))
            self.conn.commit()
            self.load_substance_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Вещество '{name}' удалено")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_substance_id:
            messagebox.showwarning("Внимание", "Сначала выберите вещество для редактирования!")
            return
            
        # Получаем данные из полей
        substance_class = self.substance_class_var.get().strip()
        name = self.name_var.get().strip()
        formula = self.formula_var.get().strip()
        molecular_weight = self.molecular_weight_var.get()
        solubility = self.solubility_var.get()
        energy_value = self.energy_value_var.get()
        toxic_concentration = self.toxic_concentration_var.get()
        description = self.description_text.get(1.0, tk.END).strip()
        
        if not substance_class or not name:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Класс вещества и Название!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE substances 
                SET substance_class = ?, name = ?, formula = ?, molecular_weight = ?, 
                    solubility = ?, energy_value = ?, toxic_concentration = ?, 
                    description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                substance_class, name, formula if formula else None, 
                molecular_weight if molecular_weight > 0 else None,
                solubility if solubility > 0 else None,
                energy_value if energy_value > 0 else None,
                toxic_concentration if toxic_concentration > 0 else None,
                description,
                self.current_substance_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if substance_class != self.current_substance_class:
                self.current_substance_class = substance_class
                self.load_substance_class_list()
                # Выделяем обновленный класс в списке
                index = self.substance_class_listbox.get(0, tk.END).index(substance_class)
                self.substance_class_listbox.selection_clear(0, tk.END)
                self.substance_class_listbox.selection_set(index)
                self.substance_class_listbox.see(index)
            
            self.load_substance_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для вещества {name} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.substance_class_var.set("")
        self.name_var.set("")
        self.formula_var.set("")
        self.molecular_weight_var.set(0.0)
        self.solubility_var.set(0.0)
        self.energy_value_var.set(0.0)
        self.toxic_concentration_var.set(0.0)
        self.description_text.delete(1.0, tk.END)
        
        self.current_substance_id = None
        
        # Снимаем выделение в списках
        self.substance_class_listbox.selection_clear(0, tk.END)
        self.substance_listbox.selection_clear(0, tk.END)
        self.substance_listbox.delete(0, tk.END)
        self.substance_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_substance_class_list()
        if self.current_substance_class:
            self.load_substance_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}