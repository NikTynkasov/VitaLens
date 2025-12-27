# [file database/guide.py]
# Главный запускаемый файл для управления справочниками

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Добавляем путь к модулям справочников (если guide.py запускается напрямую)
sys.path.append(os.path.join(os.path.dirname(__file__), "reference_books"))

from reference_books.microorganisms import MicroorganismsWindow
from reference_books.culture_media import CultureMediaWindow
from reference_books.substances import SubstancesWindow
from reference_books.interactions import InteractionsWindow
from reference_books.bioreactor_params import BioreactorParamsWindow
from reference_books.antimicrobials import AntimicrobialsWindow
from reference_books.metabolic_pathways import MetabolicPathwaysWindow
from reference_books.experimental_protocols import ExperimentalProtocolsWindow


class MainApplication:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Симулятор роста микроорганизмов - Справочники")
        self.root.geometry("800x600")

        # Проверяем наличие базы данных
        self.check_database()

        # Создаем главное меню
        self.create_menu()

        # Создаем главный интерфейс
        self.create_main_interface()

    def check_database(self) -> None:
        """Проверка и инициализация базы данных (единый выбор файла БД)."""
        try:
            # если guide.py в пакете database
            from .database import ensure_database
        except Exception:
            # если guide.py запускается как скрипт из каталога
            try:
                from database.database import ensure_database
            except Exception:
                from database import ensure_database

        ensure_database()

    def create_menu(self) -> None:
        """Создание главного меню."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Выход", command=self.root.quit)

        # Меню Справочники
        reference_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справочники", menu=reference_menu)
        reference_menu.add_command(label="Микроорганизмы", command=self.open_microorganisms)
        reference_menu.add_command(label="Питательные среды", command=self.open_culture_media)
        reference_menu.add_command(label="Вещества-компоненты", command=self.open_substances)
        reference_menu.add_command(label="Типы взаимодействий", command=self.open_interactions)
        reference_menu.add_command(label="Параметры биореактора", command=self.open_bioreactor_params)
        reference_menu.add_command(label="Антимикробные агенты", command=self.open_antimicrobials)
        reference_menu.add_command(label="Метаболические пути/продукты", command=self.open_metabolic_pathways)
        reference_menu.add_command(label="Экспериментальные протоколы", command=self.open_experimental_protocols)

        # Меню Помощь
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Помощь", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)

    def create_main_interface(self) -> None:
        """Создание главного интерфейса."""
        # Заголовок
        title_label = tk.Label(
            self.root,
            text="Система управления справочниками для симуляции роста микроорганизмов",
            font=("Arial", 16, "bold"),
            pady=20,
        )
        title_label.pack()

        # Описание
        desc_label = tk.Label(
            self.root,
            text=(
                "Выберите справочник для просмотра и редактирования данных,\n"
                "используемых в моделировании роста микроорганизмов."
            ),
            font=("Arial", 12),
            pady=10,
        )
        desc_label.pack()

        # Фрейм для кнопок справочников
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(expand=True, fill=tk.BOTH)

        # Создаем кнопки для каждого справочника в сетке 4x2
        buttons = [
            ("Микроорганизмы", self.open_microorganisms),
            ("Питательные среды", self.open_culture_media),
            ("Вещества-компоненты", self.open_substances),
            ("Типы взаимодействий", self.open_interactions),
            ("Параметры биореактора", self.open_bioreactor_params),
            ("Антимикробные агенты", self.open_antimicrobials),
            ("Метаболические пути", self.open_metabolic_pathways),
            ("Экспериментальные протоколы", self.open_experimental_protocols),
        ]

        for i, (text, command) in enumerate(buttons):
            row = i // 2
            col = i % 2

            btn = tk.Button(
                frame,
                text=text,
                command=command,
                width=25,
                height=3,
                font=("Arial", 12),
            )
            btn.grid(row=row, column=col, padx=10, pady=10, sticky=(tk.W, tk.E))

        # Настройка весов для расширения
        for i in range(4):
            frame.rowconfigure(i, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        # Статус бар
        self.status_bar = tk.Label(
            self.root,
            text="Готово",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padx=5,
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def open_microorganisms(self) -> None:
        """Открыть справочник микроорганизмов."""
        window = tk.Toplevel(self.root)
        MicroorganismsWindow(window, self.status_bar)

    def open_culture_media(self) -> None:
        """Открыть справочник питательных сред."""
        window = tk.Toplevel(self.root)
        CultureMediaWindow(window, self.status_bar)

    def open_substances(self) -> None:
        """Открыть справочник веществ-компонентов."""
        window = tk.Toplevel(self.root)
        SubstancesWindow(window, self.status_bar)

    def open_interactions(self) -> None:
        """Открыть справочник типов взаимодействий."""
        window = tk.Toplevel(self.root)
        InteractionsWindow(window, self.status_bar)

    def open_bioreactor_params(self) -> None:
        """Открыть справочник параметров биореактора."""
        window = tk.Toplevel(self.root)
        BioreactorParamsWindow(window, self.status_bar)

    def open_antimicrobials(self) -> None:
        """Открыть справочник антимикробных агентов."""
        window = tk.Toplevel(self.root)
        AntimicrobialsWindow(window, self.status_bar)

    def open_metabolic_pathways(self) -> None:
        """Открыть справочник метаболических путей/продуктов."""
        window = tk.Toplevel(self.root)
        MetabolicPathwaysWindow(window, self.status_bar)

    def open_experimental_protocols(self) -> None:
        """Открыть справочник экспериментальных протоколов."""
        window = tk.Toplevel(self.root)
        ExperimentalProtocolsWindow(window, self.status_bar)

    def show_about(self) -> None:
        """Показать информацию о программе."""
        messagebox.showinfo(
            "О программе",
            "Симулятор роста и взаимодействия микроорганизмов\n\n"
            "Версия 1.0\n"
            "Для ускорения изыскательных работ в микробиологии\n\n"
            "Разработано с использованием Python и SQLite",
        )

    def update_status(self, message: str) -> None:
        """Обновить статус бар."""
        self.status_bar.config(text=message)
        self.root.update_idletasks()


if __name__ == "__main__":
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()
