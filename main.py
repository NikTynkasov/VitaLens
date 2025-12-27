#[file name]: main.py

import os
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import time
import threading
import math
import platform
import ctypes
import traceback


# ==========================
#   НАСТРОЙКИ И КОНСТАНТЫ
# ==========================

APP_TITLE = "VitaLens (Virtual Laboratory Environment for Natural Simulations)"
APP_VERSION = "v1.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VESSEL_IMG_DIR = os.path.join(BASE_DIR, "images", "vessels")

BACKGROUND_IMG_PATH = os.path.join(BASE_DIR, "images", "background.png")
EXIT_IMG_PATH = os.path.join(BASE_DIR, "images", "btn_exit.png")
ABOUT_IMG_PATH = os.path.join(BASE_DIR, "images", "btn_info.png")
LOGO_IMG_PATH = os.path.join(BASE_DIR, "images", "logo.png")
NEW_EXP_IMG_PATH = os.path.join(BASE_DIR, "images", "new_exp.png")  # Новая кнопка
VIEW_EXP_IMG_PATH = os.path.join(BASE_DIR, "images", "view_exp.png")  # Новая кнопка

# Размер окна 500x500 как просили
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 500


class MainMenuApp(tk.Tk):
    """
    Главное окно приложения без рамок и заголовка.
    """

    def __init__(self) -> None:
        super().__init__()

        # Убираем заголовок и рамки окна
        self.overrideredirect(True)
        
        # Устанавливаем прозрачный цвет для окна (будет использоваться как маска прозрачности)
        self.configure(bg='black')
        
        # Устанавливаем атрибут прозрачности цвета для поддержки альфа-канала
        self.attributes('-transparentcolor', 'black')
        
        # Загружаем логотип
        self._logo_image = self._load_logo_image()
        
        # Загружаем изображения кнопок
        self._new_exp_image = None
        self._view_exp_image = None
        self._exit_icon = None
        self._about_icon = None
        
        # Устанавливаем фиксированный размер окна 500x500
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.resizable(False, False)

        # Центрирование окна
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (WINDOW_WIDTH // 2)
        y = (self.winfo_screenheight() // 2) - (WINDOW_HEIGHT // 2)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

        # Основной контейнер с прозрачным фоном
        self.container = tk.Frame(self, bg="black")
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas для рисования с прозрачным фоном
        self.canvas = tk.Canvas(self.container, highlightthickness=0, bd=0, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Переменные для анимации
        self.window_alpha = 0.0  # Прозрачность окна (0.0-1.0)
        self.buttons_visible = False  # Видимость кнопок
        
        # Хранилище для элементов кнопок
        self.button_items = []
        
        # Запускаем анимацию появления
        self._animate_startup()

    # ==========================
    #   АНИМАЦИЯ ЗАПУСКА
    # ==========================

    def _animate_startup(self):
        """Анимация появления интерфейса."""
        # Начальная прозрачность окна
        self.attributes('-alpha', 0.0)
        
        # Сначала рисуем логотип (невидимый)
        self._draw_logo_background()
        
        # Шаг 1: Плавное появление окна с логотипом (2 секунды)
        self._fade_in_window()
        
        # Шаг 2: Через 2 секунды начинаем плавное появление кнопок (1 секунда)
        self.after(2000, self._fade_in_buttons)

    def _fade_in_window(self, step=0):
        """Плавное появление окна за 2 секунды."""
        if step <= 20:  # 20 шагов за 2 секунды (100ms каждый)
            self.window_alpha = step / 20
            
            # Устанавливаем прозрачность окна
            try:
                self.attributes('-alpha', self.window_alpha)
            except:
                pass
            
            # Следующий шаг
            if step < 20:
                # Используем именованную функцию вместо лямбды
                self.after(100, lambda s=step+1: self._fade_in_window(s))
            else:
                # Окончание анимации - окно полностью видимо
                self.attributes('-alpha', 1.0)

    def _draw_logo_background(self):
        """Отрисовывает логотип как фон."""
        # Очищаем canvas
        self.canvas.delete("all")
        
        if self._logo_image:
            # Растягиваем логотип на весь canvas 500x500
            self.canvas.create_image(
                0,
                0,
                image=self._logo_image,
                anchor="nw",
                tags="logo"
            )
        else:
            # Фолбэк - черный фон с текстом
            self.canvas.create_rectangle(
                0, 0, WINDOW_WIDTH, WINDOW_HEIGHT,
                fill="black",
                outline=""
            )
            self.canvas.create_text(
                WINDOW_WIDTH // 2,
                WINDOW_HEIGHT // 2,
                text="VitaLens",
                font=("Segoe UI", 48, "bold"),
                fill="white",
                tags="logo"
            )

    def _fade_in_buttons(self, step=0):
        """Плавное появление кнопок за 1 секунду."""
        if step == 0:
            # Отрисовываем кнопки (пока невидимые)
            self._create_buttons()
            # Скрываем все элементы кнопок
            for item in self.button_items:
                self.canvas.itemconfig(item, state='hidden')
        
        if step <= 20:  # 20 шагов за 1 секунду (50ms каждый)
            # Показываем кнопки с текущей прозрачностью
            if step > 0:  # На первом шаге еще скрыты
                for item in self.button_items:
                    self.canvas.itemconfig(item, state='normal')
                    # Применяем эффект плавного появления через изменение прозрачности окна
                    if step < 20:
                        # Создаем эффект плавного появления
                        alpha = step / 20
                        self._apply_alpha_effect(item, alpha)
            
            # Следующий шаг
            if step < 20:
                # Используем именованную функцию вместо лямбды
                self.after(50, lambda s=step+1: self._fade_in_buttons(s))
            else:
                # Кнопки полностью видны
                self.buttons_visible = True
                for item in self.button_items:
                    self.canvas.itemconfig(item, state='normal')

    def _apply_alpha_effect(self, item_id, alpha):
        """Применяет эффект прозрачности к элементу canvas."""
        item_type = self.canvas.type(item_id)
        tags = self.canvas.gettags(item_id)
        
        # Пропускаем логотип
        if "logo" in tags:
            return
            
        if alpha < 1.0:
            # Для изображений можно добавить эффект затемнения/осветления
            if item_type == "image":
                # Для эффекта прозрачности временно изменяем яркость
                pass  # Tkinter не поддерживает прозрачность изображений напрямую

    # ==========================
    #   СОЗДАНИЕ КНОПОК
    # ==========================

    def _create_buttons(self):
        """Создает кнопки-картинки на canvas."""
        # Очищаем список элементов кнопок
        self.button_items = []
        
        # Загружаем изображения кнопок
        new_exp_img = self._get_new_exp_image()
        view_exp_img = self._get_view_exp_image()
        
        # Две основные кнопки-картинки
        button_specs = [
            (new_exp_img, "Новый эксперимент", self._on_new_experiment, "new_exp_btn"),
            (view_exp_img, "Просмотр экспериментов", self._on_view_experiments, "view_exp_btn"),
        ]

        button_size = 70  # 70x70 пикселей (размер изображений)
        spacing = 280  # Расстояние между кнопками

        total_width = len(button_specs) * button_size + (len(button_specs) - 1) * spacing
        start_x = (WINDOW_WIDTH - total_width) // 2 + button_size // 2
        buttons_center_y = WINDOW_HEIGHT // 2 - 180  # Выше центра

        for idx, (image, tooltip_text, command, tag_name) in enumerate(button_specs):
            if image is None:
                # Если изображение не загрузилось, создаем текстовую кнопку
                self._create_fallback_button(idx, start_x, buttons_center_y, button_size, spacing, 
                                            tooltip_text, command, tag_name)
                continue
                
            cx = start_x + idx * (button_size + spacing)
            x0 = cx - button_size // 2
            y0 = buttons_center_y - button_size // 2
            x1 = cx + button_size // 2
            y1 = buttons_center_y + button_size // 2

            tag = tag_name

            # Изображение кнопки (без фона)
            img_id = self.canvas.create_image(
                cx,
                buttons_center_y,
                image=image,
                tags=(tag, "button", "button_image"),
            )
            self.button_items.append(img_id)

            # Невидимая область для кликов (прямоугольник по размеру изображения)
            click_id = self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="",
                fill="",
                tags=(tag, "button", "click_area")
            )
            self.button_items.append(click_id)

            # Обработчики событий для кнопки
            self._bind_button_events(tag, img_id, command)

        # ===== НИЖНИЕ КНОПКИ (ИКОНКИ) =====
        bottom_y = WINDOW_HEIGHT - 30
        btn_size = 20  # Размер иконок

        # "О программе" — слева
        about_cx = 20 + btn_size // 2
        about_tag = "about_btn"

        about_icon = self._get_about_icon()
        if about_icon is not None:
            about_icon_id = self.canvas.create_image(
                about_cx,
                bottom_y,
                image=about_icon,
                tags=(about_tag, "button", "bottom_button"),
            )
            self.button_items.append(about_icon_id)
            
            # Область клика для иконки "О программе"
            about_click_id = self.canvas.create_rectangle(
                about_cx - btn_size // 2, bottom_y - btn_size // 2,
                about_cx + btn_size // 2, bottom_y + btn_size // 2,
                outline="",
                fill="",
                tags=(about_tag, "button", "click_area")
            )
            self.button_items.append(about_click_id)
        else:
            about_text_id = self.canvas.create_text(
                about_cx,
                bottom_y,
                text="ⓘ",
                font=("Segoe UI", 12, "bold"),
                fill="#e5e7eb",
                tags=(about_tag, "button", "bottom_button"),
            )
            self.button_items.append(about_text_id)
            
            about_click_id = self.canvas.create_rectangle(
                about_cx - btn_size // 2, bottom_y - btn_size // 2,
                about_cx + btn_size // 2, bottom_y + btn_size // 2,
                outline="",
                fill="",
                tags=(about_tag, "button", "click_area")
            )
            self.button_items.append(about_click_id)

        # "Выход" — справа
        exit_cx = WINDOW_WIDTH - (25 + btn_size // 2)
        exit_tag = "exit_btn"

        exit_icon = self._get_exit_icon()
        if exit_icon is not None:
            exit_icon_id = self.canvas.create_image(
                exit_cx,
                bottom_y,
                image=exit_icon,
                tags=(exit_tag, "button", "bottom_button"),
            )
            self.button_items.append(exit_icon_id)
            
            # Область клика для иконки "Выход"
            exit_click_id = self.canvas.create_rectangle(
                exit_cx - btn_size // 2, bottom_y - btn_size // 2,
                exit_cx + btn_size // 2, bottom_y + btn_size // 2,
                outline="",
                fill="",
                tags=(exit_tag, "button", "click_area")
            )
            self.button_items.append(exit_click_id)
        else:
            exit_text_id = self.canvas.create_text(
                exit_cx,
                bottom_y,
                text="⏻",
                font=("Segoe UI", 12, "bold"),
                fill="#fee2e2",
                tags=(exit_tag, "button", "bottom_button"),
            )
            self.button_items.append(exit_text_id)
            
            exit_click_id = self.canvas.create_rectangle(
                exit_cx - btn_size // 2, bottom_y - btn_size // 2,
                exit_cx + btn_size // 2, bottom_y + btn_size // 2,
                outline="",
                fill="",
                tags=(exit_tag, "button", "click_area")
            )
            self.button_items.append(exit_click_id)

        # Привязка событий к нижним кнопкам
        self._bind_icon_button_events(about_tag, self.on_about)
        self._bind_icon_button_events(exit_tag, self.on_exit)

    def _create_fallback_button(self, idx, start_x, center_y, size, spacing, text, command, tag_name):
        """Создает текстовую кнопку, если изображение не загрузилось."""
        cx = start_x + idx * (size + spacing)
        x0 = cx - size // 2
        y0 = center_y - size // 2
        x1 = cx + size // 2
        y1 = center_y + size // 2

        tag = tag_name

        # Текст внутри кнопки (прямо на фоне логотипа)
        if "new" in tag_name:
            btn_text = "Н"
        else:
            btn_text = "П"
            
        text_id = self.canvas.create_text(
            cx,
            center_y,
            text=btn_text,
            font=("Segoe UI", 24, "bold"),
            fill="#e5e7eb",
            tags=(tag, "button", "button_text"),
        )
        self.button_items.append(text_id)

        # Невидимая область для кликов
        click_id = self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline="",
            fill="",
            tags=(tag, "button", "click_area")
        )
        self.button_items.append(click_id)

        # Обработчики событий
        self._bind_fallback_button_events(tag, text_id, command)

    def _bind_button_events(self, tag, img_id, command):
        """Привязывает события к кнопке-изображению."""
        def on_enter(event):
            self.canvas.configure(cursor="hand2")

        def on_leave(event):
            self.canvas.configure(cursor="")

        def on_click(event):
            command()

        self.canvas.tag_bind(tag, "<Enter>", on_enter)
        self.canvas.tag_bind(tag, "<Leave>", on_leave)
        self.canvas.tag_bind(tag, "<Button-1>", on_click)

    def _bind_fallback_button_events(self, tag, text_id, command):
        """Привязывает события к текстовой кнопке (fallback)."""
        def on_enter(event):
            # Подсветка текста при наведении
            self.canvas.itemconfig(text_id, fill="#a5f3fc")
            self.canvas.configure(cursor="hand2")

        def on_leave(event):
            # Возвращаем обычный цвет
            self.canvas.itemconfig(text_id, fill="#e5e7eb")
            self.canvas.configure(cursor="")

        def on_click(event):
            command()

        self.canvas.tag_bind(tag, "<Enter>", on_enter)
        self.canvas.tag_bind(tag, "<Leave>", on_leave)
        self.canvas.tag_bind(tag, "<Button-1>", on_click)

    def _bind_icon_button_events(self, tag, command):
        """Привязывает события к иконке."""
        def on_enter(event):
            self.canvas.configure(cursor="hand2")

        def on_leave(event):
            self.canvas.configure(cursor="")

        def on_click(event):
            command()

        self.canvas.tag_bind(tag, "<Enter>", on_enter)
        self.canvas.tag_bind(tag, "<Leave>", on_leave)
        self.canvas.tag_bind(tag, "<Button-1>", on_click)

    # ==========================
    #   ИКОНКИ И ИЗОБРАЖЕНИЯ
    # ==========================

    def _load_logo_image(self):
        """
        Загружает логотип и масштабирует его до 500x500.
        """
        if not os.path.exists(LOGO_IMG_PATH):
            print(f"Логотип не найдено: {LOGO_IMG_PATH}")
            return None

        try:
            from PIL import Image, ImageTk
        except ImportError:
            print("PIL (Pillow) не установлен")
            return None

        try:
            img = Image.open(LOGO_IMG_PATH)
            
            # Проверяем, есть ли альфа-канал
            if img.mode == 'RGBA':
                # Создаем новое изображение с альфа-каналом
                new_img = Image.new('RGBA', (500, 500), (0, 0, 0, 0))
                
                # Масштабируем оригинальное изображение с сохранением пропорций
                img.thumbnail((500, 500), Image.LANCZOS)
                
                # Вставляем логотип по центру
                img_width, img_height = img.size
                x_offset = (500 - img_width) // 2
                y_offset = (500 - img_height) // 2
                new_img.paste(img, (x_offset, y_offset), img)
            else:
                # Для изображений без альфа-канала
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Масштабируем до 500x500 с сохранением пропорций
                img.thumbnail((500, 500), Image.LANCZOS)
                
                # Создаем новое изображение 500x500 с прозрачным фоном
                new_img = Image.new('RGBA', (500, 500), (0, 0, 0, 0))
                
                # Вставляем логотип по центру
                img_width, img_height = img.size
                x_offset = (500 - img_width) // 2
                y_offset = (500 - img_height) // 2
                # Конвертируем в RGBA для вставки
                rgb_img = img.convert('RGBA')
                new_img.paste(rgb_img, (x_offset, y_offset))
            
            # Создаем PhotoImage
            self._logo_photo = ImageTk.PhotoImage(new_img)
            return self._logo_photo
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
            return None

    def _get_new_exp_image(self):
        """Загружает изображение для кнопки нового эксперимента."""
        if self._new_exp_image is not None:
            return self._new_exp_image
            
        if not os.path.exists(NEW_EXP_IMG_PATH):
            print(f"Изображение кнопки не найдено: {NEW_EXP_IMG_PATH}")
            return None
            
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None
            
        try:
            img = Image.open(NEW_EXP_IMG_PATH)
            # Проверяем альфа-канал
            if img.mode == 'RGBA':
                # Сохраняем альфа-канал
                img = img.resize((100, 100), Image.LANCZOS)
            else:
                # Конвертируем в RGBA для прозрачности
                img = img.convert('RGBA')
                img = img.resize((100, 100), Image.LANCZOS)
                
            self._new_exp_image = ImageTk.PhotoImage(img)
            return self._new_exp_image
        except Exception as e:
            print(f"Ошибка загрузки изображения кнопки: {e}")
            return None

    def _get_view_exp_image(self):
        """Загружает изображение для кнопки просмотра экспериментов."""
        if self._view_exp_image is not None:
            return self._view_exp_image
            
        if not os.path.exists(VIEW_EXP_IMG_PATH):
            print(f"Изображение кнопки не найдено: {VIEW_EXP_IMG_PATH}")
            return None
            
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return None
            
        try:
            img = Image.open(VIEW_EXP_IMG_PATH)
            # Проверяем альфа-канал
            if img.mode == 'RGBA':
                # Сохраняем альфа-канал
                img = img.resize((100, 100), Image.LANCZOS)
            else:
                # Конвертируем в RGBA для прозрачности
                img = img.convert('RGBA')
                img = img.resize((100, 100), Image.LANCZOS)
                
            self._view_exp_image = ImageTk.PhotoImage(img)
            return self._view_exp_image
        except Exception as e:
            print(f"Ошибка загрузки изображения кнопки: {e}")
            return None

    def _get_exit_icon(self):
        """Иконка exit.png для кнопки выхода."""
        if self._exit_icon is not None:
            return self._exit_icon
            
        if not os.path.exists(EXIT_IMG_PATH):
            return None
            
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None
            
        try:
            img = Image.open(EXIT_IMG_PATH)
            # Проверяем альфа-канал
            if img.mode == 'RGBA':
                img = img.resize((20, 20), Image.LANCZOS)
            else:
                img = img.convert('RGBA')
                img = img.resize((20, 20), Image.LANCZOS)
            self._exit_icon = ImageTk.PhotoImage(img)
            return self._exit_icon
        except Exception:
            return None

    def _get_about_icon(self):
        """Иконка about.png для кнопки 'О программе'."""
        if self._about_icon is not None:
            return self._about_icon
            
        if not os.path.exists(ABOUT_IMG_PATH):
            return None
            
        try:
            from PIL import Image, ImageTk
        except Exception:
            return None
            
        try:
            img = Image.open(ABOUT_IMG_PATH)
            # Проверяем альфа-канал
            if img.mode == 'RGBA':
                img = img.resize((20, 20), Image.LANCZOS)
            else:
                img = img.convert('RGBA')
                img = img.resize((20, 20), Image.LANCZOS)
            self._about_icon = ImageTk.PhotoImage(img)
            return self._about_icon
        except Exception:
            return None

    # ==========================
    #   ВСПОМОГАТЕЛЬНОЕ РИСОВАНИЕ
    # ==========================

    def _create_rounded_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        radius: int = 25,
        **kwargs,
    ) -> int:
        """Создаёт скруглённый прямоугольник на Canvas."""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    # ==========================
    #   ЛОГИКА КНОПОК МЕНЮ
    # ==========================

    def _on_new_experiment(self):
        """Обработчик нажатия кнопки 'Новый эксперимент'."""
        # Закрываем главное меню
        self.destroy()
        
        # Открываем рабочее пространство
        try:
            # Импортируем модуль рабочего пространства
            from work_space.workspace_app import WorkspaceApp
                
            # Создаем и запускаем рабочее пространство
            workspace = WorkspaceApp()
            workspace.root.mainloop()
                
        except ImportError as e:
            # Если модуль не найден, показываем сообщение
            messagebox.showerror(
                "Ошибка",
                f"Модуль рабочего пространства не найден.\n\n"
                f"Создайте папку 'work_space' с файлом workspace_app.py\n\n"
                f"Ошибка: {str(e)}"
            )
            sys.exit(1)
                
        except Exception as e:
            messagebox.showerror(
                "Ошибка",
                f"Не удалось открыть рабочее пространство:\n{str(e)}"
            )
            sys.exit(1)

    def _on_view_experiments(self):
        """Обработчик нажатия кнопки 'Просмотр экспериментов'."""
        self.show_feature_not_available()

    def show_feature_not_available(self) -> None:
        """Заглушка для кнопки просмотра экспериментов."""
        messagebox.showinfo(
            "Функция в разработке",
            "Данная функциональность находится в стадии разработки.\n"
            "Кнопка 'Просмотр экспериментов' временно не активна.\n\n"
            "Вы можете использовать:\n"
            "• Кнопку 'Новый эксперимент' для создания нового эксперимента\n"
            "• Кнопку 'О программе' для просмотра информации\n"
            "• Кнопку 'Выход' для закрытия приложения",
        )

    # ==========================
    #   ОБЩИЕ ДЕЙСТВИЯ
    # ==========================

    def on_exit(self) -> None:
        if messagebox.askyesno("Выход", "Вы действительно хотите выйти из программы?"):
            self.destroy()

    def on_about(self) -> None:
        messagebox.showinfo(
            "О программе",
            f"{APP_TITLE}\n{APP_VERSION}\n\n"
            "Интерактивный био-симулятор развития клеточных культур.\n"
            "Автор: Тынкасов Николай Павлович, 2025 год.\n\n"
            "Программа предназначена для образовательных целей.\n\n"
            "Функции:\n"
            "• Создание новых экспериментов\n"
            "• Рабочее пространство для симуляций\n"
            "• Анализ и визуализация данных\n"
            "• Экспорт результатов\n\n"
            "Новые возможности:\n"
            "✓ Рабочее пространство доступно через кнопку 'Новый эксперимент'",
        )


def main() -> None:
    app = MainMenuApp()
    app.mainloop()


if __name__ == "__main__":
    main()