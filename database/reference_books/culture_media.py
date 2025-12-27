# [file name database/reference_books/culture_media.py ]
# Справочник «Питательные среды»
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




class CultureMediaWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Питательные среды")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('culture_media')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.media_type_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.current_media_type = None
        self.current_media_id = None
        
        self.create_widgets()
        self.load_media_type_list()
        
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
        title_label = ttk.Label(main_frame, text="Справочник питательных сред", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Тип среды
        frame1 = ttk.LabelFrame(main_frame, text="1. Тип среды", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для типа среды
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        media_type_search_var = tk.StringVar()
        media_type_search_var.trace('w', lambda *args: self.filter_media_type_list(media_type_search_var.get()))
        media_type_search = ttk.Entry(search_frame, textvariable=media_type_search_var, width=20)
        media_type_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список типов сред
        self.media_type_listbox = tk.Listbox(frame1, width=25)
        self.media_type_index_to_id = {}
        self.media_type_listbox.pack(fill=tk.BOTH, expand=True)
        self.media_type_listbox.bind('<<ListboxSelect>>', self.on_media_type_select)
        
        # Кнопки для типа среды
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_media_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_media_type).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Названия сред выбранного типа
        frame2 = ttk.LabelFrame(main_frame, text="2. Названия сред", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для названий сред
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        name_search_var = tk.StringVar()
        name_search_var.trace('w', lambda *args: self.filter_media_list(name_search_var.get()))
        name_search = ttk.Entry(search_frame2, textvariable=name_search_var, width=20)
        name_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список названий сред
        self.media_listbox = tk.Listbox(frame2)
        self.media_index_to_id = {}
        self.media_listbox.pack(fill=tk.BOTH, expand=True)
        self.media_listbox.bind('<<ListboxSelect>>', self.on_media_select)
        
        # Кнопки для названий сред
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_media).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_media).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранной среде
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация о среде", padding="10")
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
        
        # Тип среды
        ttk.Label(self.detail_frame, text="Тип среды:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.media_type_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.media_type_var)
        self.media_type_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Название среды
        ttk.Label(self.detail_frame, text="Название:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.name_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.name_var)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Состав
        ttk.Label(self.detail_frame, text="Состав (г/л):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.composition_text = tk.Text(self.detail_frame, width=30, height=5)
        self.composition_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # pH
        ttk.Label(self.detail_frame, text="pH:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.ph_var = tk.DoubleVar(value=7.0)
        self.ph_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=14, increment=0.1, 
                                     textvariable=self.ph_var, width=27)
        self.ph_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Цвет
        ttk.Label(self.detail_frame, text="Цвет:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.color_var = tk.StringVar()
        self.color_combo = ttk.Combobox(self.detail_frame, textvariable=self.color_var, width=27,
                                      values=["Прозрачный", "Красный", "Желтый", "Зеленый", "Синий", 
                                             "Коричневый", "Бесцветный", "Другой"])
        self.color_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Консистенция
        ttk.Label(self.detail_frame, text="Консистенция:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.consistency_var = tk.StringVar()
        self.consistency_combo = ttk.Combobox(self.detail_frame, textvariable=self.consistency_var, width=27,
                                            values=["Жидкая", "Полутвердая", "Твердая", "Гель", "Порошок"])
        self.consistency_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Метод приготовления
        ttk.Label(self.detail_frame, text="Метод приготовления:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.preparation_text = tk.Text(self.detail_frame, width=30, height=8)
        self.preparation_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_media_type_list(self):
        """Загрузка списка типов сред из базы данных"""
        self.media_type_listbox.delete(0, tk.END)
        self.media_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT media_type FROM culture_media ORDER BY media_type")
        media_types = self.cursor.fetchall()
        
        for media_type in media_types:
            self.media_type_listbox.insert(tk.END, media_type[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(media_types)} типов сред")
    
    def filter_media_type_list(self, search_text):
        """Фильтрация списка типов сред"""
        self.media_type_listbox.delete(0, tk.END)
        self.media_type_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT media_type FROM culture_media WHERE media_type LIKE ? ORDER BY media_type", 
                          (f'%{search_text}%',))
        media_types = self.cursor.fetchall()
        
        for media_type in media_types:
            self.media_type_listbox.insert(tk.END, media_type[0])
    
    def on_media_type_select(self, event):
        """Обработка выбора типа среды"""
        selection = self.media_type_listbox.curselection()
        if not selection:
            return
            
        self.current_media_type = self.media_type_listbox.get(selection[0])
        self.media_type_var.set(self.current_media_type)
        self.load_media_list()
    
    def load_media_list(self):
        """Загрузка списка сред для выбранного типа"""
        self.media_listbox.delete(0, tk.END)
        self.media_index_to_id.clear()
        if not self.current_media_type:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM culture_media 
            WHERE media_type = ? 
            ORDER BY name
        """, (self.current_media_type,))
        
        media_list = self.cursor.fetchall()
        
        for media_id, name in media_list:
            self.media_listbox.insert(tk.END, name)
            # Сохраняем ID в атрибуте элемента списка
            self.media_index_to_id[self.media_listbox.size() - 1] = media_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(media_list)} сред для типа {self.current_media_type}")
    
    def filter_media_list(self, search_text):
        """Фильтрация списка сред"""
        self.media_listbox.delete(0, tk.END)
        self.media_index_to_id.clear()
        if not self.current_media_type:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM culture_media 
            WHERE media_type = ? AND name LIKE ?
            ORDER BY name
        """, (self.current_media_type, f'%{search_text}%'))
        
        media_list = self.cursor.fetchall()
        
        for media_id, name in media_list:
            self.media_listbox.insert(tk.END, name)
            self.media_index_to_id[self.media_listbox.size() - 1] = media_id
    
    def on_media_select(self, event):
        """Обработка выбора среды"""
        selection = self.media_listbox.curselection()
        if not selection:
            return
            
        media_id = self.media_index_to_id.get(selection[0])
            
        if media_id is None:
            
            return
        self.current_media_id = media_id
        self.load_media_details(media_id)
    
    def load_media_details(self, media_id):
        """Загрузка детальной информации о среде"""
        self.cursor.execute("""
            SELECT media_type, name, composition, ph, color, consistency, preparation_method
            FROM culture_media 
            WHERE id = ?
        """, (media_id,))
        
        result = self.cursor.fetchone()
        if result:
            (media_type, name, composition, ph, color, consistency, preparation_method) = result
            
            self.media_type_var.set(media_type)
            self.name_var.set(name)
            self.composition_text.delete(1.0, tk.END)
            self.composition_text.insert(1.0, composition if composition else "")
            self.ph_var.set(ph)
            self.color_var.set(color if color else "")
            self.consistency_var.set(consistency if consistency else "")
            self.preparation_text.delete(1.0, tk.END)
            self.preparation_text.insert(1.0, preparation_method if preparation_method else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для среды: {name}")
    
    def add_media_type(self):
        """Добавление нового типа среды"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый тип среды")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название типа среды:").pack(pady=(20, 5))
        media_type_entry = ttk.Entry(dialog, width=30)
        media_type_entry.pack(pady=5)
        media_type_entry.focus_set()
        
        def save_media_type():
            media_type_name = media_type_entry.get().strip()
            if media_type_name:
                # Проверяем, существует ли уже такой тип
                self.cursor.execute("SELECT COUNT(*) FROM culture_media WHERE media_type = ?", (media_type_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Тип среды '{media_type_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового типа
                    self.cursor.execute("""
                        INSERT INTO culture_media (media_type, name, composition, ph)
                        VALUES (?, 'Пример среды', 'Компонент1: 10 г/л', 7.0)
                    """, (media_type_name,))
                    self.conn.commit()
                    self.load_media_type_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название типа среды!")
        
        ttk.Button(dialog, text="Сохранить", command=save_media_type).pack(pady=10)
        
    def delete_media_type(self):
        """Удаление выбранного типа среды"""
        selection = self.media_type_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите тип среды для удаления!")
            return
            
        media_type_name = self.media_type_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить тип среды '{media_type_name}' и все связанные среды?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM culture_media WHERE media_type = ?", (media_type_name,))
            self.conn.commit()
            self.load_media_type_list()
            self.media_listbox.delete(0, tk.END)
            self.media_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Тип среды '{media_type_name}' удален")
    
    def add_media(self):
        """Добавление новой среды"""
        if not self.current_media_type:
            messagebox.showwarning("Внимание", "Сначала выберите тип среды!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новую среду для типа {self.current_media_type}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Название среды:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        name_entry.focus_set()
        
        def save_media():
            media_name = name_entry.get().strip()
            
            if media_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO culture_media (media_type, name, composition, ph, color, consistency)
                    VALUES (?, ?, 'Компонент1: 10 г/л', 7.0, 'Прозрачный', 'Жидкая')
                """, (self.current_media_type, media_name))
                
                self.conn.commit()
                self.load_media_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлена новая среда: {media_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название среды!")
        
        ttk.Button(frame, text="Сохранить", command=save_media).grid(row=1, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_media(self):
        """Удаление выбранной среды"""
        selection = self.media_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите среду для удаления!")
            return
            
        media_id = self.media_index_to_id.get(selection[0])
            
        if media_id is None:
            
            return
        # Получаем информацию о среде для сообщения
        self.cursor.execute("SELECT media_type, name FROM culture_media WHERE id = ?", (media_id,))
        media_type, name = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить среду '{name}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM culture_media WHERE id = ?", (media_id,))
            self.conn.commit()
            self.load_media_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Среда '{name}' удалена")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_media_id:
            messagebox.showwarning("Внимание", "Сначала выберите среду для редактирования!")
            return
            
        # Получаем данные из полей
        media_type = self.media_type_var.get().strip()
        name = self.name_var.get().strip()
        composition = self.composition_text.get(1.0, tk.END).strip()
        ph = self.ph_var.get()
        color = self.color_var.get()
        consistency = self.consistency_var.get()
        preparation_method = self.preparation_text.get(1.0, tk.END).strip()
        
        if not media_type or not name:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Тип среды и Название!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE culture_media 
                SET media_type = ?, name = ?, composition = ?, ph = ?, color = ?, 
                    consistency = ?, preparation_method = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                media_type, name, composition, ph, color, consistency, preparation_method,
                self.current_media_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if media_type != self.current_media_type:
                self.current_media_type = media_type
                self.load_media_type_list()
                # Выделяем обновленный тип в списке
                index = self.media_type_listbox.get(0, tk.END).index(media_type)
                self.media_type_listbox.selection_clear(0, tk.END)
                self.media_type_listbox.selection_set(index)
                self.media_type_listbox.see(index)
            
            self.load_media_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для среды {name} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.media_type_var.set("")
        self.name_var.set("")
        self.composition_text.delete(1.0, tk.END)
        self.ph_var.set(7.0)
        self.color_var.set("")
        self.consistency_var.set("")
        self.preparation_text.delete(1.0, tk.END)
        
        self.current_media_id = None
        
        # Снимаем выделение в списках
        self.media_type_listbox.selection_clear(0, tk.END)
        self.media_listbox.selection_clear(0, tk.END)
        self.media_listbox.delete(0, tk.END)
        self.media_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_media_type_list()
        if self.current_media_type:
            self.load_media_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}