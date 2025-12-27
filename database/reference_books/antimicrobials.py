# [file name database/reference_books/culture_media.py]
# Справочник «Антимикробные агенты»
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




class AntimicrobialsWindow:
    def __init__(self, parent, status_bar=None):
        self.parent = parent
        self.status_bar = status_bar
        self.parent.title("Справочник: Антимикробные агенты")
        self.parent.geometry("1000x700")
        
        # Подключение к базе данных
        db_path = get_db_path('antimicrobials')

        _ensure_db_initialized(db_path)

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Переменные для хранения данных
        self.agent_class_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.current_agent_class = None
        self.current_agent_id = None
        
        self.create_widgets()
        self.load_agent_class_list()
        
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
        title_label = ttk.Label(main_frame, text="Справочник антимикробных агентов", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Поле 1: Класс агента
        frame1 = ttk.LabelFrame(main_frame, text="1. Класс агента", padding="10")
        frame1.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Поле поиска для класса агента
        search_frame = ttk.Frame(frame1)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        agent_class_search_var = tk.StringVar()
        agent_class_search_var.trace('w', lambda *args: self.filter_agent_class_list(agent_class_search_var.get()))
        agent_class_search = ttk.Entry(search_frame, textvariable=agent_class_search_var, width=20)
        agent_class_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список классов агентов
        self.agent_class_listbox = tk.Listbox(frame1, width=25)
        self.agent_class_index_to_id = {}
        self.agent_class_listbox.pack(fill=tk.BOTH, expand=True)
        self.agent_class_listbox.bind('<<ListboxSelect>>', self.on_agent_class_select)
        
        # Кнопки для класса агента
        btn_frame = ttk.Frame(frame1)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Добавить", command=self.add_agent_class).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame, text="Удалить", command=self.delete_agent_class).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 2: Названия агентов выбранного класса
        frame2 = ttk.LabelFrame(main_frame, text="2. Названия агентов", padding="10")
        frame2.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Поле поиска для названий агентов
        search_frame2 = ttk.Frame(frame2)
        search_frame2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_frame2, text="Поиск:").pack(side=tk.LEFT, padx=(0, 5))
        name_search_var = tk.StringVar()
        name_search_var.trace('w', lambda *args: self.filter_agent_list(name_search_var.get()))
        name_search = ttk.Entry(search_frame2, textvariable=name_search_var, width=20)
        name_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Список названий агентов
        self.agent_listbox = tk.Listbox(frame2)
        self.agent_index_to_id = {}
        self.agent_listbox.pack(fill=tk.BOTH, expand=True)
        self.agent_listbox.bind('<<ListboxSelect>>', self.on_agent_select)
        
        # Кнопки для названий агентов
        btn_frame2 = ttk.Frame(frame2)
        btn_frame2.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame2, text="Добавить", command=self.add_agent).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(btn_frame2, text="Удалить", command=self.delete_agent).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Поле 3: Детальная информация о выбранном агенте
        frame3 = ttk.LabelFrame(main_frame, text="3. Детальная информация об агенте", padding="10")
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
        
        # Класс агента
        ttk.Label(self.detail_frame, text="Класс агента:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.agent_class_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.agent_class_var)
        self.agent_class_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Название агента
        ttk.Label(self.detail_frame, text="Название:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.name_entry = ttk.Entry(self.detail_frame, width=30, textvariable=self.name_var)
        self.name_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Мишень действия
        ttk.Label(self.detail_frame, text="Мишень действия:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(self.detail_frame, textvariable=self.target_var, width=27,
                                        values=["Клеточная стенка", "Рибосома", "ДНК-гираза", 
                                               "Мембрана", "Метаболизм фолиевой кислоты", 
                                               "Синтез белка", "Другая"])
        self.target_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Типичная МИК
        ttk.Label(self.detail_frame, text="Типичная МИК (мг/л):").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.typical_mic_var = tk.DoubleVar(value=0.0)
        self.typical_mic_spinbox = ttk.Spinbox(self.detail_frame, from_=0, to=1000, increment=0.1, 
                                              textvariable=self.typical_mic_var, width=27)
        self.typical_mic_spinbox.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Механизм устойчивости
        ttk.Label(self.detail_frame, text="Механизм устойчивости:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.resistance_mechanism_text = tk.Text(self.detail_frame, width=30, height=4)
        self.resistance_mechanism_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Единица концентрации
        ttk.Label(self.detail_frame, text="Единица концентрации:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.concentration_unit_var = tk.StringVar()
        self.concentration_unit_combo = ttk.Combobox(self.detail_frame, textvariable=self.concentration_unit_var, width=27,
                                                    values=["мг/л", "мкг/мл", "мМ", "%", "ед/мл"])
        self.concentration_unit_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Спектр действия
        ttk.Label(self.detail_frame, text="Спектр действия:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.spectrum_text = tk.Text(self.detail_frame, width=30, height=4)
        self.spectrum_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        row += 1
        
        # Настраиваем вес колонок
        self.detail_frame.columnconfigure(1, weight=1)
        
    def load_agent_class_list(self):
        """Загрузка списка классов агентов из базы данных"""
        self.agent_class_listbox.delete(0, tk.END)
        self.agent_class_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT agent_class FROM antimicrobials ORDER BY agent_class")
        agent_classes = self.cursor.fetchall()
        
        for agent_class in agent_classes:
            self.agent_class_listbox.insert(tk.END, agent_class[0])
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(agent_classes)} классов агентов")
    
    def filter_agent_class_list(self, search_text):
        """Фильтрация списка классов агентов"""
        self.agent_class_listbox.delete(0, tk.END)
        self.agent_class_index_to_id.clear()
        self.cursor.execute("SELECT DISTINCT agent_class FROM antimicrobials WHERE agent_class LIKE ? ORDER BY agent_class", 
                          (f'%{search_text}%',))
        agent_classes = self.cursor.fetchall()
        
        for agent_class in agent_classes:
            self.agent_class_listbox.insert(tk.END, agent_class[0])
    
    def on_agent_class_select(self, event):
        """Обработка выбора класса агента"""
        selection = self.agent_class_listbox.curselection()
        if not selection:
            return
            
        self.current_agent_class = self.agent_class_listbox.get(selection[0])
        self.agent_class_var.set(self.current_agent_class)
        self.load_agent_list()
    
    def load_agent_list(self):
        """Загрузка списка агентов для выбранного класса"""
        self.agent_listbox.delete(0, tk.END)
        self.agent_index_to_id.clear()
        if not self.current_agent_class:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM antimicrobials 
            WHERE agent_class = ? 
            ORDER BY name
        """, (self.current_agent_class,))
        
        agent_list = self.cursor.fetchall()
        
        for agent_id, name in agent_list:
            self.agent_listbox.insert(tk.END, name)
            # Сохраняем ID в атрибуте элемента списка
            self.agent_index_to_id[self.agent_listbox.size() - 1] = agent_id
        
        if self.status_bar:
            self.status_bar.config(text=f"Загружено {len(agent_list)} агентов для класса {self.current_agent_class}")
    
    def filter_agent_list(self, search_text):
        """Фильтрация списка агентов"""
        self.agent_listbox.delete(0, tk.END)
        self.agent_index_to_id.clear()
        if not self.current_agent_class:
            return
            
        self.cursor.execute("""
            SELECT id, name 
            FROM antimicrobials 
            WHERE agent_class = ? AND name LIKE ?
            ORDER BY name
        """, (self.current_agent_class, f'%{search_text}%'))
        
        agent_list = self.cursor.fetchall()
        
        for agent_id, name in agent_list:
            self.agent_listbox.insert(tk.END, name)
            self.agent_index_to_id[self.agent_listbox.size() - 1] = agent_id
    
    def on_agent_select(self, event):
        """Обработка выбора агента"""
        selection = self.agent_listbox.curselection()
        if not selection:
            return
            
        agent_id = self.agent_index_to_id.get(selection[0])
            
        if agent_id is None:
            
            return
        self.current_agent_id = agent_id
        self.load_agent_details(agent_id)
    
    def load_agent_details(self, agent_id):
        """Загрузка детальной информации об агенте"""
        self.cursor.execute("""
            SELECT agent_class, name, target, typical_mic, resistance_mechanism, 
                   concentration_unit, spectrum
            FROM antimicrobials 
            WHERE id = ?
        """, (agent_id,))
        
        result = self.cursor.fetchone()
        if result:
            (agent_class, name, target, typical_mic, resistance_mechanism, 
             concentration_unit, spectrum) = result
            
            self.agent_class_var.set(agent_class)
            self.name_var.set(name)
            self.target_var.set(target if target else "")
            self.typical_mic_var.set(typical_mic if typical_mic else 0.0)
            self.resistance_mechanism_text.delete(1.0, tk.END)
            self.resistance_mechanism_text.insert(1.0, resistance_mechanism if resistance_mechanism else "")
            self.concentration_unit_var.set(concentration_unit if concentration_unit else "")
            self.spectrum_text.delete(1.0, tk.END)
            self.spectrum_text.insert(1.0, spectrum if spectrum else "")
            
            if self.status_bar:
                self.status_bar.config(text=f"Загружены данные для агента: {name}")
    
    def add_agent_class(self):
        """Добавление нового класса агента"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Добавить новый класс агента")
        dialog.geometry("300x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Название класса агента:").pack(pady=(20, 5))
        agent_class_entry = ttk.Entry(dialog, width=30)
        agent_class_entry.pack(pady=5)
        agent_class_entry.focus_set()
        
        def save_agent_class():
            agent_class_name = agent_class_entry.get().strip()
            if agent_class_name:
                # Проверяем, существует ли уже такой класс
                self.cursor.execute("SELECT COUNT(*) FROM antimicrobials WHERE agent_class = ?", (agent_class_name,))
                if self.cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Внимание", f"Класс агента '{agent_class_name}' уже существует!")
                else:
                    # Добавляем пример записи для нового класса
                    self.cursor.execute("""
                        INSERT INTO antimicrobials (agent_class, name, typical_mic, concentration_unit)
                        VALUES (?, 'Пример агента', 1.0, 'мг/л')
                    """, (agent_class_name,))
                    self.conn.commit()
                    self.load_agent_class_list()
                    dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите название класса агента!")
        
        ttk.Button(dialog, text="Сохранить", command=save_agent_class).pack(pady=10)
        
    def delete_agent_class(self):
        """Удаление выбранного класса агента"""
        selection = self.agent_class_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите класс агента для удаления!")
            return
            
        agent_class_name = self.agent_class_listbox.get(selection[0])
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить класс агента '{agent_class_name}' и все связанные агенты?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM antimicrobials WHERE agent_class = ?", (agent_class_name,))
            self.conn.commit()
            self.load_agent_class_list()
            self.agent_listbox.delete(0, tk.END)
            self.agent_index_to_id.clear()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Класс агента '{agent_class_name}' удален")
    
    def add_agent(self):
        """Добавление нового агента"""
        if not self.current_agent_class:
            messagebox.showwarning("Внимание", "Сначала выберите класс агента!")
            return
            
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Добавить новый агент для класса {self.current_agent_class}")
        dialog.geometry("400x150")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Название агента:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        name_entry.focus_set()
        
        def save_agent():
            agent_name = name_entry.get().strip()
            
            if agent_name:
                # Добавляем новую запись с минимальными данными
                self.cursor.execute("""
                    INSERT INTO antimicrobials (agent_class, name, typical_mic, concentration_unit)
                    VALUES (?, ?, 1.0, 'мг/л')
                """, (self.current_agent_class, agent_name))
                
                self.conn.commit()
                self.load_agent_list()
                dialog.destroy()
                
                if self.status_bar:
                    self.status_bar.config(text=f"Добавлен новый агент: {agent_name}")
            else:
                messagebox.showwarning("Внимание", "Введите название агента!")
        
        ttk.Button(frame, text="Сохранить", command=save_agent).grid(row=1, column=0, columnspan=2, pady=20)
        
        frame.columnconfigure(1, weight=1)
    
    def delete_agent(self):
        """Удаление выбранного агента"""
        selection = self.agent_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите агент для удаления!")
            return
            
        agent_id = self.agent_index_to_id.get(selection[0])
            
        if agent_id is None:
            
            return
        # Получаем информацию об агенте для сообщения
        self.cursor.execute("SELECT agent_class, name FROM antimicrobials WHERE id = ?", (agent_id,))
        agent_class, name = self.cursor.fetchone()
        
        if messagebox.askyesno("Подтверждение", 
                              f"Удалить агент '{name}'?\nЭто действие нельзя отменить!"):
            self.cursor.execute("DELETE FROM antimicrobials WHERE id = ?", (agent_id,))
            self.conn.commit()
            self.load_agent_list()
            self.clear_form()
            
            if self.status_bar:
                self.status_bar.config(text=f"Агент '{name}' удален")
    
    def save_changes(self):
        """Сохранение изменений в базе данных"""
        if not self.current_agent_id:
            messagebox.showwarning("Внимание", "Сначала выберите агент для редактирования!")
            return
            
        # Получаем данные из полей
        agent_class = self.agent_class_var.get().strip()
        name = self.name_var.get().strip()
        target = self.target_var.get()
        typical_mic = self.typical_mic_var.get()
        resistance_mechanism = self.resistance_mechanism_text.get(1.0, tk.END).strip()
        concentration_unit = self.concentration_unit_var.get()
        spectrum = self.spectrum_text.get(1.0, tk.END).strip()
        
        if not agent_class or not name:
            messagebox.showwarning("Внимание", "Заполните обязательные поля: Класс агента и Название!")
            return
        
        try:
            # Обновляем запись
            self.cursor.execute("""
                UPDATE antimicrobials 
                SET agent_class = ?, name = ?, target = ?, typical_mic = ?, 
                    resistance_mechanism = ?, concentration_unit = ?, spectrum = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                agent_class, name, target if target else None,
                typical_mic if typical_mic > 0 else None,
                resistance_mechanism, concentration_unit if concentration_unit else None,
                spectrum,
                self.current_agent_id
            ))
            
            self.conn.commit()
            
            # Обновляем списки
            if agent_class != self.current_agent_class:
                self.current_agent_class = agent_class
                self.load_agent_class_list()
                # Выделяем обновленный класс в списке
                index = self.agent_class_listbox.get(0, tk.END).index(agent_class)
                self.agent_class_listbox.selection_clear(0, tk.END)
                self.agent_class_listbox.selection_set(index)
                self.agent_class_listbox.see(index)
            
            self.load_agent_list()
            
            if self.status_bar:
                self.status_bar.config(text=f"Данные для агента {name} сохранены")
                
            messagebox.showinfo("Успех", "Изменения успешно сохранены!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения:\n{str(e)}")
    
    def clear_form(self):
        """Очистка формы"""
        self.agent_class_var.set("")
        self.name_var.set("")
        self.target_var.set("")
        self.typical_mic_var.set(0.0)
        self.resistance_mechanism_text.delete(1.0, tk.END)
        self.concentration_unit_var.set("")
        self.spectrum_text.delete(1.0, tk.END)
        
        self.current_agent_id = None
        
        # Снимаем выделение в списках
        self.agent_class_listbox.selection_clear(0, tk.END)
        self.agent_listbox.selection_clear(0, tk.END)
        self.agent_listbox.delete(0, tk.END)
        self.agent_index_to_id.clear()
        if self.status_bar:
            self.status_bar.config(text="Форма очищена")
    
    def refresh_lists(self):
        """Обновление списков"""
        self.load_agent_class_list()
        if self.current_agent_class:
            self.load_agent_list()
        
        if self.status_bar:
            self.status_bar.config(text="Списки обновлены")
    
    def __del__(self):
        """Закрытие соединения с базой данных при уничтожении объекта"""
        if hasattr(self, 'conn'):
            self.conn.close()

# Создаем атрибут items для Listbox для хранения ID
tk.Listbox.items = {}