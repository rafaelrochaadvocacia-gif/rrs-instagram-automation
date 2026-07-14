"""
Renderiza os slides de um carrossel como imagens PNG 1080x1350 com a identidade
visual do escritorio. Centraliza o bloco de texto verticalmente em cada slide.
"""
import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350
FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo", "logo_mark.png")

FONT_BOLD = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
FONT_MEDIUM = os.path.join(FONTS_DIR, "Poppins-Medium.ttf")
FONT_REGULAR = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")

WHITE = "#FFFFFF"
WHITE_SOFT = "#FAF6F0"
GRAY_MUTED = "#4B4B4B"

LOGO_HEIGHT = 56
LOGO_MARGIN = 50

_logo_cache = None

def _get_logo():
    global _logo_cache
    if _logo_cache is None:
        if not os.path.exists(LOGO_PATH):
            return None
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio = LOGO_HEIGHT / logo.height
        new_size = (max(1, int(logo.width * ratio)), LOGO_HEIGHT)
        _logo_cache = logo.resize(new_size, Image.LANCZOS)
    return _logo_cache

def _apply_logo(img):
    logo = _get_logo()
    if logo is None:
        return
    x = WIDTH - LOGO_MARGIN - logo.width
    y = LOGO_MARGIN
    img.paste(logo, (x, y), logo)

def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def _wrap(draw, text, font, max_width):
    """Quebra o texto em linhas que cabem em max_width, respeitando as quebras de
    linha explicitas do texto original (\n). Uma linha em branco no texto original
    (ex.: \n\n entre paragrafos) vira uma linha vazia na saida, preservando o
    espacamento visual pretendido por quem editou o texto."""
    if not text:
        return []
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            trial = (current + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines

def _draw_wrapped(draw, text, font, x, y, max_width, fill, line_spacing=1.3):
    lines = _wrap(draw, text, font, max_width)
    line_height = font.size * line_spacing
    for i, line in enumerate(lines):
        if line:
            draw.text((x, y + i * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height

def _block_height(headline_lines, body_lines, headline_size, body_size,
                   headline_spacing, body_spacing, gap):
    h = headline_lines * headline_size * headline_spacing
    if body_lines:
        h += gap + body_lines * body_size * body_spacing
    return h

def _base_slide(brand_color):
    return Image.new("RGB", (WIDTH, HEIGHT), _hex_to_rgb(brand_color))

def _footer(draw, index, total, ig_username, accent_color):
    font_small = ImageFont.truetype(FONT_MEDIUM, 26)
    draw.text((70, HEIGHT - 90), "@" + ig_username, font=font_small, fill=WHITE_SOFT)
    dots_y = HEIGHT - 55
    dot_gap = 22
    total_width = (total - 1) * dot_gap
    start_x = WIDTH - 70 - total_width
    for i in range(total):
        cx = start_x + i * dot_gap
        r = 6 if i == index else 4
        color = _hex_to_rgb(accent_color) if i == index else _hex_to_rgb(GRAY_MUTED)
        draw.ellipse((cx - r, dots_y - r, cx + r, dots_y + r), fill=color)

def render_cover(headline, practice_area, account):
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)
    accent = account["accent_color"]
    draw.rectangle((70, 110, 150, 118), fill=_hex_to_rgb(accent))

    font_eyebrow = ImageFont.truetype(FONT_MEDIUM, 30)
    draw.text((70, 140), practice_area.upper(), font=font_eyebrow, fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 78)
    max_width = WIDTH - 140
    lines = _wrap(draw, headline, font_headline, max_width)
    block_h = _block_height(len(lines), 0, font_headline.size, 0, 1.15, 1.4, 40)

    top, bottom = 210, HEIGHT - 220
    y = top + max(0, (bottom - top - block_h) / 2)
    _draw_wrapped(draw, headline, font_headline, 70, y, max_width, WHITE, line_spacing=1.15)

    font_cta = ImageFont.truetype(FONT_REGULAR, 32)
    draw.text((70, HEIGHT - 170), "Arraste para o lado >>", font=font_cta, fill=WHITE_SOFT)
    return img

def render_content_slide(headline, body, account):
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)
    accent = account["accent_color"]
    draw.rectangle((70, 100, 150, 108), fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 56)
    font_body = ImageFont.truetype(FONT_REGULAR, 38)
    max_width = WIDTH - 140

    h_lines = _wrap(draw, headline, font_headline, max_width)
    b_lines = _wrap(draw, body, font_body, max_width) if body else []
    block_h = _block_height(len(h_lines), len(b_lines), font_headline.size, font_body.size, 1.2, 1.4, 40)

    top, bottom = 150, HEIGHT - 150
    y = top + max(0, (bottom - top - block_h) / 2)

    y = _draw_wrapped(draw, headline, font_headline, 70, y, max_width, WHITE, line_spacing=1.2)
    if body:
        _draw_wrapped(draw, body, font_body, 70, y + 40, max_width, WHITE_SOFT, line_spacing=1.4)
    return img

def render_closing_slide(headline, body, account):
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)
    accent = account["accent_color"]
    draw.rectangle((70, 100, 150, 108), fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 52)
    font_body = ImageFont.truetype(FONT_REGULAR, 36)
    max_width = WIDTH - 140

    h_lines = _wrap(draw, headline, font_headline, max_width)
    b_lines = _wrap(draw, body, font_body, max_width) if body else []
    block_h = _block_height(len(h_lines), len(b_lines), font_headline.size, font_body.size, 1.2, 1.4, 40)

    has_author = bool(account.get("author_name"))
    top = 150
    bottom = HEIGHT - 150 - (110 if has_author else 0)
    y = top + max(0, (bottom - top - block_h) / 2)

    y = _draw_wrapped(draw, headline, font_headline, 70, y, max_width, WHITE, line_spacing=1.2)
    if body:
        _draw_wrapped(draw, body, font_body, 70, y + 40, max_width, WHITE_SOFT, line_spacing=1.4)

    if has_author:
        font_author = ImageFont.truetype(FONT_MEDIUM, 30)
        font_oab = ImageFont.truetype(FONT_REGULAR, 26)
        author_line = account["author_name"] + " - " + account["author_title"]
        author_lines = _wrap(draw, author_line, font_author, max_width)
        line_h = font_author.size * 1.25
        author_y = HEIGHT - 230 - (len(author_lines) - 1) * line_h
        for j, line in enumerate(author_lines):
            draw.text((70, author_y + j * line_h), line, font=font_author, fill=_hex_to_rgb(accent))
        oab_y = author_y + len(author_lines) * line_h + 12
        draw.text((70, oab_y), account["author_oab"], font=font_oab, fill=WHITE_SOFT)
    return img

def render_carousel(content, account, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    slides = content["slides"]
    total = len(slides)
    paths = []
    for i, slide in enumerate(slides):
        if i == 0:
            img = render_cover(slide["headline"], account["practice_area"], account)
        elif i == total - 1:
            img = render_closing_slide(slide["headline"], slide["body"], account)
        else:
            img = render_content_slide(slide["headline"], slide["body"], account)
        draw = ImageDraw.Draw(img)
        _footer(draw, i, total, account["ig_username"], account["accent_color"])
        _apply_logo(img)
        filename = "slide_" + str(i + 1).zfill(2) + ".png"
        path = os.path.join(output_dir, filename)
        img.save(path, "PNG")
        paths.append(path)
    return paths
