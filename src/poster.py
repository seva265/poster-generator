"""Poster generation with ReportLab for PD Generator."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from reportlab.lib.colors import black, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .config import Config
from .text_utils import fit_text_to_box, format_output_filename

logger = logging.getLogger(__name__)

DEJAVU_FONTS = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
}

LOCAL_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

SYSTEM_CYRILLIC_FONTS = {
    "Arial": "arial.ttf",
    "Arial-Bold": "arialbd.ttf",
    "Calibri": "calibri.ttf",
    "Calibri-Bold": "calibrib.ttf",
    "TimesNewRoman": "times.ttf",
    "TimesNewRoman-Bold": "timesbd.ttf",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

FONT_SEARCH_PATHS = [
    LOCAL_FONTS_DIR,
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]


def _find_font_file(font_filename: str) -> Optional[Path]:
    """Search for a font file in standard locations."""
    target = font_filename.lower()

    # First, check local fonts directory explicitly
    local_font_path = LOCAL_FONTS_DIR / font_filename
    if local_font_path.exists() and local_font_path.is_file():
        return local_font_path
    
    # Also check case-insensitive in local directory
    if LOCAL_FONTS_DIR.exists():
        for font_path in LOCAL_FONTS_DIR.iterdir():
            if font_path.is_file() and font_path.name.lower() == target:
                return font_path

    for search_path in FONT_SEARCH_PATHS:
        if not search_path.exists():
            continue

        # First try exact match
        for font_path in search_path.rglob(font_filename):
            if font_path.is_file():
                return font_path

        # Then try case-insensitive match
        for font_path in search_path.rglob("*.ttf"):
            if font_path.is_file() and font_path.name.lower() == target:
                return font_path

    return None


def _register_fonts() -> bool:
    """Register fonts with ReportLab."""
    registered_any = False
    all_fonts = {**DEJAVU_FONTS, **SYSTEM_CYRILLIC_FONTS}

    for font_name, font_filename in all_fonts.items():
        try:
            pdfmetrics.getFont(font_name)
            registered_any = True
            continue
        except KeyError:
            pass

        font_path = _find_font_file(font_filename)
        if not font_path:
            continue

        try:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            logger.debug("Registered font: %s from %s", font_name, font_path)
            registered_any = True
        except Exception as e:
            logger.warning("Failed to register font %s: %s", font_name, e)

    return registered_any


def _ensure_fonts_available(config: Config) -> Tuple[str, str, str]:
    """Ensure required fonts are available."""
    _register_fonts()

    def _has_font(name: str) -> bool:
        try:
            pdfmetrics.getFont(name)
            return True
        except KeyError:
            return False

    def _pick(preferred: List[str]) -> str:
        for name in preferred:
            if _has_font(name):
                return name
        return "Helvetica"

    title_candidates = []
    heading_candidates = []
    body_candidates = []

    if config.fonts.title_font:
        title_candidates.append(config.fonts.title_font)
    if config.fonts.heading_font:
        heading_candidates.append(config.fonts.heading_font)
    if config.fonts.body_font:
        body_candidates.append(config.fonts.body_font)

    title_candidates += ["DejaVuSans-Bold", "Arial-Bold", "Calibri-Bold"]
    heading_candidates += ["DejaVuSans-Bold", "Arial-Bold", "Calibri-Bold"]
    body_candidates += ["DejaVuSans", "Arial", "Calibri"]
    title_candidates += ["Helvetica-Bold"]
    heading_candidates += ["Helvetica-Bold"]
    body_candidates += ["Helvetica"]

    return _pick(title_candidates), _pick(heading_candidates), _pick(body_candidates)


class PosterGenerator:
    """Generator for project posters."""

    def __init__(self, config: Config, images_folder: Path, output_folder: Path):
        self.config = config
        self.images_folder = images_folder
        self.output_folder = output_folder
        self.warnings: List[str] = []

        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.title_font, self.heading_font, self.body_font = _ensure_fonts_available(config)

    def _add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(message)

    def _draw_image(
        self,
        c: canvas.Canvas,
        image_path: Path,
        x: float,
        y: float,
        width: float,
        height: float,
        fit_mode: str = "cover",
    ):
        """Draw an image on the canvas."""
        try:
            img = Image.open(image_path)
            img_width, img_height = img.size
            img_aspect = img_width / img_height
            target_aspect = width / height

            if fit_mode == "cover":
                if img_aspect > target_aspect:
                    scale = height / img_height
                    scaled_width = img_width * scale
                    scaled_height = height
                    draw_x = x - (scaled_width - width) / 2
                    draw_y = y
                else:
                    scale = width / img_width
                    scaled_width = width
                    scaled_height = img_height * scale
                    draw_x = x
                    draw_y = y - (scaled_height - height) / 2

                c.saveState()
                path = c.beginPath()
                path.rect(x, y, width, height)
                path.close()
                c.clipPath(path, stroke=0, fill=0)
                c.drawImage(str(image_path), draw_x, draw_y, scaled_width, scaled_height,
                           preserveAspectRatio=False, mask='auto')
                c.restoreState()
            else:
                if img_aspect > target_aspect:
                    scaled_width = width
                    scaled_height = width / img_aspect
                else:
                    scaled_height = height
                    scaled_width = height * img_aspect

                draw_x = x + (width - scaled_width) / 2
                draw_y = y + (height - scaled_height) / 2
                c.drawImage(str(image_path), draw_x, draw_y, scaled_width, scaled_height,
                           preserveAspectRatio=True, mask='auto')

        except Exception as e:
            logger.error(f"Failed to draw image {image_path}: {e}")
            self._add_warning(f"Failed to draw image {image_path}: {e}")
            c.setStrokeColor(black)
            c.setFillColor(white)
            c.rect(x, y, width, height, fill=1, stroke=1)

    def _find_image_by_stem(self, stem: str) -> Optional[Path]:
        """Find an image by filename stem."""
        stem_l = stem.lower()

        for ext in IMAGE_EXTS:
            p = self.images_folder / f"{stem}{ext}"
            if p.exists() and p.is_file():
                return p

        try:
            for p in self.images_folder.iterdir():
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.stem.lower() == stem_l:
                    return p
        except Exception:
            pass

        return None

    def _desired_height_fit_width(self, image_path: Path, target_width: float) -> float:
        """Height needed to fit image to target_width keeping aspect ratio."""
        img = Image.open(image_path)
        w, h = img.size
        if w <= 0:
            return 0.0
        return target_width * (h / w)

    def _draw_university_logo_from_images(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        max_width: float,
        max_height: float,
    ) -> bool:
        """Draw two-component logo: logo1 at bottom, logo2 stacked above."""
        spacing = self.config.logos.spacing_mm * mm

        logo1_path = self._find_image_by_stem("logo1")
        logo2_path = self._find_image_by_stem("logo2")

        if logo1_path and logo2_path:
            h1 = self._desired_height_fit_width(logo1_path, max_width)
            h2 = self._desired_height_fit_width(logo2_path, max_width)

            if h1 <= 0:
                h1 = (max_height - spacing) / 2
            if h2 <= 0:
                h2 = (max_height - spacing) / 2

            total = h1 + h2 + spacing
            if total > max_height:
                scale = max(0.0, (max_height - spacing) / (h1 + h2))
                h1 *= scale
                h2 *= scale

            logo1_y = y
            logo2_y = y + h1 + spacing

            self._draw_image(c=c, image_path=logo1_path, x=x, y=logo1_y, width=max_width, height=h1, fit_mode="contain")
            self._draw_image(c=c, image_path=logo2_path, x=x, y=logo2_y, width=max_width, height=h2, fit_mode="contain")
            return True

        logo_path = self._find_image_by_stem("logo")
        if not logo_path:
            logger.debug("University logo not found in images folder.")
            return False

        self._draw_image(c=c, image_path=logo_path, x=x, y=y, width=max_width, height=max_height, fit_mode="contain")
        return True

    def _draw_text_block(
        self,
        c: canvas.Canvas,
        text: str,
        x: float,
        y: float,
        max_width: float,
        max_height: float,
        font_name: str,
        font_size: float,
        heading: Optional[str] = None,
    ) -> Tuple[float, bool]:
        """Draw a text block with optional heading."""
        initial_y = y

        if heading:
            c.setFont(self.heading_font, self.config.fonts.heading_size)
            c.drawString(x, y - self.config.fonts.heading_size, heading)
            y -= self.config.fonts.heading_size * 1.6
            max_height -= self.config.fonts.heading_size * 1.6

        lines, final_size, truncated = fit_text_to_box(
            text,
            max_width=max_width,
            max_height=max_height,
            font_name=font_name,
            initial_font_size=font_size,
            min_font_size=self.config.fonts.min_font_size,
            line_spacing=self.config.fonts.line_spacing,
        )

        c.setFont(font_name, final_size)
        line_h = final_size * self.config.fonts.line_spacing

        cur_y = y - final_size
        for line in lines:
            c.drawString(x, cur_y, line)
            cur_y -= line_h

        used_height = initial_y - cur_y
        return used_height, truncated

    def generate_poster(self, project, image_path: Optional[Path]) -> Tuple[Path, List[str]]:
        """Generate a poster for a project."""
        self.warnings = []

        page_width = self.config.page.width_mm * mm
        page_height = self.config.page.height_mm * mm

        image_height = self.config.layout.image_height_mm * mm
        content_height = page_height - image_height

        padding_left = self.config.layout.content_padding_left_mm * mm
        padding_right = self.config.layout.content_padding_right_mm * mm
        padding_top = self.config.layout.content_padding_top_mm * mm
        padding_bottom = self.config.layout.content_padding_bottom_mm * mm

        text_column_width = self.config.layout.text_column_width_mm * mm
        logo_area_width = page_width - padding_left - padding_right - text_column_width - 20 * mm

        filename = format_output_filename(
            self.config.output.naming_pattern,
            project.project_id,
            project.project_name,
        )
        output_path = self.output_folder / f"{filename}.pdf"

        c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

        image_y = page_height - image_height
        if image_path and image_path.exists():
            self._draw_image(
                c, image_path, 0, image_y, page_width, image_height,
                self.config.layout.image_fit_mode,
            )
        else:
            c.setFillColor(white)
            c.setStrokeColor(black)
            c.rect(0, image_y, page_width, image_height, fill=1, stroke=1)
            c.setFillColor(black)
            c.setFont(self.body_font, 24)
            c.drawCentredString(page_width / 2, image_y + image_height / 2, "No image available")

        content_top_y = image_y - padding_top
        left_x = padding_left
        left_width = logo_area_width

        label = "Проект"
        label_size = self.config.fonts.heading_size
        label_gap = 4 * mm

        c.setFillColor(black)
        c.setFont(self.heading_font, label_size)
        c.drawString(left_x, content_top_y - label_size, label)

        title_box_top = content_top_y - (label_size * 1.6) - label_gap
        title_box_height = 65 * mm

        name_lines, name_size, name_truncated = fit_text_to_box(
            project.project_name,
            max_width=left_width,
            max_height=title_box_height,
            font_name=self.title_font,
            initial_font_size=self.config.fonts.title_size,
            min_font_size=self.config.fonts.min_font_size,
            line_spacing=self.config.fonts.line_spacing,
        )

        c.setFont(self.title_font, name_size)
        line_h = name_size * self.config.fonts.line_spacing

        cur_y = title_box_top - name_size
        for line in name_lines[:3]:
            c.drawString(left_x, cur_y, line)
            cur_y -= line_h

        if name_truncated:
            self._add_warning(f"Project name truncated for project {project.project_id}")

        text_start_y = content_top_y
        text_area_height = text_start_y - padding_bottom
        text_x = page_width - padding_right - text_column_width

        section_height = (text_area_height - 60 * mm) / 3

        current_y = text_start_y
        sections = [
            ("Проблема", project.problem),
            ("Решение", project.solution),
            ("Продукт", project.product),
        ]

        for heading, content in sections:
            height_used, truncated = self._draw_text_block(
                c, content, text_x, current_y, text_column_width, section_height,
                self.body_font, self.config.fonts.body_size, heading=heading,
            )
            if truncated:
                self._add_warning(f"Text truncated in {heading} section for project {project.project_id}")
            current_y -= height_used + 15 * mm

        team_block_height = 70 * mm
        team_top = padding_bottom + team_block_height

        c.setFont(self.heading_font, self.config.fonts.heading_size)
        c.drawString(text_x, team_top - self.config.fonts.heading_size, "Команда")

        team_text_top = team_top - (self.config.fonts.heading_size * 1.8)
        team_max_height = team_text_top - padding_bottom

        team_lines, team_size, team_truncated = fit_text_to_box(
            project.team or "",
            max_width=text_column_width,
            max_height=team_max_height,
            font_name=self.body_font,
            initial_font_size=max(self.config.fonts.body_size - 2, self.config.fonts.min_font_size),
            min_font_size=self.config.fonts.min_font_size,
            line_spacing=self.config.fonts.line_spacing,
        )

        c.setFont(self.body_font, team_size)
        cur_y = team_text_top - team_size
        line_h = team_size * self.config.fonts.line_spacing
        for line in team_lines:
            c.drawString(text_x, cur_y, line)
            cur_y -= line_h

        if team_truncated:
            self._add_warning(f"Team text truncated for project {project.project_id}")

        logo_x = self.config.logos.margin_left_mm * mm
        logo_y = self.config.logos.margin_bottom_mm * mm
        logo_height = self.config.logos.height_mm * mm
        logo_width = logo_area_width

        drawn = self._draw_university_logo_from_images(c, logo_x, logo_y, logo_width, logo_height)

        c.save()

        return output_path, self.warnings
