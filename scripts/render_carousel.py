"""
Renderiza os slides de um carrossel (dict retornado por generate_content.py) como
imagens PNG 1080x1350 (proporção 4:5, formato recomendado pelo Instagram) com a
identidade visual do escritório.
"""
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350
FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")

FONT_BOLD = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
FONT_MEDIUM = os.path.join(FONTS_DIR, "Poppins-Medium.ttf")
FONT_REGULAR = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")

WHITE = "#FFFFFF"
WHITE_SOFT = "#FAF6F0"
GRAY_MUTED = "#4B4B4B"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, max_width):
    if not text:
        return []
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(draw, text, font, x, y, max_width, fill, line_spacing=1.3, align="left"):
    lines = _wrap(draw, text, font, max_width)
    line_height = font.size * line_spacing
    for i, line in enumerate(lines):
        line_y = y + i * line_height
        if align == "center":
            line_width = draw.textlength(line, font=font)
            line_x = x + (max_width - line_width) / 2
        else:
            line_x = x
        draw.text((line_x, line_y), line, font=font, fill=fill)
    return y + len(lines) * line_height


def _base_slide(brand_color: str) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), _hex_to_rgb(brand_color))
    return img


def _footer(draw, index: int, total: int, ig_username: str, accent_color: str):
    font_small = ImageFont.truetype(FONT_MEDIUM, 26)
    draw.text((70, HEIGHT - 90), f"@{ig_username}", font=font_small, fill=WHITE_SOFT)
    dots_y = HEIGHT - 55
    dot_gap = 22
    total_width = (total - 1) * dot_gap
    start_x = WIDTH - 70 - total_width
    for i in range(total):
        cx = start_x + i * dot_gap
        r = 6 if i == index else 4
        color = _hex_to_rgb(accent_color) if i == index else _hex_to_rgb(GRAY_MUTED)
        draw.ellipse((cx - r, dots_y - r, cx + r, dots_y + r), fill=color)


def render_cover(headline: str, practice_area: str, account: dict) -> Image.Image:
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)

    accent = account["accent_color"]
    draw.rectangle((70, 110, 150, 118), fill=_hex_to_rgb(accent))

    font_eyebrow = ImageFont.truetype(FONT_MEDIUM, 30)
    draw.text((70, 140), practice_area.upper(), font=font_eyebrow, fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 78)
    _draw_wrapped(draw, headline, font_headline, 70, 240, WIDTH - 140, WHITE, line_spacing=1.15)

    font_cta = ImageFont.truetype(FONT_REGULAR, 32)
    draw.text((70, HEIGHT - 170), "Arraste para o lado »", font=font_cta, fill=WHITE_SOFT)

    return img


def render_content_slide(headline: str, body: str, account: dict) -> Image.Image:
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)
    accent = account["accent_color"]

    draw.rectangle((70, 100, 150, 108), fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 56)
    y = _draw_wrapped(draw, headline, font_headline, 70, 150, WIDTH - 140, WHITE, line_spacing=1.2)

    font_body = ImageFont.truetype(FONT_REGULAR, 38)
    _draw_wrapped(draw, body, font_body, 70, y + 40, WIDTH - 140, WHITE_SOFT, line_spacing=1.4)

    return img


def render_closing_slide(headline: str, body: str, account: dict) -> Image.Image:
    img = _base_slide(account["brand_color"])
    draw = ImageDraw.Draw(img)
    accent = account["accent_color"]

    draw.rectangle((70, 100, 150, 108), fill=_hex_to_rgb(accent))

    font_headline = ImageFont.truetype(FONT_BOLD, 52)
    y = _draw_wrapped(draw, headline, font_headline, 70, 150, WIDTH - 140, WHITE, line_spacing=1.2)

    font_body = ImageFont.truetype(FONT_REGULAR, 36)
    y = _draw_wrapped(draw, body, font_body, 70, y + 40, WIDTH - 140, WHITE_SOFT, line_spacing=1.4)

    if account.get("author_name"):
        font_author = ImageFont.truetype(FONT_MEDIUM, 30)
        author_line = f"{account['author_name']} — {account['author_title']}"
        oab_line = account["author_oab"]
        draw.text((70, HEIGHT - 230), author_line, font=font_author, fill=_hex_to_rgb(accent))
        draw.text((70, HEIGHT - 190), oab_line, font=ImageFont.truetype(FONT_REGULAR, 26), fill=WHITE_SOFT)

    return img


def render_carousel(content: dict, account: dict, output_dir: str) -> list[str]:
    """Renderiza todos os slides e salva como PNG. Retorna lista de caminhos, em ordem."""
    os.makedirs(output_dir, exist_ok=True)
    slides = content["slides"]
    total = len(slides)
    paths = []

    for i, slide in enumerate(slides):
        is_first = i == 0
        is_last = i == total - 1
        if is_first:
            img = render_cover(slide["headline"], account["practice_area"], account)
        elif is_last:
            img = render_closing_slide(slide["headline"], slide["body"], account)
        else:
            img = render_content_slide(slide["headline"], slide["body"], account)

        draw = ImageDraw.Draw(img)
        _footer(draw, i, total, account["ig_username"], account["accent_color"])

        path = os.path.join(output_dir, f"slide_{i+1:02d}.png")
        img.save(path, "PNG")
        paths.append(path)

    return paths


if __name__ == "__main__":
    import json

    sample_content = {
        "topic": "BPC/LOAS",
        "slides": [
            {"headline": "Você pode ter direito ao BPC/LOAS e não sabe", "body": ""},
            {"headline": "O que é o BPC/LOAS", "body": "É um benefício assistencial de um salário mínimo para idosos e pessoas com deficiência em situação de baixa renda."},
            {"headline": "Quem pode pedir", "body": "Idosos a partir de 65 anos ou pessoas com deficiência, com renda familiar per capita de até 1/4 do salário mínimo."},
            {"headline": "Erros comuns no pedido", "body": "Muitos pedidos são negados por documentação incompleta ou laudo médico insuficiente."},
            {"headline": "Vale a pena conversar com um advogado?", "body": "Cada caso tem particularidades. Uma análise pode esclarecer se você preenche os requisitos."},
        ],
        "caption": "Exemplo de legenda.",
    }
    with open(os.path.join(os.path.dirname(__file__), "..", "config", "accounts.json"), encoding="utf-8") as f:
        acc = json.load(f)["accounts"][0]
    out = render_carousel(sample_content, acc, "/tmp/carousel_preview")
    print("\n".join(out))
