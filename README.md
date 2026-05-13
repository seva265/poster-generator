# PD Generator — Генератор постеров проектов

Веб-приложение на Streamlit для создания A1 постеров (594×841 мм) для университетских проектов.

## Возможности

- **Генерация PDF**: Создание постеров формата A1 с поддержкой кириллицы
- **Простой интерфейс**: Заполнение формы и загрузка изображения через браузер
- **Гибкая настройка**: Конфигурация шрифтов, размеров и отступов в YAML
- **Автоматическое форматирование**: Текст автоматически переносится и масштабируется

## Установка

### Вариант 1: Использование Poetry (Рекомендуется)

Если у вас установлен Poetry, это рекомендуемый способ установки:

```bash
# Установка зависимостей через Poetry
poetry install

# Запуск приложения
poetry run streamlit run app.py
```

### Вариант 2: Использование venv и pip

Если у вас не установлен Poetry или вы предпочитаете использовать pip:

#### На Linux/macOS:
```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
streamlit run app.py
```

#### На Windows:
```bash
# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск приложения
streamlit run app.py
```

## Конфигурация

Отредактируйте `config.yaml` для настройки:

```yaml
page:
  width_mm: 594
  height_mm: 841

layout:
  image_height_mm: 434
  text_column_width_mm: 225

fonts:
  title_font: DejaVuSans-Bold
  title_size: 48
  body_font: DejaVuSans
  body_size: 18

logos:
  height_mm: 80
  spacing_mm: 5
  margin_left_mm: -50
  margin_bottom_mm: 10
```

## Логотипы

Для добавления логотипов университета разместите файлы в папке `images/`:
- `logo1.png` — нижний логотип
- `logo2.png` — верхний логотип (опционально)
- или один `logo.png`

## Требования

- Python 3.10+
- Шрифты с поддержкой кириллицы (DejaVu, Arial, Calibri)

