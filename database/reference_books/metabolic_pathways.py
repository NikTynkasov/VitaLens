# [file name database/reference_books/culture_media.py]
# Справочник «Метаболические пути/продукты»
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




class ExperimentalProtocolsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Экспериментальные протоколы")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('metabolic_pathways')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.experiment_purpose_var = tk.StringVar()
        self.protocol_name_var = tk.StringVar()
        self.current_experiment_purpose = None
        self.current_protocol_id = None
        
        self.create_widgets()
        self.load_experiment_purpose_list()
        
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
        
        # Поле 1: Цель эксперимента
        frame1 = ttk.LabelFrame(main_frame, text="1. Цель эксперимента", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для цели эксперимента
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        purpose_search_var = tk.StringVar()
        purpose_search_var.trace('w', lambda *args: self.filter_experiment_purpose_list(purpose_search_var.get()))
        purpose_search = ttk.Entry(search_frame, textvariable=purpose_search_var, width=20)
        purpose_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список целей эксперимента
        self.experiment_purpose_listbox = tk.Listbox(frame1, width=25)
        self.experiment_purpose_index_to_id = {}
        self.experiment_purpose_listbox.pack(fill=tk.BOTH, expand=True)
        self.experiment_purpose_listbox.bind('<<ListboxSelect>>', self.on_experiment_purpose_select)
        
        # Кнопки для цели эксперимента
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_experiment_purpose).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_experiment_purpose).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Названия протоколов выбранной цели
        frame2 = ttk.LabelFrame(main_frame, text="2. Названия протоколов", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для названий протоколов
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        protocol_name_search_var = tk.StringVar()
        protocol_name_search_var.trace('w', lambda *args: self.filter_protocol_list(protocol_name_search_var.get()))
        protocol_name_search = ttk.Entry(search_frame2, textvariable=protocol_name_search_var, width=20)
        protocol_name_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список названий протоколов
        self.protocol_listbox = tk.Listbox(frame2)
        self.protocol_index_to_id = {}
        self.protocol_listbox.pack(fill=tk.BOTH, expand=True)
        self.protocol_listbox.bind('<<ListboxSelect>>', self.on_protocol_select)
        
        # Кнопки для названий протоколов
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
        self.experiment_purpose_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.experiment_purpose_var)
        self.experiment_purpose_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Название протокола
        ttk.Label(self.detail_frame, text="Название протокола:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.protocol_name_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.protocol_name_var)
        self.protocol_name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Пошаговое описание
        ttk.Label(self.detail_frame, text="Пошаговое описание:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.step_by_step_text = tk.Text(self.detail_frame, width=30, height=8)
        self.step_by_step_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Материалы
        ttk.Label(self.detail_frame, text="Материалы:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.materials_text = tk.Text(self.detail_frame, width=30, height=5)
        self.materials_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Формулы расчета
        ttk.Label(self.detail_frame, text="Формулы расчета:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.calculation_formulas_text = tk.Text(self.detail_frame, width=30, height=5)
        self.calculation_formulas_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Ссылки
        ttk.Label(self.detail_frame, text="Ссылки:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.references_text = tk.Text(self.detail_frame, width=30, height=4)
        self.references_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Длительность (минуты)
        ttk.Label(self.detail_frame, text="Длительность (минуты):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.duration_minutes_var = tk.IntVar(value=0)
        self.duration_minutes_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=10000, increment=5, 
                                                   textvariable=self.duration_minutes_var, width=27)
        self.duration_minutes_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Уровень сложности
        ttk.Label(self.detail_frame, text="Уровень сложности:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.difficulty_level_var = tk.StringVar()
        self.difficulty_level_combo = ttk.Combobox(self.detail_frame, textvariable=self.difficulty_level_var, width=27,
                                                  values=["Низкий", "Средний", "Высокий", "Экспертный"])
        self.difficulty_level_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_experiment_purpose_list(self):
        """Загрузка списка целей эксперимента из базы данных"""
        self.experiment_purpose_listbox.delete(0, tk.END)
        self.experiment_purpose_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT experiment_purpose FROM experimental_protocols ORDER BY experiment_purpose")
        purposes = self.cursor.fetchall()
        
        for purpose in purposes:
            self.experiment_purpose_listbox.insert(tk.END, purpose[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(purposes)} целей эксперимента")
    
    def filter_experiment_purpose_list(self, search_text):
        """Фильтрация списка целей эксперимента"""
        self.experiment_purpose_listbox.delete(0, tk.END)
        self.experiment_purpose_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT experiment_purpose FROM experimental_protocols WHERE experiment_purpose LIKE ? ORDER BY experiment_purpose", 
                          (f'%{search_text}%',))
        purposes = self.cursor.fetchall()
        
        for purpose in purposes:
            self.experiment_purpose_listbox.insert(tk.END, purpose[0])
    
    def on_experiment_purpose_select(self, event):
        """Обработка выбора цели эксперимента"""
        selection = self.experiment_purpose_listbox.curselection()
        if not selection:
            return
            
        self.current_experiment_purpose = self.experiment_purpose_listbox.get(selection[0])
        self.experiment_purpose_var.set(self.current_experiment_purpose)
        self.load_protocol_list()
    
    def load_protocol_list(self):
        """Загрузка списка протоколов для выбранной цели"""
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if not self.current_experiment_purpose:
            return
            
        self.cursor.execute("""
            SELECT id, protocol_name 
            FROM experimental_protocols 
            WHERE experiment_purpose = ? 
            ORDER BY protocol_name
        """, (self.current_experiment_purpose,))
        
        protocol_list = self.cursor.fetchall()
        
        for protocol_id, protocol_name in protocol_list:
            self.protocol_listbox.insert(tk.END, protocol_name)
            # Сохраняем ID в атрибуте элемента списка
            self.protocol_index_to_id[self.protocol_listbox.size() - 1] = protocol_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(protocol_list)} протоколов для цели {self.current_experiment_purpose}")
    
    def filter_protocol_list(self, search_text):
        """Фильтрация списка протоколов"""
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if not self.current_experiment_purpose:
            return
            
        self.cursor.execute("""
            SELECT id, protocol_name 
            FROM experimental_protocols 
            WHERE experiment_purpose = ? AND protocol_name LIKE ?
            ORDER BY protocol_name
        """, (self.current_experiment_purpose, f'%{search_text}%'))
        
        protocol_list = self.cursor.fetchall()
        
        for protocol_id, protocol_name in protocol_list:
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
            
            self.experiment_purpose_var.set(experiment_purpose)
            self.protocol_name_var.set(protocol_name)
            self.step_by_step_text.delete(1.0, tk.END)
            self.step_by_step_text.insert(1.0, step_by_step if step_by_step else "")
            self.materials_text.delete(1.0, tk.END)
            self.materials_text.insert(1.0, materials if materials else "")
            self.calculation_formulas_text.delete(1.0, tk.END)
            self.calculation_formulas_text.insert(1.0, calculation_formulas if calculation_formulas else "")
            self.references_text.delete(1.0, tk.END)
            self.references_text.insert(1.0, references if references else "")
            self.duration_minutes_var.set(duration_minutes if duration_minutes else 0)
            self.difficulty_level_var.set(difficulty_level if difficulty_level else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для протокола: {protocol_name}")
    
    def add_experiment_purpose(self):
        """Добавление новой цели эксперимента"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новую цель эксперимента")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название цели эксперимента:").pack(pady=(20, 5))
        purpose_entry = ttk.Entry(dialog, width=30)
        purpose_entry.pack(pady=5)
        purpose_entry.focus_set()
        
        def save_experiment_purpose():
            purpose_name = purpose_entry.get().strip()
            if purpose_name:
                # Проверяем, существует ли уже такая цель
                self.cursor.execute("SELECT COUNT(*) FROM experimental_protocols WHERE experiment_purpose = ?", (purpose_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Цель эксперимента '{purpose_name}' уже существует!")
                else:
                    # Добавляем пример записи для новой цели
                    self.cursor.execute("""
                        INSERT INTO experimental_protocols (experiment_purpose, protocol_name, step_by_step, duration_minutes)
                        VALUES (?, 'Пример протокола', 'Шаг 1: ...', 60)
                    """, (purpose_name,))
                    self.conn.commit()
                    self.load_experiment_purpose_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название цели эксперимента!")
        
        ttk.Button(dialog, text="Сохранить", command=save_experiment_purpose).pack(pady=10)
        
    def delete_experiment_purpose(self):
        """Удаление выбранной цели эксперимента"""
        selection = self.experiment_purpose_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите цель эксперимента для удаления!")
            return
            
        purpose_name = self.experiment_purpose_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить цель эксперимента '{purpose_name}' и все связанные протоколы?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM experimental_protocols WHERE experiment_purpose = ?", (purpose_name,))
            self.conn.commit()
            self.load_experiment_purpose_list()
            self.protocol_listbox.delete(0, tk.END)
            self.protocol_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Цель эксперимента '{purpose_name}' удалена")
    
    def add_protocol(self):
        """Добавление нового протокола"""
        if not self.current_experiment_purpose:
            messagebox.showwarning("Внимание", "Сначала выберите цель эксперимента!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новый протокол для цели {self.current_experiment_purpose}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Название протокола:").grid(row=0, column=0, sticky=tk.W, pady=5)
        protocol_name_entry = ttk.Entry(frame, width=30)
        protocol_name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        protocol_name_entry.focus_set()
        
        def save_protocol():
            protocol_name = protocol_name_entry.get().strip()
            
            if protocol_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO experimental_protocols (experiment_purpose, protocol_name, step_by_step, duration_minutes)
                    VALUES (?, ?, 'Шаг 1: ...', 60)
                """, (self.current_experiment_purpose, protocol_name))
                
                self.conn.commit()
                self.load_protocol_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлен новый протокол: {protocol_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название протокола!")
        
        ttk.Button(frame, text="Сохранить", command=save_protocol).grid(row=1, column=0, columnspan=2, pady=20)
        
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
        experiment_purpose, protocol_name = self.cursor.fetchone()
        
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
        experiment_purpose = self.experiment_purpose_var.get().strip()
        protocol_name = self.protocol_name_var.get().strip()
        step_by_step = self.step_by_step_text.get(1.0, tk.END).strip()
        materials = self.materials_text.get(1.0, tk.END).strip()
        calculation_formulas = self.calculation_formulas_text.get(1.0, tk.END).strip()
        references = self.references_text.get(1.0, tk.END).strip()
        duration_minutes = self.duration_minutes_var.get()
        difficulty_level = self.difficulty_level_var.get()
        
        if not experiment_purpose or not protocol_name:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Цель эксперимента и Название протокола!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE experimental_protocols 
                SET experiment_purpose = ?, protocol_name = ?, step_by_step = ?, materials = ?, 
                    calculation_formulas = ?, references = ?, duration_minutes = ?, 
                    difficulty_level = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                experiment_purpose, protocol_name, step_by_step, materials,
                calculation_formulas, references, duration_minutes if duration_minutes > 0 else None,
                difficulty_level if difficulty_level else None,
                self.current_protocol_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if experiment_purpose != self.current_experiment_purpose:
                self.current_experiment_purpose = experiment_purpose
                self.load_experiment_purpose_list()
                # Выделяем обновленную цель в списке
                index = self.experiment_purpose_listbox.get(0, tk.END).index(experiment_purpose)
                self.experiment_purpose_listbox.selection_clear(0, tk.END)
                self.experiment_purpose_listbox.selection_set(index)
                self.experiment_purpose_listbox.see(index)
            
            self.load_protocol_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для протокола {protocol_name} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.experiment_purpose_var.set("")
        self.protocol_name_var.set("")
        self.step_by_step_text.delete(1.0, tk.END)
        self.materials_text.delete(1.0, tk.END)
        self.calculation_formulas_text.delete(1.0, tk.END)
        self.references_text.delete(1.0, tk.END)
        self.duration_minutes_var.set(0)
        self.difficulty_level_var.set("")
        
        self.current_protocol_id = None
        
        # Снимаем выделение в списках
        self.experiment_purpose_listbox.selection_clear(0, tk.END)
        self.protocol_listbox.selection_clear(0, tk.END)
        self.protocol_listbox.delete(0, tk.END)
        self.protocol_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_experiment_purpose_list()
        if self.current_experiment_purpose:
            self.load_protocol_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}