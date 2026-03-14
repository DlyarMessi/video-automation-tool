from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ==================== 项目路径 ====================
ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input_videos"
OUTPUT_DIR = ROOT / "output_videos"
DATA_DIR = ROOT / "data"
BRANDS_DIR = DATA_DIR / "brands"
SCRIPTS_DIR = ROOT / "scripts"

# ==================== 字幕与视觉设置 ====================
# 建议：指向真实 ttf/otf 文件路径（跨平台更稳定）
FONT_PATH = "Arial"

# 水印
WATERMARK_OPACITY = 0.85
WATERMARK_MARGIN = 48
WATERMARK_HEIGHT = 96
WATERMARK_POSITION = "top-right"  # top-right|top-left|bottom-right|bottom-left

# ==================== 音频设置 ====================
BGM_VOLUME = 0.22
KEEP_ORIGINAL_AUDIO = True

# ==================== 转场/效果 ====================
FADEIN_SECONDS = 0.20
FADEOUT_SECONDS = 0.20

# ==================== 输出参数 ====================
FPS = 30
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
PRESET = "medium"
THREADS = 4

# ==================== 公司配置 ====================
@dataclass(frozen=True)
class CompanyAssets:
    logo: Path
    bgm: Path
    prefix: str

COMPANY_CONFIG: dict[str, CompanyAssets] = {
    "Siglen": CompanyAssets(
        logo=BRANDS_DIR / "siglen" / "logo.png",
        bgm=BRANDS_DIR / "siglen" / "bgm" / "default.mp3",
        prefix="Siglen_Promo_",
    ),
    "Fareo": CompanyAssets(
        logo=BRANDS_DIR / "fareo" / "logo.png",
        bgm=BRANDS_DIR / "fareo" / "bgm" / "default.mp3",
        prefix="Fareo_Promo_",
    ),
}

# ==================== 画布/分辨率 ====================
# 只有当脚本里 project.output.size 或 project.output.format 指定时，才会做统一画布适配
CANVAS_PRESETS = {
    "portrait_1080x1920": (1080, 1920),
    "landscape_1920x1080": (1920, 1080),
}

SAFE_MARGIN = {
    "portrait_1080x1920": {"top": 120, "bottom": 220, "left": 90, "right": 90},
    "landscape_1920x1080": {"top": 60, "bottom": 90, "left": 80, "right": 80},
}

# ==================== 字幕样式预设 ====================
# 竖屏（9:16）
STYLE_PRESETS_PORTRAIT = {
    "default": {
        "font": FONT_PATH,
        "fontsize": 52,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "center",
        "position": "bottom",
        "margin_bottom": 260,
        "max_width_ratio": 0.86,
    },
    "lower_third": {
        "font": FONT_PATH,
        "fontsize": 46,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "left",
        "position": "bottom",
        "margin_bottom": 300,
        "max_width_ratio": 0.82,
    },
    "slogan": {
        "font": FONT_PATH,
        "fontsize": 78,
        "color": "#FFD54A",
        "stroke_color": "black",
        "stroke_width": 4,
        "method": "caption",
        "align": "center",
        "position": "center",
        "margin_bottom": 0,
        "max_width_ratio": 0.86,
    },
    "top_tag": {
        "font": FONT_PATH,
        "fontsize": 44,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "center",
        "position": "top",
        "margin_bottom": 0,
        "max_width_ratio": 0.88,
    },
}

# 横屏（16:9）建议默认
STYLE_PRESETS_LANDSCAPE = {
    "default": {
        "font": FONT_PATH,
        "fontsize": 44,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "center",
        "position": "bottom",
        "margin_bottom": 90,
        "max_width_ratio": 0.78,
    },
    "lower_third": {
        "font": FONT_PATH,
        "fontsize": 40,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "left",
        "position": "bottom",
        "margin_bottom": 110,
        "max_width_ratio": 0.74,
    },
    "slogan": {
        "font": FONT_PATH,
        "fontsize": 64,
        "color": "#FFD54A",
        "stroke_color": "black",
        "stroke_width": 4,
        "method": "caption",
        "align": "center",
        "position": "center",
        "margin_bottom": 0,
        "max_width_ratio": 0.80,
    },
    "top_tag": {
        "font": FONT_PATH,
        "fontsize": 38,
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "method": "caption",
        "align": "center",
        "position": "top",
        "margin_bottom": 0,
        "max_width_ratio": 0.82,
    },
}

# ==================== 脚本优先级 ====================
SCRIPT_EXT_PRIORITY = [".yaml", ".yml", ".toml", ".json", ".txt"]