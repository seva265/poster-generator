"""Streamlit frontend for PD Generator."""

import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import streamlit as st
from PIL import Image

from config import Config
from poster import PosterGenerator


@dataclass
class ProjectData:
    """Data for a single project."""
    project_id: str
    project_name: str
    problem: str
    solution: str
    product: str
    team: str
    image_path: Optional[Path] = None

    def validate(self) -> list[str]:
        """Validate project data, return list of errors."""
        errors = []
        if not self.project_id:
            errors.append("Введите ID проекта")
        if not self.project_name:
            errors.append("Введите название проекта")
        if not self.problem:
            errors.append("Опишите проблему")
        if not self.solution:
            errors.append("Опишите решение")
        if not self.product:
            errors.append("Опишите продукт")
        if not self.team:
            errors.append("Укажите команду")
        return errors


def main():
    st.set_page_config(
        page_title="Генератор постеров проектов",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 Генератор постеров проектов")
    st.markdown("Заполните информацию о проекте и загрузите изображение для генерации PDF-постера")

    # Sidebar with configuration info
    with st.sidebar:
        st.header("⚙️ Настройки")
        st.info("Конфигурация загружается из `config.yaml`")
        
        config_path = Path("config.yaml")
        if config_path.exists():
            st.success("✅ config.yaml найден")
        else:
            st.warning("⚠️ config.yaml не найден, используются настройки по умолчанию")
        
        st.markdown("---")
        st.markdown("### Логотипы")
        st.markdown("Разместите файлы `logo1.png` и `logo2.jpg` в папке `images/`")

    # Main form
    with st.form("project_form"):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📝 Информация о проекте")
            
            project_id = st.text_input("ID проекта *", placeholder="например: 101")
            project_name = st.text_input("Название проекта *", placeholder="например: Умная система полива")
            
            st.markdown("#### Детали проекта")
            problem = st.text_area(
                "Проблема *", 
                placeholder="Опишите проблему, которую решает проект",
                height=100
            )
            solution = st.text_area(
                "Решение *", 
                placeholder="Опишите ваше решение",
                height=100
            )
            product = st.text_area(
                "Продукт *", 
                placeholder="Опишите конечный продукт",
                height=100
            )
            team = st.text_area(
                "Команда *", 
                placeholder="ФИО участников команды (каждое с новой строки)",
                height=80
            )
        
        with col2:
            st.subheader("🖼️ Изображение проекта")
            
            uploaded_file = st.file_uploader(
                "Загрузите изображение",
                type=["jpg", "jpeg", "png", "webp"],
                help="Рекомендуемый размер: не менее 1800×1300 пикселей"
            )
            
            if uploaded_file:
                st.image(uploaded_file, caption="Предпросмотр", use_container_width=True)

        st.markdown("---")
        
        submitted = st.form_submit_button("🚀 Сгенерировать постер", type="primary", use_container_width=True)

    # Process submission
    if submitted:
        project = ProjectData(
            project_id=project_id.strip(),
            project_name=project_name.strip(),
            problem=problem.strip(),
            solution=solution.strip(),
            product=product.strip(),
            team=team.strip()
        )
        
        errors = project.validate()
        
        if errors:
            st.error("❌ Пожалуйста, заполните все обязательные поля:")
            for error in errors:
                st.write(f"- {error}")
        else:
            # Save uploaded image temporarily
            temp_image_path = None
            if uploaded_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    temp_image_path = Path(tmp.name)
            
            try:
                # Load configuration
                config = Config.load(Path("config.yaml"))
                
                # Setup folders
                images_folder = Path("images")
                images_folder.mkdir(exist_ok=True)
                output_folder = Path("output")
                output_folder.mkdir(exist_ok=True)
                
                # Generate poster
                generator = PosterGenerator(config, images_folder, output_folder)
                output_path, warnings = generator.generate_poster(project, temp_image_path)
                
                # Success!
                st.success(f"✅ Постер успешно сгенерирован!")
                st.info(f"📁 Файл сохранен: `{output_path}`")
                
                # Show preview if possible (first page as image would need conversion)
                # For now, provide download link
                with open(output_path, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Скачать PDF",
                        data=pdf_file.read(),
                        file_name=output_path.name,
                        mime="application/pdf"
                    )
                
                # Show warnings if any
                if warnings:
                    st.warning("⚠️ Предупреждения при генерации:")
                    for warning in warnings:
                        st.write(f"- {warning}")
                
            except Exception as e:
                st.error(f"❌ Ошибка при генерации: {e}")
            finally:
                # Cleanup temp file
                if temp_image_path and temp_image_path.exists():
                    temp_image_path.unlink()

    # Footer
    st.markdown("---")
    st.markdown(
        """
        **Как использовать:**
        1. Заполните все поля формы
        2. Загрузите изображение проекта (опционально, но рекомендуется)
        3. Нажмите "Сгенерировать постер"
        4. Скачайте готовый PDF-файл
        
        **Требования к изображению:**
        - Форматы: JPG, PNG, WebP
        - Рекомендуемый размер: от 1800×1300 пикселей
        - Соотношение сторон будет автоматически подстроено под формат постера
        """
    )


if __name__ == "__main__":
    main()
