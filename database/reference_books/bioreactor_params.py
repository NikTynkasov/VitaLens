# [file name database/reference_books/culture_media.py]
# Справочник «Параметры биореактора»
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




class BioreactorParamsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Параметры биореактора")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('bioreactor_params')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.system_type_var = tk.StringVar()
        self.configuration_var = tk.StringVar()
        self.current_system_type = None
        self.current_bioreactor_id = None
        
        self.create_widgets()
        self.load_system_type_list()
        
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
        title_label = ttk.Label(main_frame, text="Справочник параметров биореактора", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Тип системы
        frame1 = ttk.LabelFrame(main_frame, text="1. Тип системы", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для типа системы
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        system_type_search_var = tk.StringVar()
        system_type_search_var.trace('w', lambda *args: self.filter_system_type_list(system_type_search_var.get()))
        system_type_search = ttk.Entry(search_frame, textvariable=system_type_search_var, width=20)
        system_type_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список типов систем
        self.system_type_listbox = tk.Listbox(frame1, width=25)
        self.system_type_index_to_id = {}
        self.system_type_listbox.pack(fill=tk.BOTH, expand=True)
        self.system_type_listbox.bind('<<ListboxSelect>>', self.on_system_type_select)
        
        # Кнопки для типа системы
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_system_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_system_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Конфигурации выбранного типа
        frame2 = ttk.LabelFrame(main_frame, text="2. Конфигурации", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для конфигураций
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        configuration_search_var = tk.StringVar()
        configuration_search_var.trace('w', lambda *args: self.filter_configuration_list(configuration_search_var.get()))
        configuration_search = ttk.Entry(search_frame2, textvariable=configuration_search_var, width=20)
        configuration_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список конфигураций
        self.configuration_listbox = tk.Listbox(frame2)
        self.configuration_index_to_id = {}
        self.configuration_listbox.pack(fill=tk.BOTH, expand=True)
        self.configuration_listbox.bind('<<ListboxSelect>>', self.on_configuration_select)
        
        # Кнопки для конфигураций
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_configuration).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_configuration).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранной конфигурации
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация о конфигурации", padding="10")
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
        
        # Тип системы
        ttk.Label(self.detail_frame, text="Тип системы:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.system_type_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.system_type_var)
        self.system_type_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Конфигурация/Название
        ttk.Label(self.detail_frame, text="Конфигурация/Название:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.configuration_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.configuration_var)
        self.configuration_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Объем
        ttk.Label(self.detail_frame, text="Объем (л):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.volume_var = tk.DoubleVar(value=0.0)
        self.volume_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=10000, increment=0.1, 
                                         textvariable=self.volume_var, width=27)
        self.volume_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Площадь
        ttk.Label(self.detail_frame, text="Площадь (м²):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.area_var = tk.DoubleVar(value=0.0)
        self.area_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.01, 
                                       textvariable=self.area_var, width=27)
        self.area_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Скорость перемешивания
        ttk.Label(self.detail_frame, text="Скорость перемешивания (об/мин):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.stirring_speed_var = tk.IntVar(value=0)
        self.stirring_speed_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=5000, increment=10, 
                                                 textvariable=self.stirring_speed_var, width=27)
        self.stirring_speed_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Коэффициент массопереноса
        ttk.Label(self.detail_frame, text="Коэффициент массопереноса (kLa):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.mass_transfer_coefficient_var = tk.DoubleVar(value=0.0)
        self.mass_transfer_coefficient_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.1, 
                                                            textvariable=self.mass_transfer_coefficient_var, width=27)
        self.mass_transfer_coefficient_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Материал
        ttk.Label(self.detail_frame, text="Материал:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.material_var = tk.StringVar()
        self.material_combo = ttk.Combobox(self.detail_frame, textvariable=self.material_var, width=27,
                                          values=["Стекло", "Поликарбонат", "Нержавеющая сталь", 
                                                 "Полипропилен", "Полистирол", "Другой"])
        self.material_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Скорость переноса кислорода
        ttk.Label(self.detail_frame, text="Скорость переноса кислорода:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.oxygen_transfer_rate_var = tk.DoubleVar(value=0.0)
        self.oxygen_transfer_rate_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.1, 
                                                       textvariable=self.oxygen_transfer_rate_var, width=27)
        self.oxygen_transfer_rate_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Описание
        ttk.Label(self.detail_frame, text="Описание:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.description_text = tk.Text(self.detail_frame, width=30, height=5)
        self.description_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_system_type_list(self):
        """Загрузка списка типов систем из базы данных"""
        self.system_type_listbox.delete(0, tk.END)
        self.system_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT system_type FROM bioreactor_params ORDER BY system_type")
        system_types = self.cursor.fetchall()
        
        for system_type in system_types:
            self.system_type_listbox.insert(tk.END, system_type[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(system_types)} типов систем")
    
    def filter_system_type_list(self, search_text):
        """Фильтрация списка типов систем"""
        self.system_type_listbox.delete(0, tk.END)
        self.system_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT system_type FROM bioreactor_params WHERE system_type LIKE ? ORDER BY system_type", 
                          (f'%{search_text}%',))
        system_types = self.cursor.fetchall()
        
        for system_type in system_types:
            self.system_type_listbox.insert(tk.END, system_type[0])
    
    def on_system_type_select(self, event):
        """Обработка выбора типа системы"""
        selection = self.system_type_listbox.curselection()
        if not selection:
            return
            
        self.current_system_type = self.system_type_listbox.get(selection[0])
        self.system_type_var.set(self.current_system_type)
        self.load_configuration_list()
    
    def load_configuration_list(self):
        """Загрузка списка конфигураций для выбранного типа"""
        self.configuration_listbox.delete(0, tk.END)
        self.configuration_index_to_id.clear()
        if not self.current_system_type:
            return
            
        self.cursor.execute("""
            SELECT id, configuration 
            FROM bioreactor_params 
            WHERE system_type = ? 
            ORDER BY configuration
        """, (self.current_system_type,))
        
        configuration_list = self.cursor.fetchall()
        
        for config_id, configuration in configuration_list:
            self.configuration_listbox.insert(tk.END, configuration)
            # Сохраняем ID в атрибуте элемента списка
            self.configuration_index_to_id[self.configuration_listbox.size() - 1] = config_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(configuration_list)} конфигураций для типа {self.current_system_type}")
    
    def filter_configuration_list(self, search_text):
        """Фильтрация списка конфигураций"""
        self.configuration_listbox.delete(0, tk.END)
        self.configuration_index_to_id.clear()
        if not self.current_system_type:
            return
            
        self.cursor.execute("""
            SELECT id, configuration 
            FROM bioreactor_params 
            WHERE system_type = ? AND configuration LIKE ?
            ORDER BY configuration
        """, (self.current_system_type, f'%{search_text}%'))
        
        configuration_list = self.cursor.fetchall()
        
        for config_id, configuration in configuration_list:
            self.configuration_listbox.insert(tk.END, configuration)
            self.configuration_index_to_id[self.configuration_listbox.size() - 1] = config_id
    
    def on_configuration_select(self, event):
        """Обработка выбора конфигурации"""
        selection = self.configuration_listbox.curselection()
        if not selection:
            return
            
        config_id = self.configuration_index_to_id.get(selection[0])
            
        if config_id is None:
            
            return
        self.current_bioreactor_id = config_id
        self.load_bioreactor_details(config_id)
    
    def load_bioreactor_details(self, bioreactor_id):
        """Загрузка детальной информации о биореакторе"""
        self.cursor.execute("""
            SELECT system_type, configuration, volume, area, stirring_speed, 
                   mass_transfer_coefficient, material, oxygen_transfer_rate, description
            FROM bioreactor_params 
            WHERE id = ?
        """, (bioreactor_id,))
        
        result = self.cursor.fetchone()
        if result:
            (system_type, configuration, volume, area, stirring_speed, 
             mass_transfer_coefficient, material, oxygen_transfer_rate, description) = result
            
            self.system_type_var.set(system_type)
            self.configuration_var.set(configuration)
            self.volume_var.set(volume if volume else 0.0)
            self.area_var.set(area if area else 0.0)
            self.stirring_speed_var.set(stirring_speed if stirring_speed else 0)
            self.mass_transfer_coefficient_var.set(mass_transfer_coefficient if mass_transfer_coefficient else 0.0)
            self.material_var.set(material if material else "")
            self.oxygen_transfer_rate_var.set(oxygen_transfer_rate if oxygen_transfer_rate else 0.0)
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, description if description else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для конфигурации: {configuration}")
    
    def add_system_type(self):
        """Добавление нового типа системы"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый тип системы")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название типа системы:").pack(pady=(20, 5))
        system_type_entry = ttk.Entry(dialog, width=30)
        system_type_entry.pack(pady=5)
        system_type_entry.focus_set()
        
        def save_system_type():
            system_type_name = system_type_entry.get().strip()
            if system_type_name:
                # Проверяем, существует ли уже такой тип
                self.cursor.execute("SELECT COUNT(*) FROM bioreactor_params WHERE system_type = ?", (system_type_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Тип системы '{system_type_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового типа
                    self.cursor.execute("""
                        INSERT INTO bioreactor_params (system_type, configuration, volume)
                        VALUES (?, 'Пример конфигурации', 1.0)
                    """, (system_type_name,))
                    self.conn.commit()
                    self.load_system_type_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название типа системы!")
        
        ttk.Button(dialog, text="Сохранить", command=save_system_type).pack(pady=10)
        
    def delete_system_type(self):
        """Удаление выбранного типа системы"""
        selection = self.system_type_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите тип системы для удаления!")
            return
            
        system_type_name = self.system_type_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить тип системы '{system_type_name}' и все связанные конфигурации?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM bioreactor_params WHERE system_type = ?", (system_type_name,))
            self.conn.commit()
            self.load_system_type_list()
            self.configuration_listbox.delete(0, tk.END)
            self.configuration_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Тип системы '{system_type_name}' удален")
    
    def add_configuration(self):
        """Добавление новой конфигурации"""
        if not self.current_system_type:
            messagebox.showwarning("Внимание", "Сначала выберите тип системы!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новую конфигурацию для типа {self.current_system_type}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Конфигурация:").grid(row=0, column=0, sticky=tk.W, pady=5)
        configuration_entry = ttk.Entry(frame, width=30)
        configuration_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        configuration_entry.focus_set()
        
        def save_configuration():
            configuration_name = configuration_entry.get().strip()
            
            if configuration_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO bioreactor_params (system_type, configuration, volume, stirring_speed)
                    VALUES (?, ?, 1.0, 100)
                """, (self.current_system_type, configuration_name))
                
                self.conn.commit()
                self.load_configuration_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлена новая конфигурация: {configuration_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название конфигурации!")
        
        ttk.Button(frame, text="Сохранить", command=save_configuration).grid(row=1, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_configuration(self):
        """Удаление выбранной конфигурации"""
        selection = self.configuration_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите конфигурацию для удаления!")
            return
            
        config_id = self.configuration_index_to_id.get(selection[0])
            
        if config_id is None:
            
            return
        # Получаем информацию о конфигурации для сообщения
        self.cursor.execute("SELECT system_type, configuration FROM bioreactor_params WHERE id = ?", (config_id,))
        system_type, configuration = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить конфигурацию '{configuration}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM bioreactor_params WHERE id = ?", (config_id,))
            self.conn.commit()
            self.load_configuration_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Конфигурация '{configuration}' удалена")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_bioreactor_id:
            messagebox.showwarning("Внимание", "Сначала выберите конфигурацию для редактирования!")
            return
            
        # Получаем данные из полей
        system_type = self.system_type_var.get().strip()
        configuration = self.configuration_var.get().strip()
        volume = self.volume_var.get()
        area = self.area_var.get()
        stirring_speed = self.stirring_speed_var.get()
        mass_transfer_coefficient = self.mass_transfer_coefficient_var.get()
        material = self.material_var.get()
        oxygen_transfer_rate = self.oxygen_transfer_rate_var.get()
        description = self.description_text.get(1.0, tk.END).strip()
        
        if not system_type or not configuration:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Тип системы и Конфигурация!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE bioreactor_params 
                SET system_type = ?, configuration = ?, volume = ?, area = ?, 
                    stirring_speed = ?, mass_transfer_coefficient = ?, material = ?, 
                    oxygen_transfer_rate = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                system_type, configuration, volume if volume > 0 else None,
                area if area > 0 else None, stirring_speed if stirring_speed > 0 else None,
                mass_transfer_coefficient if mass_transfer_coefficient > 0 else None,
                material if material else None,
                oxygen_transfer_rate if oxygen_transfer_rate > 0 else None,
                description,
                self.current_bioreactor_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if system_type != self.current_system_type:
                self.current_system_type = system_type
                self.load_system_type_list()
                # Выделяем обновленный тип в списке
                index = self.system_type_listbox.get(0, tk.END).index(system_type)
                self.system_type_listbox.selection_clear(0, tk.END)
                self.system_type_listbox.selection_set(index)
                self.system_type_listbox.see(index)
            
            self.load_configuration_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для конфигурации {configuration} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.system_type_var.set("")
        self.configuration_var.set("")
        self.volume_var.set(0.0)
        self.area_var.set(0.0)
        self.stirring_speed_var.set(0)
        self.mass_transfer_coefficient_var.set(0.0)
        self.material_var.set("")
        self.oxygen_transfer_rate_var.set(0.0)
        self.description_text.delete(1.0, tk.END)
        
        self.current_bioreactor_id = None
        
        # Снимаем выделение в списках
        self.system_type_listbox.selection_clear(0, tk.END)
        self.configuration_listbox.selection_clear(0, tk.END)
        self.configuration_listbox.delete(0, tk.END)
        self.configuration_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_system_type_list()
        if self.current_system_type:
            self.load_configuration_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}