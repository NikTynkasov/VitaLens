# work_space/menu_bar.py
"""
Модуль с реализацией главного меню рабочего пространства.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import sys
import importlib
from datetime import datetime


class WorkspaceMenuBar:
    """Главное меню рабочего пространства VitaLens."""

    def __init__(self, root, workspace_app):
        """
        Инициализирует главное меню.

        Args:
            root: Корневое окно Tk
            workspace_app: Экземпляр WorkspaceApp для доступа к методам
        """
        self.root = root
        self.app = workspace_app

        # Важно: верхнее меню лучше держать "чистым" — без эмодзи в названиях
        # (на Windows у Tk это часто приводит к визуальному сдвигу текста).
        self.menu_bar = tk.Menu(root)
        root.config(menu=self.menu_bar)

        # Инициализация всех меню
        self.setup_file_menu()
        self.setup_experiment_menu()
        self.setup_view_menu()
        self.setup_references_menu()
        self.setup_analysis_menu()
        self.setup_data_menu()
        self.setup_settings_menu()
        self.setup_help_menu()

        # Справочники (данные)
        self.references_data = {
            "microorganisms": [],
            "nutrient_media": [],
            "components": [],
            "interactions": [],
            "bioreactor_params": [],
            "antimicrobials": [],
            "metabolic_pathways": [],
            "protocols": []
        }

        # Загружаем данные справочников
        self.load_references_data()

    def setup_file_menu(self):
        """Создает меню 'Файл'."""
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Файл", menu=file_menu)

        file_menu.add_command(
            label="📄 Новый эксперимент",
            command=self.app.create_new_experiment,
            accelerator="Ctrl+N"
        )
        file_menu.add_command(
            label="📂 Открыть эксперимент...",
            command=self.open_experiment_dialog,
            accelerator="Ctrl+O"
        )
        file_menu.add_command(
            label="💾 Сохранить эксперимент",
            command=self.app.save_experiment,
            accelerator="Ctrl+S"
        )
        file_menu.add_command(
            label="💾 Сохранить как...",
            command=self.save_experiment_as,
            accelerator="Ctrl+Shift+S"
        )

        file_menu.add_separator()

        # Список последних файлов
        self.recent_files_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="📜 Последние файлы", menu=self.recent_files_menu)
        self.update_recent_files()

        file_menu.add_separator()

        file_menu.add_command(
            label="📤 Экспорт результатов...",
            command=self.app.export_results
        )
        file_menu.add_command(
            label="🖨️ Печать...",
            command=self.print_dialog,
            accelerator="Ctrl+P"
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="🚪 Выход",
            command=self.app.on_close,
            accelerator="Alt+F4"
        )

        # Бинды клавиш
        self.root.bind("<Control-n>", lambda e: self.app.create_new_experiment())
        self.root.bind("<Control-o>", lambda e: self.open_experiment_dialog())
        self.root.bind("<Control-s>", lambda e: self.app.save_experiment())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_experiment_as())
        self.root.bind("<Control-p>", lambda e: self.print_dialog())

    def setup_experiment_menu(self):
        """Создает меню 'Эксперимент'."""
        experiment_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Эксперимент", menu=experiment_menu)

        experiment_menu.add_command(
            label="🧪 Панель эксперимента",
            command=lambda: getattr(self.app, "show_experiment_panel", lambda: None)()
        )

        experiment_menu.add_separator()

        experiment_menu.add_command(
            label="▶️ Запустить симуляцию",
            command=self.app.start_simulation,
            accelerator="F5"
        )
        experiment_menu.add_command(
            label="⏸️ Остановить симуляцию",
            command=self.app.stop_simulation,
            accelerator="F6"
        )
        experiment_menu.add_command(
            label="🔄 Сбросить симуляцию",
            command=self.app.reset_simulation,
            accelerator="F7"
        )

        experiment_menu.add_separator()

        experiment_menu.add_command(
            label="➕ Добавить микроорганизм...",
            command=self.app.add_microorganism
        )
        experiment_menu.add_command(
            label="🧫 Добавить питательную среду...",
            command=self.app.add_nutrient
        )

        experiment_menu.add_separator()

        experiment_menu.add_command(
            label="🗑️ Очистить данные",
            command=self.clear_experiment_data
        )

        # Бинды клавиш
        self.root.bind("<F5>", lambda e: self.app.start_simulation())
        self.root.bind("<F6>", lambda e: self.app.stop_simulation())
        self.root.bind("<F7>", lambda e: self.app.reset_simulation())

    def setup_view_menu(self):
        """Создает меню 'Вид'."""
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Вид", menu=view_menu)

        # Подменю режимов визуализации
        visualization_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="🎨 Режим визуализации", menu=visualization_menu)

        self.visualization_var = tk.StringVar(value="Чашка Петри")
        modes = ["Чашка Петри", "График роста", "3D модель", "Тепловая карта", "Анимация роста"]
        for mode in modes:
            visualization_menu.add_radiobutton(
                label=mode,
                variable=self.visualization_var,
                value=mode,
                command=self.update_visualization_mode
            )

        # Подменю панелей инструментов
        panels_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="🧰 Панели инструментов", menu=panels_menu)

        self.panel_vars = {
            "monitoring": tk.BooleanVar(value=bool(getattr(self.app, "window_visibility", {}).get("monitoring", True))),
            "statusbar": tk.BooleanVar(value=bool(getattr(self.app, "window_visibility", {}).get("statusbar", True))),
            "icon_toolbar": tk.BooleanVar(value=bool(getattr(self.app, "window_visibility", {}).get("icon_toolbar", True))),
        }

        panels_menu.add_checkbutton(
            label="🧪 Панель эксперимента",
            variable=self.panel_vars["monitoring"],
            command=self.toggle_panels
        )
        panels_menu.add_checkbutton(
            label="📊 Строка состояния",
            variable=self.panel_vars["statusbar"],
            command=self.toggle_panels
        )
        panels_menu.add_checkbutton(
            label="🛠️ Панель инструментов",
            variable=self.panel_vars["icon_toolbar"],
            command=self.toggle_panels
        )
        view_menu.add_separator()

        view_menu.add_command(
            label="🔄 Обновить визуализацию",
            command=self.app.update_visualization,
            accelerator="F5"
        )

        view_menu.add_command(
            label="📸 Захватить изображение",
            command=self.app.capture_image
        )

        view_menu.add_separator()

        view_menu.add_command(
            label="🖥️ Полноэкранный режим",
            command=self.toggle_fullscreen,
            accelerator="F11"
        )

        # Бинд для полноэкранного режима
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.fullscreen = False

    def _open_growth_table(self):
        """Открыть окно 'Рост культуры' (табличная панель)."""
        # 1) Пробуем метод у приложения
        try:
            fn = getattr(self.app, "open_culture_growth_table", None)
            if callable(fn):
                fn()
                return
        except Exception:
            pass

        # 2) Пробуем импортировать helper из модуля culture_growth_table
        try:
            import importlib
            for mod_name in ("culture_growth_table", "work_space.culture_growth_table"):
                try:
                    mod = importlib.import_module(mod_name)
                    opener = getattr(mod, "open_culture_growth_table", None)
                    if callable(opener):
                        opener(self.app)
                        return
                except Exception:
                    continue
        except Exception:
            pass

    def setup_references_menu(self):
        """Создает меню 'Справочники'."""
        references_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Справочники", menu=references_menu)

        references_menu.add_command(
            label="🦠 Справочник «Микроорганизмы»",
            command=lambda: self.open_reference_book("microorganisms")
        )
        references_menu.add_command(
            label="🧫 Справочник «Питательные среды»",
            command=lambda: self.open_reference_book("nutrient_media")
        )
        references_menu.add_command(
            label="🧪 Справочник «Вещества-компоненты»",
            command=lambda: self.open_reference_book("components")
        )
        references_menu.add_command(
            label="🔄 Справочник «Типы взаимодействий»",
            command=lambda: self.open_reference_book("interactions")
        )
        references_menu.add_command(
            label="⚙️ Справочник «Параметры биореактора»",
            command=lambda: self.open_reference_book("bioreactor_params")
        )
        references_menu.add_command(
            label="💊 Справочник «Антимикробные агенты»",
            command=lambda: self.open_reference_book("antimicrobials")
        )
        references_menu.add_command(
            label="🔄 Справочник «Метаболические пути/продукты»",
            command=lambda: self.open_reference_book("metabolic_pathways")
        )
        references_menu.add_command(
            label="📋 Справочник «Экспериментальные протоколы»",
            command=lambda: self.open_reference_book("protocols")
        )

        references_menu.add_separator()

        references_menu.add_command(
            label="⚙️ Управление справочниками...",
            command=self.open_references_manager
        )
        references_menu.add_command(
            label="🔄 Импорт справочников...",
            command=self.import_references
        )
        references_menu.add_command(
            label="📤 Экспорт справочников...",
            command=self.export_references
        )

    def setup_analysis_menu(self):
        """Создает меню 'Анализ'."""
        analysis_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Анализ", menu=analysis_menu)

        analysis_menu.add_command(
            label="📈 Открыть анализ данных",
            command=self.app.open_analysis,
            accelerator="F2"
        )

        analysis_menu.add_separator()

        analysis_menu.add_command(
            label="📊 Статистический анализ",
            command=self.open_statistical_analysis
        )
        analysis_menu.add_command(
            label="🔄 Корреляционный анализ",
            command=self.open_correlation_analysis
        )

        graphs_menu = tk.Menu(analysis_menu, tearoff=0)
        analysis_menu.add_cascade(label="📈 Построить график...", menu=graphs_menu)

        graphs_menu.add_command(
            label="📈 График роста",
            command=lambda: self.create_plot("growth")
        )
        graphs_menu.add_command(
            label="🧪 График метаболитов",
            command=lambda: self.create_plot("metabolites")
        )
        graphs_menu.add_command(
            label="📊 Комбинированный график",
            command=lambda: self.create_plot("combined")
        )
        graphs_menu.add_command(
            label="🌡️ График параметров среды",
            command=lambda: self.create_plot("environment")
        )

        analysis_menu.add_command(
            label="🔮 Прогнозирование...",
            command=self.open_forecasting
        )
        analysis_menu.add_command(
            label="⚖️ Сравнить эксперименты",
            command=self.compare_experiments
        )

        analysis_menu.add_separator()

        analysis_menu.add_command(
            label="📋 Создать отчет",
            command=self.generate_report
        )

        self.root.bind("<F2>", lambda e: self.app.open_analysis())

    def setup_data_menu(self):
        """Создает меню 'Данные'."""
        data_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Данные", menu=data_menu)

        data_menu.add_command(
            label="👁️ Просмотр данных",
            command=self.open_data_viewer
        )
        data_menu.add_command(
            label="🔍 Фильтрация данных",
            command=self.open_data_filter
        )
        data_menu.add_command(
            label="🔎 Поиск в журнале",
            command=self.app.search_log
        )
        data_menu.add_command(
            label="🗑️ Очистить журнал",
            command=self.app.clear_log
        )

        data_menu.add_separator()

        data_menu.add_command(
            label="📤 Экспорт данных...",
            command=self.export_data_dialog
        )
        data_menu.add_command(
            label="📥 Импорт данных...",
            command=self.import_data_dialog
        )

        data_menu.add_separator()

        data_menu.add_command(
            label="🔄 Конвертировать данные...",
            command=self.convert_data_format
        )
        data_menu.add_command(
            label="🧹 Очистка данных...",
            command=self.data_cleaning
        )

    def setup_settings_menu(self):
        """Создает меню 'Настройки'."""
        settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Настройки", menu=settings_menu)

        settings_menu.add_command(
            label="🎨 Настройки интерфейса",
            command=self.open_ui_settings
        )
        settings_menu.add_command(
            label="⚙️ Настройки симуляции",
            command=self.open_simulation_settings
        )

        theme_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="🎨 Темы оформления", menu=theme_menu)

        self.theme_var = tk.StringVar(value="Светлая")
        themes = ["Светлая", "Темная", "Системная", "Контрастная", "Научная"]
        for theme in themes:
            theme_menu.add_radiobutton(
                label=theme,
                variable=self.theme_var,
                value=theme,
                command=self.apply_theme
            )

        settings_menu.add_command(
            label="🌐 Язык интерфейса",
            command=self.open_language_settings
        )

        settings_menu.add_separator()

        # Новая опция для настройки отображения окон
        settings_menu.add_command(
            label="🪟 Настройка отображения окон",
            command=self.open_window_visibility_settings
        )

        settings_menu.add_command(
            label="🔄 Сброс настроек",
            command=self.app.reset_settings
        )
        settings_menu.add_command(
            label="📥 Импорт настроек...",
            command=self.app.import_settings
        )
        settings_menu.add_command(
            label="📤 Экспорт настроек...",
            command=self.app.export_settings
        )

        settings_menu.add_separator()

        settings_menu.add_command(
            label="💾 Настройки автосохранения",
            command=self.open_autosave_settings
        )
        settings_menu.add_command(
            label="🔔 Настройки уведомлений",
            command=self.open_notification_settings
        )

    def setup_help_menu(self):
        """Создает меню 'Справка'."""
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Справка", menu=help_menu)

        help_menu.add_command(
            label="📖 Руководство пользователя",
            command=self.open_user_guide,
            accelerator="F1"
        )
        help_menu.add_command(
            label="ℹ️ О программе VitaLens",
            command=self.show_about_dialog
        )

        help_menu.add_separator()

        help_menu.add_command(
            label="🔄 Проверить обновления",
            command=self.check_for_updates
        )
        help_menu.add_command(
            label="🐛 Сообщить об ошибке",
            command=self.report_bug
        )
        help_menu.add_command(
            label="💡 Предложить улучшение",
            command=self.suggest_improvement
        )

        help_menu.add_separator()

        help_menu.add_command(
            label="📄 Лицензия",
            command=self.show_license
        )
        help_menu.add_command(
            label="🔗 Онлайн-справка",
            command=self.open_online_help
        )

        self.root.bind("<F1>", lambda e: self.open_user_guide())

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "ФАЙЛ"
    # ==========================

    def open_experiment_dialog(self):
        """Открывает диалог выбора файла эксперимента."""
        filetypes = [
            ("Файлы экспериментов", "*.json"),
            ("Все файлы", "*.*")
        ]

        filename = filedialog.askopenfilename(
            title="Открыть эксперимент",
            filetypes=filetypes,
            initialdir=os.path.join(os.path.dirname(__file__), "experiments")
        )

        if filename:
            self.app.add_log_entry(f"Открытие эксперимента: {filename}", "INFO")
            messagebox.showinfo("Открытие", f"Эксперимент будет загружен из:\n{filename}")
            self.add_to_recent_files(filename)

    def save_experiment_as(self):
        """Сохраняет эксперимент под новым именем."""
        if not self.app.current_experiment:
            messagebox.showwarning("Внимание", "Сначала создайте эксперимент")
            return

        filetypes = [
            ("Файлы экспериментов", "*.json"),
            ("Все файлы", "*.*")
        ]

        default_name = f"{self.app.exp_name_var.get()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filename = filedialog.asksaveasfilename(
            title="Сохранить эксперимент как",
            filetypes=filetypes,
            initialfile=default_name,
            defaultextension=".json"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.app.current_experiment, f, ensure_ascii=False, indent=2)

                messagebox.showinfo("Сохранение", f"Эксперимент сохранен в:\n{filename}")
                self.app.add_log_entry(f"Эксперимент сохранен как: {filename}", "SUCCESS")
                self.add_to_recent_files(filename)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

    def print_dialog(self):
        """Открывает диалог печати."""
        self.app.add_log_entry("Открытие диалога печати", "INFO")
        messagebox.showinfo("Печать", "Функция печати будет доступна в следующем обновлении")

    def update_recent_files(self):
        """Обновляет список последних файлов."""
        self.recent_files_menu.delete(0, tk.END)

        recent_files = self.load_recent_files()

        if not recent_files:
            self.recent_files_menu.add_command(
                label="Нет последних файлов",
                state=tk.DISABLED
            )
            return

        for i, filepath in enumerate(recent_files[:10]):
            display_name = os.path.basename(filepath)
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."

            self.recent_files_menu.add_command(
                label=f"{i + 1}. {display_name}",
                command=lambda fp=filepath: self.open_recent_file(fp)
            )

        self.recent_files_menu.add_separator()
        self.recent_files_menu.add_command(
            label="Очистить список",
            command=self.clear_recent_files
        )

    def add_to_recent_files(self, filepath):
        """Добавляет файл в список последних."""
        try:
            recent_file = os.path.join(os.path.dirname(__file__), "recent_files.json")

            if os.path.exists(recent_file):
                with open(recent_file, 'r', encoding='utf-8') as f:
                    recent_files = json.load(f)
            else:
                recent_files = []

            if filepath in recent_files:
                recent_files.remove(filepath)

            recent_files.insert(0, filepath)
            recent_files = recent_files[:15]

            with open(recent_file, 'w', encoding='utf-8') as f:
                json.dump(recent_files, f, ensure_ascii=False, indent=2)

            self.update_recent_files()

        except Exception as e:
            print(f"Ошибка сохранения списка последних файлов: {e}")

    def load_recent_files(self):
        """Загружает список последних файлов."""
        try:
            recent_file = os.path.join(os.path.dirname(__file__), "recent_files.json")
            if os.path.exists(recent_file):
                with open(recent_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return []

    def open_recent_file(self, filepath):
        """Открывает файл из списка последних."""
        if os.path.exists(filepath):
            self.app.add_log_entry(f"Открытие файла: {filepath}", "INFO")
            messagebox.showinfo("Открытие", f"Будет загружен файл:\n{filepath}")
        else:
            messagebox.showerror("Ошибка", f"Файл не найден:\n{filepath}")
            self.remove_from_recent_files(filepath)

    def clear_recent_files(self):
        """Очищает список последних файлов."""
        try:
            recent_file = os.path.join(os.path.dirname(__file__), "recent_files.json")
            if os.path.exists(recent_file):
                os.remove(recent_file)
            self.update_recent_files()
            self.app.add_log_entry("Список последних файлов очищен", "INFO")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось очистить список:\n{str(e)}")

    def remove_from_recent_files(self, filepath):
        """Удаляет файл из списка последних."""
        try:
            recent_files = self.load_recent_files()
            if filepath in recent_files:
                recent_files.remove(filepath)

                recent_file = os.path.join(os.path.dirname(__file__), "recent_files.json")
                with open(recent_file, 'w', encoding='utf-8') as f:
                    json.dump(recent_files, f, ensure_ascii=False, indent=2)

                self.update_recent_files()
        except:
            pass

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "ЭКСПЕРИМЕНТ"
    # ==========================



    def clear_experiment_data(self):
        """Очищает данные эксперимента."""
        if messagebox.askyesno("Подтверждение",
                               "Вы уверены, что хотите очистить все данные эксперимента?"):
            self.app.reset_simulation()
            self.app.microorganism_listbox.delete(0, tk.END)
            self.app.exp_desc_text.delete("1.0", tk.END)
            self.app.exp_desc_text.insert("1.0", "Исследование роста микроорганизмов")
            self.app.current_experiment = None
            self.app.add_log_entry("Данные эксперимента очищены", "INFO")

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "ВИД"
    # ==========================

    def update_visualization_mode(self):
        """Обновляет режим визуализации."""
        mode = self.visualization_var.get()
        self.app.visualization_mode.set(mode)
        self.app.update_visualization()
        self.app.add_log_entry(f"Режим визуализации изменен на: {mode}", "INFO")

    def toggle_panels(self):
        """Переключает видимость панелей."""
        # Обновляем настройки в приложении
        self.app.window_visibility["monitoring"] = self.panel_vars["monitoring"].get()
        self.app.window_visibility["statusbar"] = self.panel_vars["statusbar"].get()
        self.app.window_visibility["icon_toolbar"] = self.panel_vars["icon_toolbar"].get()
        
        # Сохраняем настройки
        self.app.save_window_visibility_settings()
        
        # Перестраиваем интерфейс
        self.app.rebuild_interface()
        
        self.app.add_log_entry("Настройки панелей изменены", "INFO")

    def toggle_fullscreen(self):
        """Переключает полноэкранный режим."""
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

        if not self.fullscreen:
            self.root.geometry("1200x800")

        self.app.add_log_entry(
            f"Полноэкранный режим {'включен' if self.fullscreen else 'выключен'}",
            "INFO"
        )

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "СПРАВОЧНИКИ"
    # ==========================

    def load_references_data(self):
        """Загружает данные справочников."""
        try:
            ref_dir = os.path.join(os.path.dirname(__file__), "references")
            if not os.path.exists(ref_dir):
                os.makedirs(ref_dir)
                self.create_default_references()
                return

            for ref_name in self.references_data.keys():
                ref_file = os.path.join(ref_dir, f"{ref_name}.json")
                if os.path.exists(ref_file):
                    with open(ref_file, 'r', encoding='utf-8') as f:
                        self.references_data[ref_name] = json.load(f)
                else:
                    with open(ref_file, 'w', encoding='utf-8') as f:
                        json.dump([], f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Ошибка загрузки справочников: {e}")
            self.create_default_references()

    def create_default_references(self):
        """Создает справочники по умолчанию."""
        self.references_data["microorganisms"] = [
            {"id": 1, "name": "Escherichia coli", "type": "Бактерия", "optimal_temp": 37.0, "optimal_ph": 7.0},
            {"id": 2, "name": "Saccharomyces cerevisiae", "type": "Дрожжи", "optimal_temp": 30.0, "optimal_ph": 5.5},
            {"id": 3, "name": "Bacillus subtilis", "type": "Бактерия", "optimal_temp": 37.0, "optimal_ph": 7.0},
            {"id": 4, "name": "Pseudomonas aeruginosa", "type": "Бактерия", "optimal_temp": 37.0, "optimal_ph": 7.2},
            {"id": 5, "name": "Lactococcus lactis", "type": "Бактерия", "optimal_temp": 30.0, "optimal_ph": 6.5}
        ]

        self.references_data["nutrient_media"] = [
            {"id": 1, "name": "LB-бульон", "description": "Лизиногенный бульон для выращивания бактерий"},
            {"id": 2, "name": "YPD-среда", "description": "Дрожжевая среда с пептоном и декстрозой"},
            {"id": 3, "name": "M9 минимальная среда", "description": "Минимальная среда для E. coli"}
        ]

        self.save_references_data()

    def save_references_data(self):
        """Сохраняет данные справочников."""
        try:
            ref_dir = os.path.join(os.path.dirname(__file__), "references")
            if not os.path.exists(ref_dir):
                os.makedirs(ref_dir)

            for ref_name, data in self.references_data.items():
                ref_file = os.path.join(ref_dir, f"{ref_name}.json")
                with open(ref_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Ошибка сохранения справочников: {e}")

    # ==========================
    # СПРАВОЧНИКИ (DB/GUI)
    # ==========================

    def _ensure_reference_books_import_paths(self):
        """Гарантирует, что каталоги со справочниками доступны для import.

        Поддерживает несколько вариантов структуры проекта и размещение menu_bar.py
        НЕ в корне проекта (например, ./work_space/menu_bar.py).

        Ищем каталоги вверх по дереву от текущего файла, пока не найдём:
        1) <root>/database/reference_books/*.py
        2) <root>/reference_books/*.py
        Также добавляем в sys.path:
        - <root> (для import database.reference_books.* при наличии __init__.py)
        - <root>/database (на случай прямых импортов из database)
        - <root>/database/reference_books и <root>/reference_books (для импортов по имени файла)
        """
        base_dir = os.path.abspath(os.path.dirname(__file__))

        # Поднимаемся вверх ограниченное число уровней, чтобы не засорять sys.path
        search_roots: list[str] = []
        cur = base_dir
        for _ in range(10):
            if cur not in search_roots:
                search_roots.append(cur)
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

        candidates: list[str] = []
        for r in search_roots:
            candidates.extend([
                os.path.join(r, "database", "reference_books"),
                os.path.join(r, "reference_books"),
                os.path.join(r, "database"),
                r,
            ])

        # Дедуп + вставка в sys.path (в начало, чтобы приоритет был выше)
        seen = set()
        for p in candidates:
            if p in seen:
                continue
            seen.add(p)
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)

    def _import_reference_window_class(self, ref_type):
        """Возвращает (WindowClass, resolved_module, resolved_class) или (None, None, None) при ошибке."""
        self._ensure_reference_books_import_paths()

        # ref_type -> список (module_name, class_name) в порядке предпочтения
        mapping = {
            "microorganisms": [
                ("microorganisms", "MicroorganismsWindow"),
                ("database.reference_books.microorganisms", "MicroorganismsWindow"),
            ],
            "nutrient_media": [
                ("culture_media", "CultureMediaWindow"),
                ("database.reference_books.culture_media", "CultureMediaWindow"),
            ],
            "components": [
                ("substances", "SubstancesWindow"),
                ("database.reference_books.substances", "SubstancesWindow"),
            ],
            "interactions": [
                ("interactions", "InteractionsWindow"),
                ("database.reference_books.interactions", "InteractionsWindow"),
            ],
            "bioreactor_params": [
                ("bioreactor_params", "BioreactorParamsWindow"),
                ("database.reference_books.bioreactor_params", "BioreactorParamsWindow"),
            ],
            "antimicrobials": [
                ("antimicrobials", "AntimicrobialsWindow"),
                ("database.reference_books.antimicrobials", "AntimicrobialsWindow"),
            ],
            "metabolic_pathways": [
                ("metabolic_pathways", "MetabolicPathwaysWindow"),
                ("database.reference_books.metabolic_pathways", "MetabolicPathwaysWindow"),
            ],
            "protocols": [
                ("experimental_protocols", "ExperimentalProtocolsWindow"),
                ("database.reference_books.experimental_protocols", "ExperimentalProtocolsWindow"),
                # fallback: в некоторых версиях проекта протоколы могли оказаться в metabolic_pathways.py
                ("metabolic_pathways", "ExperimentalProtocolsWindow"),
                ("database.reference_books.metabolic_pathways", "ExperimentalProtocolsWindow"),
            ],
        }

        attempts = mapping.get(ref_type, [])
        last_err = None

        for module_name, class_name in attempts:
            try:
                mod = importlib.import_module(module_name)
                cls = getattr(mod, class_name, None)
                if cls is None:
                    raise AttributeError(f"В модуле '{module_name}' нет класса '{class_name}'")
                return cls, module_name, class_name
            except Exception as e:
                last_err = e

        try:
            if last_err is not None:
                self.app.add_log_entry(f"Не удалось импортировать окно справочника '{ref_type}': {last_err}", "ERROR")
        except Exception:
            pass

        return None, None, None

    def _center_window(self, window):
        """Центрирует Toplevel относительно главного окна."""
        try:
            window.update_idletasks()
            w = window.winfo_width()
            h = window.winfo_height()

            if w <= 1 or h <= 1:
                geo = window.geometry().split("+")[0]
                if "x" in geo:
                    w, h = map(int, geo.split("x"))

            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (w // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (h // 2)
            window.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def open_reference_book(self, ref_type):
        """Открывает GUI1-справочник из database/reference_books.

        Если не удалось импортировать окно справочника — откроется legacy-диалог (JSON),
        чтобы пункт меню не ломался.
        """
        ref_names = {
            "microorganisms": "Микроорганизмы",
            "nutrient_media": "Питательные среды",
            "components": "Вещества-компоненты",
            "interactions": "Типы взаимодействий",
            "bioreactor_params": "Параметры биореактора",
            "antimicrobials": "Антимикробные агенты",
            "metabolic_pathways": "Метаболические пути/продукты",
            "protocols": "Экспериментальные протоколы",
        }

        pretty_name = ref_names.get(ref_type, ref_type)
        try:
            self.app.add_log_entry(f"Открытие справочника (GUI/DB): {pretty_name}", "INFO")
        except Exception:
            pass

        WindowClass, _, _ = self._import_reference_window_class(ref_type)
        if WindowClass is None:
            messagebox.showwarning(
                "Справочник недоступен",
                f"Не удалось открыть GUI-справочник '{pretty_name}'.\nОткроется встроенный (legacy) просмотр."
            )
            return self.open_reference_dialog(ref_type)

        win = tk.Toplevel(self.root)
        win.transient(self.root)
        win.grab_set()

        status_bar = getattr(self.app, "status_bar", None)
        try:
            WindowClass(win, status_bar)
        except TypeError:
            WindowClass(win)

        self._center_window(win)

    def open_reference_dialog(self, ref_type):
        """Открывает диалог просмотра справочника."""
        ref_names = {
            "microorganisms": "Микроорганизмы",
            "nutrient_media": "Питательные среды",
            "components": "Вещества-компоненты",
            "interactions": "Типы взаимодействий",
            "bioreactor_params": "Параметры биореактора",
            "antimicrobials": "Антимикробные агенты",
            "metabolic_pathways": "Метаболические пути/продукты",
            "protocols": "Экспериментальные протоколы"
        }

        ref_name = ref_names.get(ref_type, ref_type)
        self.app.add_log_entry(f"Открытие справочника: {ref_name}", "INFO")

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Справочник: {ref_name}")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (800 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (600 // 2)
        dialog.geometry(f"800x600+{x}+{y}")

        ttk.Label(dialog, text=f"📚 {ref_name}",
                  font=("Segoe UI", 14, "bold")).pack(pady=10)

        canvas = tk.Canvas(dialog, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        data = self.references_data.get(ref_type, [])

        if not data:
            ttk.Label(scrollable_frame, text="Справочник пуст",
                      font=("Segoe UI", 12)).pack(pady=50)
        else:
            if ref_type == "microorganisms":
                headers = ["ID", "Название", "Тип", "Температура", "pH"]
                for i, header in enumerate(headers):
                    ttk.Label(scrollable_frame, text=header, font=("Segoe UI", 10, "bold"),
                              borderwidth=1, relief="solid", width=15).grid(row=0, column=i, sticky="nsew",
                                                                            padx=1, pady=1)

                for row_idx, item in enumerate(data, 1):
                    ttk.Label(scrollable_frame, text=str(item.get("id", "")),
                              borderwidth=1, relief="solid", width=15).grid(row=row_idx, column=0, sticky="nsew",
                                                                            padx=1, pady=1)
                    ttk.Label(scrollable_frame, text=item.get("name", ""),
                              borderwidth=1, relief="solid", width=15).grid(row=row_idx, column=1, sticky="nsew",
                                                                            padx=1, pady=1)
                    ttk.Label(scrollable_frame, text=item.get("type", ""),
                              borderwidth=1, relief="solid", width=15).grid(row=row_idx, column=2, sticky="nsew",
                                                                            padx=1, pady=1)
                    ttk.Label(scrollable_frame, text=str(item.get("optimal_temp", "")),
                              borderwidth=1, relief="solid", width=15).grid(row=row_idx, column=3, sticky="nsew",
                                                                            padx=1, pady=1)
                    ttk.Label(scrollable_frame, text=str(item.get("optimal_ph", "")),
                              borderwidth=1, relief="solid", width=15).grid(row=row_idx, column=4, sticky="nsew",
                                                                            padx=1, pady=1)
            else:
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        text = f"{item.get('id', i + 1)}. {item.get('name', 'Без названия')}"
                        if 'description' in item:
                            text += f" - {item['description']}"
                    else:
                        text = f"{i + 1}. {str(item)}"

                    ttk.Label(scrollable_frame, text=text,
                              font=("Segoe UI", 10)).pack(anchor=tk.W, pady=2)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Добавить запись",
                   command=lambda: self.add_reference_item(ref_type, dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Редактировать",
                   command=lambda: self.edit_reference_item(ref_type, dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Удалить",
                   command=lambda: self.delete_reference_item(ref_type, dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Закрыть",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def add_reference_item(self, ref_type, parent_dialog):
        """Добавляет запись в справочник."""
        self.app.add_log_entry(f"Добавление записи в справочник {ref_type}", "INFO")
        messagebox.showinfo("Добавление", f"Функция добавления записей в справочник '{ref_type}' "
                                          "будет доступна в следующем обновлении")

    def edit_reference_item(self, ref_type, parent_dialog):
        """Редактирует запись в справочнике."""
        self.app.add_log_entry(f"Редактирование записи в справочнике {ref_type}", "INFO")
        messagebox.showinfo("Редактирование", f"Функция редактирования записей в справочнике '{ref_type}' "
                                             "будет доступна в следующем обновлении")

    def delete_reference_item(self, ref_type, parent_dialog):
        """Удаляет запись из справочника."""
        self.app.add_log_entry(f"Удаление записи в справочнике {ref_type}", "INFO")
        messagebox.showinfo("Удаление", f"Функция удаления записей в справочнике '{ref_type}' "
                                        "будет доступна в следующем обновлении")

    def open_references_manager(self):
        """Открывает менеджер справочников."""
        self.app.add_log_entry("Открытие менеджера справочников", "INFO")
        messagebox.showinfo("Менеджер справочников",
                            "Менеджер справочников будет доступен в следующем обновлении")

    def import_references(self):
        """Импортирует справочники из файла."""
        self.app.add_log_entry("Импорт справочников", "INFO")
        messagebox.showinfo("Импорт", "Функция импорта справочников будет доступна в следующем обновлении")

    def export_references(self):
        """Экспортирует справочники в файл."""
        self.app.add_log_entry("Экспорт справочников", "INFO")
        messagebox.showinfo("Экспорт", "Функция экспорта справочников будет доступна в следующем обновлении")

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "АНАЛИЗ"
    # ==========================

    def open_statistical_analysis(self):
        """Открывает статистический анализ."""
        self.app.add_log_entry("Открытие статистического анализа", "INFO")
        messagebox.showinfo("Статистический анализ",
                            "Модуль статистического анализа будет доступен в следующем обновлении")

    def open_correlation_analysis(self):
        """Открывает коррреляционный анализ."""
        self.app.add_log_entry("Открытие корреляционного анализа", "INFO")
        messagebox.showinfo("Корреляционный анализ",
                            "Модуль корреляционного анализа будет доступен в следующем обновлении")

    def create_plot(self, plot_type):
        """Создает график указанного типа."""
        self.app.add_log_entry(f"Создание графика: {plot_type}", "INFO")
        messagebox.showinfo("Создание графика",
                            f"Функция создания графика '{plot_type}' будет доступна в следующем обновлении")

    def open_forecasting(self):
        """Открывает модуль прогнозирования."""
        self.app.add_log_entry("Открытие модуля прогнозирования", "INFO")
        messagebox.showinfo("Прогнозирование",
                            "Модуль прогнозирования будет доступен в следующем обновлении")

    def compare_experiments(self):
        """Сравнивает эксперименты."""
        self.app.add_log_entry("Сравнение экспериментов", "INFO")
        messagebox.showinfo("Сравнение",
                            "Функция сравнения экспериментов будет доступна в следующем обновлении")

    def generate_report(self):
        """Генерирует отчет."""
        self.app.add_log_entry("Генерация отчета", "INFO")
        messagebox.showinfo("Отчет",
                            "Функция генерации отчетов будет доступна в следующем обновлении")

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "ДАННЫЕ"
    # ==========================

    def open_data_viewer(self):
        """Открывает просмотрщик данных."""
        self.app.add_log_entry("Открытие просмотрщика данных", "INFO")
        messagebox.showinfo("Просмотр данных",
                            "Просмотрщик данных будет доступен в следующем обновлении")

    def open_data_filter(self):
        """Открывает фильтр данных."""
        self.app.add_log_entry("Открытие фильтра данных", "INFO")
        messagebox.showinfo("Фильтрация данных",
                            "Фильтр данных будет доступен в следующем обновлении")

    def export_data_dialog(self):
        """Открывает диалог экспорта данных."""
        self.app.add_log_entry("Экспорт данных", "INFO")
        messagebox.showinfo("Экспорт данных",
                            "Диалог экспорта данных будет доступен в следующем обновлении")

    def import_data_dialog(self):
        """Открывает диалог импорта данных."""
        self.app.add_log_entry("Импорт данных", "INFO")
        messagebox.showinfo("Импорт данных",
                            "Диалог импорта данных будет доступен в следующем обновлении")

    def convert_data_format(self):
        """Конвертирует формат данных."""
        self.app.add_log_entry("Конвертация формата данных", "INFO")
        messagebox.showinfo("Конвертация",
                            "Функция конвертации данных будет доступна в следующем обновлении")

    def data_cleaning(self):
        """Открывает инструмент очистки данных."""
        self.app.add_log_entry("Очистка данных", "INFO")
        messagebox.showinfo("Очистка данных",
                            "Инструмент очистки данных будет доступен в следующем обновлении")

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "НАСТРОЙКИ"
    # ==========================

    def open_ui_settings(self):
        """Открывает настройки интерфейса."""
        self.app.add_log_entry("Открытие настроек интерфейса", "INFO")
        self.app.apply_settings()

    def open_window_visibility_settings(self):
        """Открывает настройки отображения окон."""
        self.app.add_log_entry("Открытие настроек отображения окон", "INFO")
        self.app.open_window_settings_dialog()

    def open_simulation_settings(self):
        """Открывает настройки симуляции."""
        self.app.add_log_entry("Открытие настроек симуляции", "INFO")
        messagebox.showinfo("Настройки симуляции",
                            "Расширенные настройки симуляции будут доступны в следующем обновлении")

    def apply_theme(self):
        """Применяет выбранную тему."""
        theme = self.theme_var.get()
        self.app.add_log_entry(f"Применение темы: {theme}", "INFO")
        messagebox.showinfo("Тема", f"Тема '{theme}' будет применена в следующем обновлении")

    def open_language_settings(self):
        """Открывает настройки языка."""
        self.app.add_log_entry("Открытие настроек языка", "INFO")
        messagebox.showinfo("Язык",
                            "Настройки языка будут доступны в следующем обновлении")

    def open_autosave_settings(self):
        """Открывает настройки автосохранения."""
        self.app.add_log_entry("Открытие настроек автосохранения", "INFO")
        messagebox.showinfo("Автосохранение",
                            "Настройки автосохранения будут доступны в следующем обновлении")

    def open_notification_settings(self):
        """Открывает настройки уведомлений."""
        self.app.add_log_entry("Открытие настроек уведомлений", "INFO")
        messagebox.showinfo("Уведомления",
                            "Настройки уведомлений будут доступны в следующем обновлении")

    # ==========================
    # МЕТОДЫ ДЛЯ МЕНЮ "СПРАВКА"
    # ==========================

    def open_user_guide(self):
        """Открывает руководство пользователя."""
        self.app.add_log_entry("Открытие руководства пользователя", "INFO")
        messagebox.showinfo("Руководство пользователя",
                            "Руководство пользователя будет доступно в следующем обновлении")

    def show_about_dialog(self):
        """Показывает диалог 'О программе'."""
        about_text = """VitaLens - Рабочее пространство для экспериментов

Версия: 1.0.0
Разработчик: Тынкасов Николай Павлович

Описание: Программа для симуляции и анализа
роста микроорганизмов в различных условиях.

© 2024 Все права защищены."""
        messagebox.showinfo("О программе VitaLens", about_text)
        self.app.add_log_entry("Открытие диалога 'О программе'", "INFO")

    def check_for_updates(self):
        """Проверяет наличие обновлений."""
        self.app.add_log_entry("Проверка обновлений", "INFO")
        messagebox.showinfo("Обновления",
                            "Проверка обновлений будет доступна в следующем обновлении")

    def report_bug(self):
        """Открывает форму сообщения об ошибке."""
        self.app.add_log_entry("Открытие формы сообщения об ошибке", "INFO")
        messagebox.showinfo("Сообщить об ошибке",
                            "Форма сообщения об ошибке будет доступна в следующем обновлении")

    def suggest_improvement(self):
        """Открывает форму предложения улучшений."""
        self.app.add_log_entry("Открытие формы предложений", "INFO")
        messagebox.showinfo("Предложить улучшение",
                            "Форма предложения улучшений будет доступна в следующем обновлении")

    def show_license(self):
        """Показывает лицензионное соглашение."""
        license_text = """Лицензионное соглашение

1. Данное программное обеспечение предоставляется "как есть".
2. Автор не несет ответственности за любые последствия использования ПО.
3. Запрещено коммерческое использование без разрешения автора.
4. Разрешается использование в учебных и научных целях."""
        messagebox.showinfo("Лицензионное соглашение", license_text)
        self.app.add_log_entry("Открытие лицензионного соглашения", "INFO")

    def open_online_help(self):
        """Открывает онлайн-справку."""
        self.app.add_log_entry("Открытие онлайн-справки", "INFO")
        messagebox.showinfo("Онлайн-справка",
                            "Онлайн-справка будет доступна в следующем обновлении")


def create_menu_bar(root, workspace_app):
    """
    Создает главное меню для рабочего пространства.

    Args:
        root: Корневое окно Tk
        workspace_app: Экземпляр WorkspaceApp

    Returns:
        Экземпляр WorkspaceMenuBar
    """
    return WorkspaceMenuBar(root, workspace_app)
