"""Poster generation with ReportLab for PD Generator."""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from reportlab.lib.colors import black, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from config import Config
from text_utils import fit_text_to_box, format_output_filename

logger = logging.getLogger(__name__)

# DejaVu font files (support Cyrillic)
DEJAVU_FONTS = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
    "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf",
    "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
    "DejaVuSerif": "DejaVuSerif.ttf",
    "DejaVuSerif-Bold": "DejaVuSerif-Bold.ttf",
}

# Local fonts folder (recommended to bundle fonts with the project)
LOCAL_FONTS_DIR = Path(__file__).resolve().parent / "fonts"

# ReportLab base14 fonts (do NOT support Cyrillic reliably)
BASE14_FONTS = {
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Symbol", "ZapfDingbats",
}

# Common system fonts on Windows that support Cyrillic
SYSTEM_CYRILLIC_FONTS = {
    "Arial": "arial.ttf",
    "Arial-Bold": "arialbd.ttf",
    "Arial-Italic": "ariali.ttf",
    "Arial-BoldItalic": "arialbi.ttf",
    "Calibri": "calibri.ttf",
    "Calibri-Bold": "calibrib.ttf",
    "TimesNewRoman": "times.ttf",
    "TimesNewRoman-Bold": "timesbd.ttf",
    "TimesNewRoman-Italic": "timesi.ttf",
    "TimesNewRoman-BoldItalic": "timesbi.ttf",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

FONT_SEARCH_PATHS = [
    # Project-local fonts (bundle here)
    LOCAL_FONTS_DIR,

    # Windows
    Path("C:/Windows/Fonts"),

    # Linux
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path(os.path.expanduser("~/.fonts")),
    Path(os.path.expanduser("~/.local/share/fonts")),

    # macOS
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path(os.path.expanduser("~/Library/Fonts")),
]


def _auto_find_university_logo(images_folder: Path) -> Optional[Path]:
    """
    Find a university logo file inside images folder (or its common subfolders).
    Put a single logo image (with university name inside it) into images/.
    Recommended filename: logo.png
    """
    search_dirs = [
        images_folder,
        images_folder / "logos",
        images_folder / "logo",
    ]

    patterns = [
        "logo.*",
        "*logo*.*",
        "*логотип*.*",
        "*polytech*.*",
        "*политех*.*",
        "*mospolytech*.*",
    ]

    found: List[Path] = []
    for d in search_dirs:
        if not d.exists() or not d.is_dir():
            continue
        for pat in patterns:
            found.extend([p for p in d.glob(pat) if p.is_file() and p.suffix.lower() in IMAGE_EXTS])

    if not found:
        return None

    # If multiple — use newest file
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0]


def _find_font_file(font_filename: str) -> Optional[Path]:
    """Search for a font file in standard locations (case-insensitive)."""
    target = font_filename.lower()

    for search_path in FONT_SEARCH_PATHS:
        if not search_path.exists():
            continue

        # Fast path (works well on Windows)
        for font_path in search_path.rglob(font_filename):
            if font_path.is_file():
                return font_path

        # Fallback: case-insensitive scan
        for font_path in search_path.rglob("*.ttf"):
            if font_path.is_file() and font_path.name.lower() == target:
                return font_path

    return None



def _register_fonts() -> bool:
    """Register fonts with ReportLab, return True if successful."""
    registered_any = False

    all_fonts = {}
    all_fonts.update(DEJAVU_FONTS)
    all_fonts.update(SYSTEM_CYRILLIC_FONTS)

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
            logger.warning("Failed to register font %s (%s): %s", font_name, font_path, e)

    return registered_any



def _ensure_fonts_available(config: Config) -> Tuple[str, str, str]:
    """
    Ensure required fonts are available, return actual font names to use.
    Prefer Unicode TTF fonts that support Cyrillic.
    """
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
        return "Helvetica"  # last resort

    # If config fonts are base14, prefer Unicode fonts instead (Cyrillic-safe)
    cfg_title = config.fonts.title_font
    cfg_heading = config.fonts.heading_font
    cfg_body = config.fonts.body_font

    title_candidates = []
    heading_candidates = []
    body_candidates = []

    if cfg_title and cfg_title not in BASE14_FONTS:
        title_candidates.append(cfg_title)
    if cfg_heading and cfg_heading not in BASE14_FONTS:
        heading_candidates.append(cfg_heading)
    if cfg_body and cfg_body not in BASE14_FONTS:
        body_candidates.append(cfg_body)

    # Strong defaults for Cyrillic
    title_candidates += ["DejaVuSans-Bold", "Arial-Bold", "Calibri-Bold", "TimesNewRoman-Bold"]
    heading_candidates += ["DejaVuSans-Bold", "Arial-Bold", "Calibri-Bold", "TimesNewRoman-Bold"]
    body_candidates += ["DejaVuSans", "Arial", "Calibri", "TimesNewRoman"]

    # Absolute fallback (will show squares on Cyrillic, but better than crash)
    title_candidates += ["Helvetica-Bold"]
    heading_candidates += ["Helvetica-Bold"]
    body_candidates += ["Helvetica"]

    title_font = _pick(title_candidates)
    heading_font = _pick(heading_candidates)
    body_font = _pick(body_candidates)

    logger.info("Fonts selected: title=%s, heading=%s, body=%s", title_font, heading_font, body_font)
    return title_font, heading_font, body_font



class PosterGenerator:
    """Generator for project posters."""

    def __init__(self, config: Config, images_folder: Path, output_folder: Path):
        """
        Initialize poster generator.

        Args:
            config: Configuration object
            images_folder: Folder containing project images
            output_folder: Folder for output PDFs
        """
        self.config = config
        self.images_folder = images_folder
        self.output_folder = output_folder
        self.warnings: List[str] = []

        # Ensure output folder exists
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # Get actual fonts to use
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
        """
        Draw an image on the canvas with specified fit mode.

        Args:
            c: ReportLab canvas
            image_path: Path to image file
            x: X position (bottom-left) in points
            y: Y position (bottom-left) in points
            width: Target width in points
            height: Target height in points
            fit_mode: "cover" (fill, may crop) or "contain" (fit within)
        """
        try:
            img = Image.open(image_path)
            img_width, img_height = img.size
            img_aspect = img_width / img_height
            target_aspect = width / height

            if fit_mode == "cover":
                # Scale to fill the entire area, cropping if needed
                if img_aspect > target_aspect:
                    # Image is wider - scale by height
                    scale = height / img_height
                    scaled_width = img_width * scale
                    scaled_height = height
                    # Center horizontally (will be cropped)
                    draw_x = x - (scaled_width - width) / 2
                    draw_y = y
                else:
                    # Image is taller - scale by width
                    scale = width / img_width
                    scaled_width = width
                    scaled_height = img_height * scale
                    # Center vertically (will be cropped)
                    draw_x = x
                    draw_y = y - (scaled_height - height) / 2

                # Save state, clip, draw, restore
                c.saveState()
                path = c.beginPath()
                path.rect(x, y, width, height)
                path.close()
                c.clipPath(path, stroke=0, fill=0)
                c.drawImage(str(image_path), draw_x, draw_y, scaled_width, scaled_height,
                           preserveAspectRatio=False, mask='auto')
                c.restoreState()
            else:
                # Contain mode - fit within bounds
                if img_aspect > target_aspect:
                    # Image is wider - scale by width
                    scaled_width = width
                    scaled_height = width / img_aspect
                else:
                    # Image is taller - scale by height
                    scaled_height = height
                    scaled_width = height * img_aspect

                # Center the image
                draw_x = x + (width - scaled_width) / 2
                draw_y = y + (height - scaled_height) / 2

                c.drawImage(str(image_path), draw_x, draw_y, scaled_width, scaled_height,
                           preserveAspectRatio=True, mask='auto')

        except Exception as e:
            logger.error(f"Failed to draw image {image_path}: {e}")
            self._add_warning(f"Failed to draw image {image_path}: {e}")
            # Draw placeholder rectangle
            c.setStrokeColor(black)
            c.setFillColor(white)
            c.rect(x, y, width, height, fill=1, stroke=1)

    def _draw_logos(self, c: canvas.Canvas, x: float, y: float, max_width: float, max_height: float):
        """Draw logos in the specified area."""
        if not self.config.logos.paths:
            return

        logo_height = self.config.logos.height_mm * mm
        spacing = self.config.logos.spacing_mm * mm
        current_x = x

        for logo_path_str in self.config.logos.paths:
            logo_path = Path(logo_path_str)
            if not logo_path.exists():
                logger.debug(f"Logo not found: {logo_path}")
                continue

            try:
                img = Image.open(logo_path)
                img_width, img_height = img.size
                aspect = img_width / img_height
                logo_width = logo_height * aspect

                if current_x + logo_width > x + max_width:
                    break  # No more space

                c.drawImage(
                    str(logo_path),
                    current_x,
                    y,
                    logo_width,
                    logo_height,
                    preserveAspectRatio=True,
                )
                current_x += logo_width + spacing

            except Exception as e:
                logger.debug(f"Failed to draw logo {logo_path}: {e}")
    
    def _find_image_by_stem(self, stem: str) -> Optional[Path]:
        """Find an image in images_folder by filename stem (case-insensitive), with any supported extension."""
        stem_l = stem.lower()

        # Fast path: exact stem + known extensions
        for ext in IMAGE_EXTS:
            p = self.images_folder / f"{stem}{ext}"
            if p.exists() and p.is_file():
                return p

        # Fallback: case-insensitive scan
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
        """
        Draw two-component logo: logo1.* at bottom, logo2.* stacked above.
        Falls back to single auto-found logo.*.
        Returns True if something was drawn.
        """
        spacing = self.config.logos.spacing_mm * mm

        # Prefer explicit two-component logo
        logo1_path = self._find_image_by_stem("logo1")
        logo2_path = self._find_image_by_stem("logo2")

        if logo1_path and logo2_path:
            # Compute “natural” heights when fitting to width, then scale to fit max_height
            h1 = self._desired_height_fit_width(logo1_path, max_width)
            h2 = self._desired_height_fit_width(logo2_path, max_width)

            # Guard rails
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

            logger.info(
                "Two-component logo: logo1=%s (y=%.1fmm, h=%.1fmm), logo2=%s (y=%.1fmm, h=%.1fmm)",
                logo1_path.name, logo1_y / mm, h1 / mm,
                logo2_path.name, logo2_y / mm, h2 / mm,
            )

            # Draw bottom then top
            self._draw_image(c=c, image_path=logo1_path, x=x, y=logo1_y, width=max_width, height=h1, fit_mode="contain")
            self._draw_image(c=c, image_path=logo2_path, x=x, y=logo2_y, width=max_width, height=h2, fit_mode="contain")
            return True

        # Fallback: single logo (auto-find, picks newest if multiple) :contentReference[oaicite:5]{index=5}
        logo_path = _auto_find_university_logo(self.images_folder)
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
        """
        Draw a text block with optional heading.

        Args:
            c: ReportLab canvas
            text: Text content
            x: X position (left) in points
            y: Y position (top) in points
            max_width: Maximum width in points
            max_height: Maximum height in points
            font_name: Font name for body text
            font_size: Font size for body text
            heading: Optional heading text

        Returns:
            Tuple of (height used, was_truncated)
        """
        line_spacing = self.config.fonts.line_spacing
        min_font_size = self.config.fonts.min_font_size
        heading_font = self.heading_font
        heading_size = self.config.fonts.heading_size

        current_y = y
        total_height = 0
        was_truncated = False

        # Draw heading if provided
        if heading:
            c.setFont(heading_font, heading_size)
            c.setFillColor(black)
            c.drawString(x, current_y - heading_size, heading)
            heading_height = heading_size * line_spacing * 1.5
            current_y -= heading_height
            total_height += heading_height
            max_height -= heading_height

        # Fit and draw body text
        lines, final_size, truncated = fit_text_to_box(
            text,
            max_width,
            max_height,
            font_name,
            font_size,
            min_font_size,
            line_spacing,
        )

        was_truncated = truncated

        c.setFont(font_name, final_size)
        line_height = final_size * line_spacing

        for line in lines:
            c.drawString(x, current_y - final_size, line)
            current_y -= line_height
            total_height += line_height

        return total_height, was_truncated

    def generate_poster(self, project: ProjectData, image_path: Optional[Path]) -> Tuple[Path, List[str]]:
        """
        Generate a poster for a project.

        Args:
            project: Project data
            image_path: Path to project image (optional)

        Returns:
            Tuple of (output path, list of warnings)
        """
        self.warnings = []

        # Calculate page dimensions
        page_width = self.config.page.width_mm * mm
        page_height = self.config.page.height_mm * mm

        # Calculate layout
        image_height = self.config.layout.image_height_mm * mm
        content_height = page_height - image_height

        padding_left = self.config.layout.content_padding_left_mm * mm
        padding_right = self.config.layout.content_padding_right_mm * mm
        padding_top = self.config.layout.content_padding_top_mm * mm
        padding_bottom = self.config.layout.content_padding_bottom_mm * mm

        text_column_width = self.config.layout.text_column_width_mm * mm
        logo_area_width = page_width - padding_left - padding_right - text_column_width - 20 * mm

        # Generate output filename
        filename = format_output_filename(
            self.config.output.naming_pattern,
            project.project_id,
            project.project_name,
        )
        output_path = self.output_folder / f"{filename}.pdf"

        # Create canvas
        c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

        # Draw top image area
        image_y = page_height - image_height
        if image_path and image_path.exists():
            self._draw_image(
                c,
                image_path,
                0,
                image_y,
                page_width,
                image_height,
                self.config.layout.image_fit_mode,
            )
        else:
            # Draw placeholder
            c.setFillColor(white)
            c.setStrokeColor(black)
            c.rect(0, image_y, page_width, image_height, fill=1, stroke=1)
            c.setFillColor(black)
            c.setFont(self.body_font, 24)
            no_image_text = "No image available" if not image_path else f"Image not found: {image_path.name}"
            c.drawCentredString(page_width / 2, image_y + image_height / 2, no_image_text)

        # Draw project title (centered in content area)
        # Inner top of the bottom content area
        content_top_y = image_y - padding_top

        # Left column geometry (same as logo area width)
        left_x = padding_left
        left_width = logo_area_width  # already calculated above

        # --- Left header block: "Проект" + bold project name ---
        label = "Проект"
        label_size = self.config.fonts.heading_size
        label_gap = 4 * mm

        c.setFillColor(black)
        c.setFont(self.heading_font, label_size)
        c.drawString(left_x, content_top_y - label_size, label)

        # Project name under the label (bold, may wrap)
        title_box_top = content_top_y - (label_size * 1.6) - label_gap
        title_box_height = 65 * mm  # enough for 1–2 lines like in your photo

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
        for line in name_lines[:3]:  # hard safety limit
            c.drawString(left_x, cur_y, line)
            cur_y -= line_h

        if name_truncated:
            self._add_warning(f"Project name truncated for project {project.project_id}")

        # Calculate text areas
        text_start_y = content_top_y
        text_area_height = text_start_y - padding_bottom
        text_x = page_width - padding_right - text_column_width

        # Divide text area for three sections (problem, solution, product)
        section_height = (text_area_height - 60 * mm) / 3  # Leave some spacing

        # Draw text sections
        current_y = text_start_y
        sections = [
            ("Проблема", project.problem),
            ("Решение", project.solution),
            ("Продукт", project.product),
        ]

        for heading, content in sections:
            height_used, truncated = self._draw_text_block(
                c,
                content,
                text_x,
                current_y,
                text_column_width,
                section_height,
                self.body_font,
                self.config.fonts.body_size,
                heading=heading,
            )
            if truncated:
                self._add_warning(f"Text truncated in {heading} section for project {project.project_id}")
            current_y -= height_used + 15 * mm

        # Draw team info at the bottom of text column
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


        # Draw logos in bottom-left corner with configurable margins
        logo_x = self.config.logos.margin_left_mm * mm
        logo_y = self.config.logos.margin_bottom_mm * mm
        logo_height = self.config.logos.height_mm * mm
        logo_width = logo_area_width

        # Priority: university logo(s) from images folder; fallback to config logos
        drawn = self._draw_university_logo_from_images(c, logo_x, logo_y, logo_width, logo_height)
        if not drawn:
            self._draw_logos(c, logo_x, logo_y, logo_width, logo_height)


        # First try config-specified logos
        self._draw_logos(c, logo_x, logo_y, logo_width, logo_height)

        # Then try auto-finding university logo from images folder
        self._draw_university_logo_from_images(c, logo_x, logo_y, logo_width, logo_height)

        # Save PDF
        c.save()

        return output_path, self.warnings


def generate_all_posters(
    projects: List[ProjectData],
    config: Config,
    images_folder: Path,
    output_folder: Path,
    only_ids: Optional[List[str]] = None,
) -> Tuple[List[Tuple[str, Path]], List[Tuple[str, str]]]:
    """
    Generate posters for all projects.

    Args:
        projects: List of project data
        config: Configuration object
        images_folder: Folder containing project images
        output_folder: Folder for output PDFs
        only_ids: Optional list of project IDs to generate (if None, generate all)

    Returns:
        Tuple of (success list, failure list)
        Success list: [(project_id, output_path), ...]
        Failure list: [(project_id, error_message), ...]
    """
    from excel_reader import find_project_image

    generator = PosterGenerator(config, images_folder, output_folder)

    successes = []
    failures = []

    for project in projects:
        # Filter by ID if specified
        if only_ids is not None and project.project_id not in only_ids:
            continue

        try:
            # Validate project data
            errors = project.validate()
            if errors:
                failures.append((project.project_id, f"Validation errors: {'; '.join(errors)}"))
                continue

            # Find image
            image_path = find_project_image(project, images_folder)
            if image_path is None:
                logger.warning(f"No image found for project {project.project_id}")

            # Generate poster
            output_path, warnings = generator.generate_poster(project, image_path)

            if warnings:
                for warning in warnings:
                    logger.warning(f"Project {project.project_id}: {warning}")

            successes.append((project.project_id, output_path))
            logger.info(f"Generated poster: {output_path}")

        except Exception as e:
            error_msg = f"Failed to generate poster: {e}"
            failures.append((project.project_id, error_msg))
            logger.error(f"Project {project.project_id}: {error_msg}")

    return successes, failures