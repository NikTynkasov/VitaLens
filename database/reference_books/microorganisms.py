# [file database/reference_books/microorganisms.py]
# Справочник: Микроорганизмы
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import io
import requests
import threading
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk, ImageOps
import urllib.request
from urllib.parse import quote
import webbrowser

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

class MicroorganismImageManager:
    """Менеджер изображений микроорганизмов"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
        self.cursor = db_connection.cursor()
        
        # Создаем таблицу для изображений, если ее нет
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS microorganism_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                microorganism_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                image_type TEXT NOT NULL, -- 'photo', 'diagram', 'microscopy'
                source TEXT, -- 'local', 'web'
                description TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (microorganism_id) REFERENCES microorganisms (id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()
        
        # Папка для хранения изображений
        self.images_dir = _project_root() / "data" / "microorganism_images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def save_image(self, microorganism_id, image_path, image_type='photo', source='local', description=''):
        """Сохранение информации об изображении в БД"""
        try:
            # Копируем файл в папку images_dir, если это локальный файл
            if source == 'local' and os.path.exists(image_path):
                # Генерируем уникальное имя файла
                ext = os.path.splitext(image_path)[1]
                new_filename = f"{microorganism_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                new_path = self.images_dir / new_filename
                
                # Копируем файл
                with open(image_path, 'rb') as src, open(new_path, 'wb') as dst:
                    dst.write(src.read())
                
                image_path = str(new_path)
            
            self.cursor.execute("""
                INSERT INTO microorganism_images (microorganism_id, image_path, image_type, source, description)
                VALUES (?, ?, ?, ?, ?)
            """, (microorganism_id, image_path, image_type, source, description))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка сохранения изображения: {e}")
            return False
    
    def get_images(self, microorganism_id):
        """Получение всех изображений для микроорганизма"""
        self.cursor.execute("""
            SELECT id, image_path, image_type, source, description, upload_date
            FROM microorganism_images 
            WHERE microorganism_id = ?
            ORDER BY upload_date DESC
        """, (microorganism_id,))
        return self.cursor.fetchall()
    
    def delete_image(self, image_id):
        """Удаление изображения"""
        try:
            # Получаем путь к файлу
            self.cursor.execute("SELECT image_path, source FROM microorganism_images WHERE id = ?", (image_id,))
            result = self.cursor.fetchone()
            
            if result:
                image_path, source = result
                # Удаляем файл, если он локальный
                if source == 'local' and os.path.exists(image_path):
                    os.remove(image_path)
                
                # Удаляем запись из БД
                self.cursor.execute("DELETE FROM microorganism_images WHERE id = ?", (image_id,))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Ошибка удаления изображения: {e}")
        return False
    
    def search_web_images(self, genus, species):
        """Поиск изображений в интернете (возвращает ссылки)"""
        search_queries = [
            f"{genus} {species} microscope",
            f"{genus} {species} bacteria",
            f"{genus} {species} microorganism",
            f"{species} bacteria"
        ]
        
        # Используем Google Images или другой источник
        # Это упрощенная версия, в реальном приложении нужно использовать API
        return search_queries
    
    def download_image_from_url(self, url, microorganism_id, description=''):
        """Скачивание изображения по URL"""
        try:
            # Генерируем имя файла
            ext = '.jpg'  # По умолчанию
            if '.png' in url.lower():
                ext = '.png'
            elif '.gif' in url.lower():
                ext = '.gif'
            
            filename = f"{microorganism_id}_web_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            filepath = self.images_dir / filename
            
            # Скачиваем изображение
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                with open(filepath, 'wb') as f:
                    f.write(response.read())
            
            # Сохраняем в БД
            return self.save_image(microorganism_id, str(filepath), 'photo', 'web', description)
        except Exception as e:
            print(f"Ошибка скачивания изображения: {e}")
            return False

class MicroorganismsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Микроорганизмы")
        self.parent.geometry("1400x800")  # Увеличили окно для изображений
        
        # Отладочная информация
        print(f"Инициализация справочника микроорганизмов.")
        
        try:
            # Подключение к базе данных
            db_path = get_db_path('microorganisms')
            print(f"Используется база данных: {db_path}")
            print(f"Путь существует: {os.path.exists(db_path)}")
            
            self.conn = sqlite3.connect(db_path)
            self.cursor = self.conn.cursor()
            
            # Проверяем структуру таблицы
            self.cursor.execute("PRAGMA table_info(microorganisms)")
            columns = self.cursor.fetchall()
            print("Структура таблицы microorganisms:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
                
            print("База данных успешно подключена")
            
            # Инициализируем менеджер изображений
            self.image_manager = MicroorganismImageManager(self.conn)
            
        except Exception as e:
            print(f"Ошибка подключения к БД: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось подключиться к базе данных:\n{str(e)}")
            self.parent.destroy()
            return
        
        # Переменные для хранения данных
        self.genus_var = tk.StringVar()
        self.species_var = tk.StringVar()
        self.strain_var = tk.StringVar()
        self.gram_var = tk.StringVar()
        self.morphology_var = tk.StringVar()
        self.metabolism_var = tk.StringVar()
        self.ph_var = tk.DoubleVar(value=7.0)
        self.temp_var = tk.DoubleVar(value=37.0)
        self.growth_rate_var = tk.DoubleVar(value=0.5)
        self.model_var = tk.StringVar()
        self.k_var = tk.DoubleVar(value=0.0)
        self.y_var = tk.DoubleVar(value=0.0)
        
        self.current_genus = None
        self.current_species_id = None
        self.current_images = []
        self.current_image_index = 0
        
        # Словари для хранения ID
        self.genus_ids = {}  # genus_name -> list of species_ids
        self.species_data = {}  # index -> species_id
        
        # Изображения
        self.current_photo = None
        self.photo_images = []  # Список PhotoImage для предотвращения сборки мусора
        
        # Кэш изображений
        self.image_cache = {}
        
        self.create_widgets()
        self.load_genus_list()
        
    def create_widgets(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка веса строк и столбцов
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        
        main_frame.columnconfigure(0, weight=1)  # Левая панель - списки
        main_frame.columnconfigure(1, weight=2)  # Центр - форма
        main_frame.columnconfigure(2, weight=2)  # Правая панель - изображения
        main_frame.rowconfigure(0, weight=0)     # Заголовок
        main_frame.rowconfigure(1, weight=1)     # Основное содержимое
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Справочник микроорганизмов", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Контейнер для основного содержимого
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=2)
        content_frame.columnconfigure(2, weight=2)
        content_frame.rowconfigure(0, weight=1)
        
        # Левая панель: Роды и Виды
        left_panel = ttk.Frame(content_frame)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле 1: Род (объединяющий параметр)
        frame1 = ttk.LabelFrame(left_panel, text="1. Род", padding="10")
        frame1.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Поле поиска для рода
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        genus_search_var = tk.StringVar()
        genus_search_var.trace('w', lambda *args: self.filter_genus_list(genus_search_var.get()))
        genus_search = ttk.Entry(search_frame, textvariable=genus_search_var, width=20)
        genus_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список родов
        self.genus_listbox = tk.Listbox(frame1, width=25)
        self.genus_listbox.pack(fill=tk.BOTH, expand=True)
        self.genus_listbox.bind('<<ListboxSelect>>', self.on_genus_select)
        
        # Кнопки для рода
        buttons_frame1 = ttk.Frame(frame1)
        buttons_frame1.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(buttons_frame1, text="Добавить", command=self.add_genus).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame1, text="Удалить", command=self.delete_genus).pack(side=tk.LEFT)
        
        # Поле 2: Вид (зависит от рода)
        frame2 = ttk.LabelFrame(left_panel, text="2. Вид", padding="10")
        frame2.pack(fill=tk.BOTH, expand=True)
        
        # Поле поиска для вида
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        species_search_var = tk.StringVar()
        species_search_var.trace('w', lambda *args: self.filter_species_list(species_search_var.get()))
        species_search = ttk.Entry(search_frame2, textvariable=species_search_var, width=20)
        species_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список видов
        self.species_listbox = tk.Listbox(frame2)
        self.species_listbox.pack(fill=tk.BOTH, expand=True)
        self.species_listbox.bind('<<ListboxSelect>>', self.on_species_select)
        
        # Кнопки для вида
        buttons_frame2 = ttk.Frame(frame2)
        buttons_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(buttons_frame2, text="Добавить", command=self.add_species).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame2, text="Удалить", command=self.delete_species).pack(side=tk.LEFT)
        
        # Центральная панель: Форма с информацией
        center_panel = ttk.LabelFrame(content_frame, text="3. Информация о микроорганизме", padding="10")
        center_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        center_panel.columnconfigure(1, weight=1)
        
        # Поля формы
        row = 0
        ttk.Label(center_panel, text="Род:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.genus_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Вид:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.species_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Штамм:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.strain_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Окраска по Граму:").grid(row=row, column=0, sticky=tk.W, pady=2)
        gram_combo = ttk.Combobox(center_panel, textvariable=self.gram_var, 
                                 values=["Positive", "Negative", "Variable", "Unknown"])
        gram_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Морфология:").grid(row=row, column=0, sticky=tk.W, pady=2)
        morph_combo = ttk.Combobox(center_panel, textvariable=self.morphology_var, 
                                  values=["Coccus", "Rod", "Spiral", "Vibrio", "Other"])
        morph_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Метаболизм:").grid(row=row, column=0, sticky=tk.W, pady=2)
        metab_combo = ttk.Combobox(center_panel, textvariable=self.metabolism_var, 
                                  values=["Aerobic", "Anaerobic", "Facultative anaerobic", 
                                          "Microaerophilic", "Other"])
        metab_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="pH оптимум:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.ph_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Температура оптимум (°C):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.temp_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Скорость роста:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.growth_rate_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="Тип модели:").grid(row=row, column=0, sticky=tk.W, pady=2)
        model_combo = ttk.Combobox(center_panel, textvariable=self.model_var, 
                                  values=["Exponential", "Logistic", "Gompertz", "Monod", "Other"])
        model_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="k (константа роста):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.k_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        row += 1
        ttk.Label(center_panel, text="y (доп. параметр):").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(center_panel, textvariable=self.y_var).grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Кнопки действий
        action_frame = ttk.Frame(center_panel)
        action_frame.grid(row=row+1, column=0, columnspan=2, pady=(15, 0), sticky=(tk.W, tk.E))
        
        ttk.Button(action_frame, text="Сохранить", command=self.save_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Очистить", command=self.clear_form).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Обновить", command=self.refresh_lists).pack(side=tk.LEFT)
        
        # Правая панель: Изображения микроорганизма
        right_panel = ttk.LabelFrame(content_frame, text="4. Фотографии микроорганизма", padding="10")
        right_panel.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=0)
        
        # Холст для отображения изображения
        self.image_canvas = tk.Canvas(right_panel, width=400, height=300, bg='white', highlightthickness=1, highlightbackground="gray")
        self.image_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Информация об изображении
        self.image_info_label = ttk.Label(right_panel, text="Нет изображений", font=('Arial', 9))
        self.image_info_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        
        # Панель управления изображениями
        image_controls_frame = ttk.Frame(right_panel)
        image_controls_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Кнопки навигации по изображениям
        nav_frame = ttk.Frame(image_controls_frame)
        nav_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(nav_frame, text="◀", width=3, command=self.prev_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(nav_frame, text="▶", width=3, command=self.next_image).pack(side=tk.LEFT)
        
        # Информация о текущем изображении
        self.image_counter_label = ttk.Label(nav_frame, text="0/0")
        self.image_counter_label.pack(side=tk.LEFT, padx=10)
        
        # Кнопки управления изображениями
        controls_frame = ttk.Frame(image_controls_frame)
        controls_frame.pack(side=tk.RIGHT)
        
        ttk.Button(controls_frame, text="Загрузить", command=self.upload_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text="Удалить", command=self.delete_current_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text="Найти в сети", command=self.search_web_images).pack(side=tk.LEFT)
        
        # Список изображений
        images_list_frame = ttk.LabelFrame(right_panel, text="Все изображения", padding="5")
        images_list_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        
        # Создаем Treeview для списка изображений
        columns = ('type', 'description', 'date')
        self.images_tree = ttk.Treeview(images_list_frame, columns=columns, show='tree headings', height=4)
        
        # Настраиваем колонки
        self.images_tree.column('#0', width=0, stretch=tk.NO)  # Скрытая колонка
        self.images_tree.column('type', width=80, anchor=tk.W)
        self.images_tree.column('description', width=150, anchor=tk.W)
        self.images_tree.column('date', width=100, anchor=tk.W)
        
        # Заголовки колонок
        self.images_tree.heading('type', text='Тип')
        self.images_tree.heading('description', text='Описание')
        self.images_tree.heading('date', text='Дата')
        
        # Scrollbar
        tree_scroll = ttk.Scrollbar(images_list_frame, orient="vertical", command=self.images_tree.yview)
        self.images_tree.configure(yscrollcommand=tree_scroll.set)
        
        # Размещаем Treeview и Scrollbar
        self.images_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Настраиваем вес строк и колонок
        images_list_frame.columnconfigure(0, weight=1)
        images_list_frame.rowconfigure(0, weight=1)
        
        # Привязываем событие выбора в Treeview
        self.images_tree.bind('<<TreeviewSelect>>', self.on_image_select)
        
        # По умолчанию отображаем сообщение об отсутствии изображений
        self.show_no_image_message()
    
    def show_no_image_message(self):
        """Отображение сообщения об отсутствии изображений"""
        self.image_canvas.delete("all")
        self.image_canvas.create_text(
            200, 150,
            text="Нет изображений\nдля этого микроорганизма",
            font=('Arial', 12),
            justify=tk.CENTER,
            fill='gray'
        )
        self.image_info_label.config(text="Нет изображений")
        self.image_counter_label.config(text="0/0")
    
    def load_images(self):
        """Загрузка изображений для текущего микроорганизма"""
        if not self.current_species_id:
            self.show_no_image_message()
            return
        
        # Очищаем Treeview
        for item in self.images_tree.get_children():
            self.images_tree.delete(item)
        
        # Загружаем изображения из БД
        self.current_images = self.image_manager.get_images(self.current_species_id)
        
        if not self.current_images:
            self.show_no_image_message()
            return
        
        # Заполняем Treeview
        for i, (img_id, path, img_type, source, description, date) in enumerate(self.current_images):
            # Форматируем дату
            if isinstance(date, str):
                date_str = date[:10]  # Берем только дату
            else:
                date_str = str(date)[:10]
            
            # Добавляем запись в Treeview
            self.images_tree.insert('', 'end', iid=str(i), 
                                  values=(img_type.capitalize(), description or 'Без описания', date_str))
        
        # Показываем первое изображение
        self.current_image_index = 0
        self.show_current_image()
    
    def show_current_image(self):
        """Отображение текущего изображения"""
        if not self.current_images or self.current_image_index >= len(self.current_images):
            self.show_no_image_message()
            return
        
        # Получаем информацию о текущем изображении
        img_id, path, img_type, source, description, date = self.current_images[self.current_image_index]
        
        try:
            # Загружаем изображение
            if os.path.exists(path):
                img = Image.open(path)
            elif path.startswith('http'):
                # Для веб-изображений (нужно реализовать скачивание)
                img = Image.new('RGB', (400, 300), color='gray')
                draw = ImageDraw.Draw(img)
                draw.text((100, 140), "Веб-изображение", fill='white')
            else:
                raise FileNotFoundError(f"Файл не найден: {path}")
            
            # Изменяем размер для отображения
            img.thumbnail((380, 280), Image.Resampling.LANCZOS)
            
            # Конвертируем в PhotoImage
            self.current_photo = ImageTk.PhotoImage(img)
            
            # Очищаем холст и отображаем изображение
            self.image_canvas.delete("all")
            canvas_width = self.image_canvas.winfo_width() or 400
            canvas_height = self.image_canvas.winfo_height() or 300
            x = canvas_width // 2
            y = canvas_height // 2
            
            self.image_canvas.create_image(x, y, image=self.current_photo, anchor=tk.CENTER)
            
            # Обновляем информацию
            self.image_info_label.config(text=f"{description or 'Без описания'} ({img_type})")
            self.image_counter_label.config(text=f"{self.current_image_index + 1}/{len(self.current_images)}")
            
            # Выделяем текущий элемент в Treeview
            self.images_tree.selection_set(str(self.current_image_index))
            self.images_tree.see(str(self.current_image_index))
            
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            self.show_no_image_message()
    
    def prev_image(self):
        """Переход к предыдущему изображению"""
        if self.current_images and len(self.current_images) > 1:
            self.current_image_index = (self.current_image_index - 1) % len(self.current_images)
            self.show_current_image()
    
    def next_image(self):
        """Переход к следующему изображению"""
        if self.current_images and len(self.current_images) > 1:
            self.current_image_index = (self.current_image_index + 1) % len(self.current_images)
            self.show_current_image()
    
    def upload_image(self):
        """Загрузка изображения с компьютера"""
        if not self.current_species_id:
            messagebox.showwarning("Внимание", "Сначала выберите микроорганизм!")
            return
        
        # Открываем диалог выбора файла
        filetypes = [
            ("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp *.tiff"),
            ("Все файлы", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=filetypes
        )
        
        if filepath:
            # Запрашиваем описание
            description = self.ask_image_description()
            
            # Сохраняем изображение
            if self.image_manager.save_image(self.current_species_id, filepath, 'photo', 'local', description):
                messagebox.showinfo("Успех", "Изображение успешно загружено!")
                self.load_images()
            else:
                messagebox.showerror("Ошибка", "Не удалось загрузить изображение")
    
    def ask_image_description(self):
        """Запрос описания изображения"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Описание изображения")
        dialog.geometry("400x200")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите описание изображения:").pack(pady=(20, 5))
        
        description_text = tk.Text(dialog, height=5, width=40)
        description_text.pack(pady=5, padx=10)
        description_text.focus_set()
        
        result = []
        
        def save_description():
            result.append(description_text.get("1.0", tk.END).strip())
            dialog.destroy()
        
        ttk.Button(dialog, text="Сохранить", command=save_description).pack(pady=10)
        
        dialog.wait_window()
        
        return result[0] if result else ""
    
    def delete_current_image(self):
        """Удаление текущего изображения"""
        if not self.current_images or self.current_image_index >= len(self.current_images):
            return
        
        img_id, path, img_type, source, description, date = self.current_images[self.current_image_index]
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить это изображение?\nОписание: {description}"):
            if self.image_manager.delete_image(img_id):
                messagebox.showinfo("Успех", "Изображение удалено")
                self.load_images()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить изображение")
    
    def search_web_images(self):
        """Поиск изображений в интернете"""
        if not self.current_species_id:
            messagebox.showwarning("Внимание", "Сначала выберите микроорганизм!")
            return
        
        genus = self.genus_var.get()
        species = self.species_var.get()
        
        if not genus or not species:
            messagebox.showwarning("Внимание", "Заполните род и вид!")
            return
        
        # Получаем поисковые запросы
        search_queries = self.image_manager.search_web_images(genus, species)
        
        # Создаем диалог для поиска
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Поиск изображений для {genus} {species}")
        dialog.geometry("600x400")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Поисковые запросы для изображений:", 
                 font=('Arial', 10, 'bold')).pack(pady=(10, 5))
        
        # Показываем поисковые запросы
        for i, query in enumerate(search_queries):
            frame = ttk.Frame(dialog)
            frame.pack(fill=tk.X, padx=20, pady=2)
            
            ttk.Label(frame, text=query, font=('Arial', 9)).pack(side=tk.LEFT)
            
            # Кнопка для поиска в браузере
            ttk.Button(frame, text="Найти", width=8,
                      command=lambda q=query: webbrowser.open(f"https://www.google.com/search?q={quote(q)}&tbm=isch")
                     ).pack(side=tk.RIGHT)
        
        # Разделитель
        ttk.Separator(dialog, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Ручной ввод URL
        ttk.Label(dialog, text="Или введите URL изображения вручную:").pack(pady=5)
        
        url_frame = ttk.Frame(dialog)
        url_frame.pack(fill=tk.X, padx=20, pady=5)
        
        url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=url_var, width=40)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def download_from_url():
            url = url_var.get().strip()
            if url and url.startswith(('http://', 'https://')):
                description = self.ask_image_description()
                if self.image_manager.download_image_from_url(url, self.current_species_id, description):
                    messagebox.showinfo("Успех", "Изображение скачано!")
                    dialog.destroy()
                    self.load_images()
                else:
                    messagebox.showerror("Ошибка", "Не удалось скачать изображение")
            else:
                messagebox.showwarning("Внимание", "Введите корректный URL")
        
        ttk.Button(url_frame, text="Скачать", command=download_from_url).pack(side=tk.RIGHT)
    
    def on_image_select(self, event):
        """Обработка выбора изображения в списке"""
        selection = self.images_tree.selection()
        if selection:
            index = int(selection[0])
            if 0 <= index < len(self.current_images):
                self.current_image_index = index
                self.show_current_image()
    
    # Остальные методы остаются без изменений (load_genus_list, filter_genus_list, и т.д.)
    # Добавлю только необходимые изменения
    
    def load_species_details(self, species_id):
        """Загрузка детальной информации о виде"""
        print(f"Загрузка деталей для вида ID: {species_id}")
        try:
            self.cursor.execute("""
                SELECT genus, species, strain, gram_staining, morphology, metabolism,
                       ph_optimum, temperature_optimum, growth_rate, model_type,
                       k_constant, y_constant
                FROM microorganisms 
                WHERE id = ?
            """, (species_id,))
            
            result = self.cursor.fetchone()
            if result:
                (genus, species, strain, gram_staining, morphology, metabolism,
                 ph_optimum, temp_optimum, growth_rate, model_type, k_constant, y_constant) = result
                
                print(f"Загружены данные: {genus} {species}, y_constant={y_constant}")
                
                self.genus_var.set(genus)
                self.species_var.set(species)
                self.strain_var.set(strain if strain else "")
                self.gram_var.set(gram_staining)
                self.morphology_var.set(morphology)
                self.metabolism_var.set(metabolism)
                self.ph_var.set(ph_optimum)
                self.temp_var.set(temp_optimum)
                self.growth_rate_var.set(growth_rate)
                self.model_var.set(model_type)
                self.k_var.set(k_constant)
                self.y_var.set(y_constant)
                
                # Загружаем изображения
                self.load_images()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Загружены данные для {genus} {species}")
            else:
                print(f"Не найдены данные для ID: {species_id}")
                messagebox.showwarning("Предупреждение", "Не найдены данные для выбранного микроорганизма")
                
        except Exception as e:
            print(f"Ошибка загрузки деталей вида: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные микроорганизма:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.genus_var.set("")
        self.species_var.set("")
        self.strain_var.set("")
        self.gram_var.set("")
        self.morphology_var.set("")
        self.metabolism_var.set("")
        self.ph_var.set(7.0)
        self.temp_var.set(37.0)
        self.growth_rate_var.set(0.5)
        self.model_var.set("")
        self.k_var.set(0.0)
        self.y_var.set(0.0)
        
        self.current_species_id = None
        self.current_images = []
        self.current_image_index = 0
        
        # Снимаем выделение в списках
        self.genus_listbox.selection_clear(0, tk.END)
        self.species_listbox.selection_clear(0, tk.END)
        self.species_listbox.delete(0, tk.END)
        
        # Очищаем изображения
        self.show_no_image_message()
        
        # Очищаем список изображений
        for item in self.images_tree.get_children():
            self.images_tree.delete(item)
        
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")

    # Остальные методы (load_genus_list, filter_genus_list, on_genus_select, 
    # load_species_list, filter_species_list, on_species_select, add_genus, 
    # delete_genus, add_species, delete_species, save_changes, refresh_lists, __del__)
    # остаются БЕЗ изменений из предыдущей версии
    
    def load_genus_list(self):
        """Загрузка списка родов"""
        self.genus_listbox.delete(0, tk.END)
        try:
            self.cursor.execute("SELECT DISTINCT genus FROM microorganisms ORDER BY genus")
            genera = self.cursor.fetchall()
            
            for genus in genera:
                genus_name = genus[0]
                self.genus_listbox.insert(tk.END, genus_name)
                
                # Загружаем ID видов для этого рода
                self.cursor.execute("SELECT id FROM microorganisms WHERE genus = ?", (genus_name,))
                species_ids = [row[0] for row in self.cursor.fetchall()]
                self.genus_ids[genus_name] = species_ids
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружено {len(genera)} родов микроорганизмов")
                
        except Exception as e:
            print(f"Ошибка загрузки родов: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить список родов:\n{str(e)}")
    
    def filter_genus_list(self, search_text):
        """Фильтрация списка родов"""
        self.genus_listbox.delete(0, tk.END)
        try:
            self.cursor.execute("SELECT DISTINCT genus FROM microorganisms WHERE genus LIKE ? ORDER BY genus", 
                              (f'%{search_text}%',))
            genera = self.cursor.fetchall()
            
            for genus in genera:
                self.genus_listbox.insert(tk.END, genus[0])
        except Exception as e:
            print(f"Ошибка фильтрации родов: {str(e)}")
    
    def on_genus_select(self, event):
        """Обработка выбора рода"""
        selection = self.genus_listbox.curselection()
        if not selection:
            return
            
        self.current_genus = self.genus_listbox.get(selection[0])
        self.genus_var.set(self.current_genus)
        print(f"Выбран род: {self.current_genus}")
        self.load_species_list()
    
    def load_species_list(self):
        """Загрузка списка видов для выбранного рода"""
        print(f"Загрузка видов для рода: {self.current_genus}")
        self.species_listbox.delete(0, tk.END)
        self.species_data.clear()
        
        if not self.current_genus:
            return
            
        try:
            self.cursor.execute("""
                SELECT id, species, strain 
                FROM microorganisms 
                WHERE genus = ? 
                ORDER BY species, strain
            """, (self.current_genus,))
            
            species_list = self.cursor.fetchall()
            print(f"Найдено видов: {len(species_list)}")
            
            for species_id, species, strain in species_list:
                display_text = f"{species}"
                if strain:
                    display_text += f" ({strain})"
                index = self.species_listbox.size()
                self.species_listbox.insert(tk.END, display_text)
                self.species_data[index] = species_id
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружено {len(species_list)} видов для рода {self.current_genus}")
                
        except Exception as e:
            print(f"Ошибка загрузки видов: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить список видов:\n{str(e)}")
    
    def filter_species_list(self, search_text):
        """Фильтрация списка видов"""
        self.species_listbox.delete(0, tk.END)
        self.species_data.clear()
        
        if not self.current_genus:
            return
            
        try:
            self.cursor.execute("""
                SELECT id, species, strain 
                FROM microorganisms 
                WHERE genus = ? AND (species LIKE ? OR strain LIKE ?)
                ORDER BY species, strain
            """, (self.current_genus, f'%{search_text}%', f'%{search_text}%'))
            
            species_list = self.cursor.fetchall()
            
            for species_id, species, strain in species_list:
                display_text = f"{species}"
                if strain:
                    display_text += f" ({strain})"
                index = self.species_listbox.size()
                self.species_listbox.insert(tk.END, display_text)
                self.species_data[index] = species_id
        except Exception as e:
            print(f"Ошибка фильтрации видов: {str(e)}")
    
    def on_species_select(self, event):
        """Обработка выбора вида"""
        selection = self.species_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        species_id = self.species_data.get(index)
        if species_id:
            self.current_species_id = species_id
            print(f"Выбран вид с ID: {species_id}")
            self.load_species_details(species_id)
    
    def add_genus(self):
        """Добавление нового рода"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый род")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название рода:").pack(pady=(20, 5))
        genus_entry = ttk.Entry(dialog, width=30)
        genus_entry.pack(pady=5)
        genus_entry.focus_set()
        
        def save_genus():
            genus_name = genus_entry.get().strip()
            if genus_name:
                # Проверяем, существует ли уже такой род
                self.cursor.execute("SELECT COUNT(*) FROM microorganisms WHERE genus = ?", (genus_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Род '{genus_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового рода
                    self.cursor.execute("""
                        INSERT INTO microorganisms (genus, species, strain, gram_staining, morphology)
                        VALUES (?, 'sp.', 'Пример', 'Positive', 'Rod')
                    """, (genus_name,))
                    self.conn.commit()
                    self.load_genus_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название рода!")
        
        ttk.Button(dialog, text="Сохранить", command=save_genus).pack(pady=10)
        
    def delete_genus(self):
        """Удаление выбранного рода"""
        selection = self.genus_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите род для удаления!")
            return
            
        genus_name = self.genus_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить род '{genus_name}' и все связанные виды?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM microorganisms WHERE genus = ?", (genus_name,))
            self.conn.commit()
            self.load_genus_list()
            self.species_listbox.delete(0, tk.END)
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Род '{genus_name}' удален")
    
    def add_species(self):
        """Добавление нового вида"""
        if not self.current_genus:
            messagebox.showwarning("Внимание", "Сначала выберите род!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новый вид для рода {self.current_genus}")
        dialog.geometry("400x200")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Вид:").grid(row=0, column=0, sticky=tk.W, pady=5)
        species_entry = ttk.Entry(frame, width=30)
        species_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        ttk.Label(frame, text="Штамм:").grid(row=1, column=0, sticky=tk.W, pady=5)
        strain_entry = ttk.Entry(frame, width=30)
        strain_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        species_entry.focus_set()
        
        def save_species():
            species_name = species_entry.get().strip()
            strain_name = strain_entry.get().strip()
            
            if species_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO microorganisms (genus, species, strain, gram_staining, morphology, 
                                              metabolism, ph_optimum, temperature_optimum, growth_rate)
                    VALUES (?, ?, ?, 'Positive', 'Rod', 'Facultative anaerobic', 7.0, 37.0, 0.5)
                """, (self.current_genus, species_name, strain_name if strain_name else None))
                
                self.conn.commit()
                self.load_species_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлен новый вид: {species_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название вида!")
        
        ttk.Button(frame, text="Сохранить", command=save_species).grid(row=2, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_species(self):
        """Удаление выбранного вида"""
        selection = self.species_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите вид для удаления!")
            return
            
        index = selection[0]
        species_id = self.species_data.get(index)
        
        if not species_id:
            return
            
        # Получаем информацию о виде для сообщения
        self.cursor.execute("SELECT genus, species, strain FROM microorganisms WHERE id = ?", (species_id,))
        result = self.cursor.fetchone()
        if result:
            genus, species, strain = result
            
            display_name = f"{genus} {species}"
            if strain:
                display_name += f" ({strain})"
            
            if messagebox.askyesno("Подтверждение", 
                                  f"Удалить микроорганизм '{display_name}'?\nЭто действие нельзя отменить!"):
                self.cursor.execute("DELETE FROM microorganisms WHERE id = ?", (species_id,))
                self.conn.commit()
                self.load_species_list()
                self.clear_form()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Микроорганизм '{display_name}' удален")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_species_id:
            messagebox.showwarning("Внимание", "Сначала выберите микроорганизм для редактирования!")
            return
            
        # Получаем данные из полей
        genus = self.genus_var.get().strip()
        species = self.species_var.get().strip()
        strain = self.strain_var.get().strip()
        
        if not genus or not species:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Род и Вид!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE microorganisms 
                SET genus = ?, species = ?, strain = ?, gram_staining = ?, morphology = ?,
                    metabolism = ?, ph_optimum = ?, temperature_optimum = ?, growth_rate = ?,
                    model_type = ?, k_constant = ?, y_constant = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                genus, species, strain if strain else None,
                self.gram_var.get(), self.morphology_var.get(), self.metabolism_var.get(),
                self.ph_var.get(), self.temp_var.get(), self.growth_rate_var.get(),
                self.model_var.get(), self.k_var.get(), self.y_var.get(),
                self.current_species_id
            ))
            
            self.conn.commit()
            print(f"Сохранены изменения для ID: {self.current_species_id}")
            
            # Обновляем списки
            if genus != self.current_genus:
                self.current_genus = genus
                self.load_genus_list()
                # Выделяем обновленный род в списке
                try:
                    index = self.genus_listbox.get(0, tk.END).index(genus)
                    self.genus_listbox.selection_clear(0, tk.END)
                    self.genus_listbox.selection_set(index)
                    self.genus_listbox.see(index)
                except ValueError:
                    pass
            
            self.load_species_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для {genus} {species} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            print(f"Ошибка сохранения: {str(e)}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_genus_list()
        if self.current_genus:
            self.load_species_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()
            print("Соединение с БД закрыто")

# Тестирование
if __name__ == "__main__":
    root = tk.Tk()
    app = MicroorganismsWindow(root)
    root.mainloop()