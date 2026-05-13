"""Configuration handling for PD Generator."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PageConfig:
    """Page dimension configuration."""
    width_mm: float = 594.0
    height_mm: float = 841.0


@dataclass
class LayoutConfig:
    """Layout configuration for poster elements."""
    image_height_mm: float = 434.0
    image_fit_mode: str = "cover"
    content_padding_left_mm: float = 40.0
    content_padding_right_mm: float = 40.0
    content_padding_top_mm: float = 20.0
    content_padding_bottom_mm: float = 20.0
    text_column_width_mm: float = 225.0


@dataclass
class FontConfig:
    """Font configuration."""
    title_font: str = "DejaVuSans-Bold"
    title_size: float = 48.0
    heading_font: str = "DejaVuSans-Bold"
    heading_size: float = 24.0
    body_font: str = "DejaVuSans"
    body_size: float = 18.0
    min_font_size: float = 10.0
    line_spacing: float = 1.2


@dataclass
class OutputConfig:
    """Output configuration."""
    naming_pattern: str = "{project_id}_{project_name}"


@dataclass
class LogoConfig:
    """Logo configuration."""
    height_mm: float = 80.0
    spacing_mm: float = 5.0
    margin_left_mm: float = -50.0
    margin_bottom_mm: float = 10.0


@dataclass
class Config:
    """Main configuration container."""
    page: PageConfig = field(default_factory=PageConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    fonts: FontConfig = field(default_factory=FontConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logos: LogoConfig = field(default_factory=LogoConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        config = cls()

        if "page" in data:
            page_data = data["page"]
            config.page = PageConfig(
                width_mm=page_data.get("width_mm", 594.0),
                height_mm=page_data.get("height_mm", 841.0),
            )

        if "layout" in data:
            layout_data = data["layout"]
            config.layout = LayoutConfig(
                image_height_mm=layout_data.get("image_height_mm", 434.0),
                image_fit_mode=layout_data.get("image_fit_mode", "cover"),
                content_padding_left_mm=layout_data.get("content_padding_left_mm", 40.0),
                content_padding_right_mm=layout_data.get("content_padding_right_mm", 40.0),
                content_padding_top_mm=layout_data.get("content_padding_top_mm", 20.0),
                content_padding_bottom_mm=layout_data.get("content_padding_bottom_mm", 20.0),
                text_column_width_mm=layout_data.get("text_column_width_mm", 225.0),
            )

        if "fonts" in data:
            fonts_data = data["fonts"]
            config.fonts = FontConfig(
                title_font=fonts_data.get("title_font", "DejaVuSans-Bold"),
                title_size=fonts_data.get("title_size", 48.0),
                heading_font=fonts_data.get("heading_font", "DejaVuSans-Bold"),
                heading_size=fonts_data.get("heading_size", 24.0),
                body_font=fonts_data.get("body_font", "DejaVuSans"),
                body_size=fonts_data.get("body_size", 18.0),
                min_font_size=fonts_data.get("min_font_size", 10.0),
                line_spacing=fonts_data.get("line_spacing", 1.2),
            )

        if "output" in data:
            output_data = data["output"]
            config.output = OutputConfig(
                naming_pattern=output_data.get("naming_pattern", "{project_id}_{project_name}"),
            )

        if "logos" in data:
            logos_data = data["logos"]
            config.logos = LogoConfig(
                height_mm=logos_data.get("height_mm", 80.0),
                spacing_mm=logos_data.get("spacing_mm", 5.0),
                margin_left_mm=logos_data.get("margin_left_mm", -50.0),
                margin_bottom_mm=logos_data.get("margin_bottom_mm", 10.0),
            )

        return config

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from file."""
        if path is None:
            path = Path("config.yaml")

        if not path.exists():
            return cls()

        return cls.from_yaml(path)
