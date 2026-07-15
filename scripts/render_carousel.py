"""
Renderiza os slides de um carrossel como imagens PNG 1080x1350 com a identidade
visual do escritorio: fundo com leve gradiente/vinheta na cor de marca, uma marca
d'agua grande e translucida do logo ao fundo, uma barra vertical de acento na
lateral esquerda (assinatura visual consistente em todo slide), brilho suave no
canto (cor de destaque da conta), linha divisoria entre titulo e corpo com espaco
generoso ao redor, e uma barra de progresso fina no rodape alem dos pontos de
paginacao. Centraliza o bloco de texto verticalmente em cada slide.
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

WATERMARK_HEIGHT_RATIO = 0.62  # altura da marca d'agua em relacao a altura do slide
WATERMARK_OPACITY = 0.16  # 0 a 1
WATERMARK_Y_RATIO = 0.46  # posicao vertical do centro da marca d'agua

MARGIN_X = 96
MARGIN_RIGHT = 70
LEFT_BAR_WIDTH = 10
CONTENT_MAX_WIDTH = WIDTH - MARGIN_X - MARGIN_RIGHT

_watermark_cache = None


def _get_watermark():
    """Logo grande e translucida, pre-processada e cacheada -- usada como marca
    d'agua de fundo em todo slide."""
    global _watermark_cache
    if _watermark_cache is None:
        if not os.path.exists(LOGO_PATH):
            return None
        logo = Image.open(LOGO_PATH).convert("RGBA")
        target_h = int(HEIGHT * WATERMARK_HEIGHT_RATIO)
        ratio = target_h / logo.height
        new_size = (max(1, int(logo.width * ratio)), target_h)
        big_logo = logo.resize(new_size, Image.LANCZOS)
        r, g, b, a = big_logo.split()
        a = a.point(lambda p: int(p * WATERMARK_OPACITY))
        big_logo.putalpha(a)
        _watermark_cache = big_logo
    return _watermark_cache


def _apply_watermark(img):
    logo = _get_watermark()
    if logo is None:
        return img
    x = (WIDTH - logo.width) // 2
    y = int(HEIGHT * WATERMARK_Y_RATIO) - logo.height // 2
    base = img.convert("RGBA")
    base.paste(logo, (x, y), logo)
    return base.convert("RGB")


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _blend_rgb(rgb_a, rgb_b, t):
    """Mistura duas cores RGB; t=0 -> rgb_a, t=1 -> rgb_b."""
    return tuple(int(rgb_a[i] + (rgb_b[i] - rgb_a[i]) * t) for i in range(3))


def _wrap(draw, text, font, max_width):
    if not text:
        return []
    words = text.split()
    lines, current = [], ""
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
        draw.text((x, y + i * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def _block_height(headline_lines, body_lines, headline_size, body_size,
                   headline_spacing, body_spacing, gap):
    h = headline_lines * headline_size * headline_spacing
    if body_lines:
        h += gap + body_lines * body_size * body_spacing
    return h


def _base_slide(brand_color, accent_color):
    """Fundo com leve gradiente vertical (banho sutil da cor de destaque no topo,
    esmaecendo para a cor de marca solida embaixo) + marca d'agua grande do logo
    ao fundo + brilho suave no canto superior direito."""
    brand_rgb = _hex_to_rgb(brand_color)
    accent_rgb = _hex_to_rgb(accent_color)
    top_rgb = _blend_rgb(brand_rgb, accent_rgb, 0.16)

    img = Image.new("RGB", (WIDTH, HEIGHT), brand_rgb)
    px = img.load()
    fade_height = int(HEIGHT * 0.55)
    for y in range(fade_height):
        t = y / fade_height
        row_rgb = _blend_rgb(top_rgb, brand_rgb, t)
        for x in range(WIDTH):
            px[x, y] = row_rgb

    img = _apply_watermark(img)
    img = _add_corner_glow(img, accent_color)
    return img


def _add_corner_glow(img, accent_color):
    """Brilho suave e desfocado no canto superior direito, na cor de destaque da
    conta -- textura discreta, nao compete com o texto."""
    accent_rgb = _hex_to_rgb(accent_color)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    cx, cy, r = WIDTH + 60, -80, 520
    odraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent_rgb + (26,))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _left_accent_bar(draw, accent_color):
    """Barra vertical de acento na lateral esquerda -- assinatura visual presente
    em todo slide, reforca identidade de marca mesmo sem o logo."""
    draw.rectangle((0, 0, LEFT_BAR_WIDTH, HEIGHT), fill=_hex_to_rgb(accent_color))


def _pill_badge(draw, text, x, y, accent_color, font, text_color=None):
    """Selo em formato de pilula (fundo arredondado na cor de destaque) -- usado
    para a categoria/area de atuacao na capa. Retorna a altura do selo."""
    pad_x, pad_y = 22, 12
    text_w = draw.textlength(text, font=font)
    text_h = font.size
    box = (x, y, x + text_w + pad_x * 2, y + text_h + pad_y * 2)
    fill_rgb = _hex_to_rgb(accent_color)
    draw.rounded_rectangle(box, radius=(text_h + pad_y * 2) / 2, fill=fill_rgb)
    fg = text_color or WHITE
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=fg)
    return box[3] - box[1]


def _number_badge(img, number, x, y, accent_color):
    """Circulo numerado (selo de indice). Nao Ã© mais usado nos slides de conteudo
    (removido a pedido do Rafael), mas a funcao fica disponivel caso volte a ser
    necessaria em outro lugar."""
    d = 64
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    accent_rgb = _hex_to_rgb(accent_color)
    odraw.ellipse((x, y, x + d, y + d), fill=accent_rgb + (255,))
    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)
    font_num = ImageFont.truetype(FONT_BOLD, 30)
    label = str(number)
    tw = draw.textlength(label, font=font_num)
    draw.text((x + (d - tw) / 2, y + (d - 34) / 2), label, font=font_num, fill=WHITE)
    return composed, d


def _divider(draw, x, y, width, accent_color):
    draw.rectangle((x, y, x + width, y + 3), fill=_hex_to_rgb(accent_color))


def _footer(draw, index, total, ig_username, accent_color):
    accent_rgb = _hex_to_rgb(accent_color)

    # barra de progresso fina, borda a borda, no rodape absoluto
    progress_w = WIDTH * ((index + 1) / total)
    draw.rectangle((0, HEIGHT - 6, WIDTH, HEIGHT), fill=_hex_to_rgb(GRAY_MUTED))
    draw.rectangle((0, HEIGHT - 6, progress_w, HEIGHT), fill=accent_rgb)

    font_small = ImageFont.truetype(FONT_MEDIUM, 26)
    draw.text((MARGIN_X, HEIGHT - 100), "@" + ig_username, font=font_small, fill=WHITE_SOFT)

    # Numeracao "NN / NN" removida do rodape a pedido do Rafael -- mantidos apenas
    # o @usuario, a barra de progresso e os pontos de paginacao abaixo.

    dots_y = HEIGHT - 62
    dot_gap = 20
    total_width = (total - 1) * dot_gap
    start_x = WIDTH - MARGIN_RIGHT - total_width
    for i in range(total):
        cx = start_x + i * dot_gap
        r = 6 if i == index else 4
        color = accent_rgb if i == index else _hex_to_rgb(GRAY_MUTED)
        draw.ellipse((cx - r, dots_y - r, cx + r, dots_y + r), fill=color)


def render_cover(headline, practice_area, account):
    accent = account["accent_color"]
    img = _base_slide(account["brand_color"], accent)
    draw = ImageDraw.Draw(img)
    _left_accent_bar(draw, accent)

    font_eyebrow = ImageFont.truetype(FONT_MEDIUM, 26)
    badge_h = _pill_badge(draw, practice_area.upper(), MARGIN_X, 130, accent, font_eyebrow)

    font_headline = ImageFont.truetype(FONT_BOLD, 76)
    max_width = CONTENT_MAX_WIDTH
    lines = _wrap(draw, headline, font_headline, max_width)
    block_h = _block_height(len(lines), 0, font_headline.size, 0, 1.15, 1.4, 40)

    top = 130 + badge_h + 50
    bottom = HEIGHT - 220
    y = top + max(0, (bottom - top - block_h) / 2)
    _draw_wrapped(draw, headline, font_headline, MARGIN_X, y, max_width, WHITE, line_spacing=1.15)

    font_cta = ImageFont.truetype(FONT_REGULAR, 30)
    draw.text((MARGIN_X, HEIGHT - 170), "Arraste para o lado >>", font=font_cta, fill=WHITE_SOFT)
    return img


def render_content_slide(headline, body, account, slide_number=None):
    accent = account["accent_color"]
    img = _base_slide(account["brand_color"], accent)

    # Selo numerico removido dos slides de conteudo a pedido do Rafael.
    draw = ImageDraw.Draw(img)
    _left_accent_bar(draw, accent)

    font_headline = ImageFont.truetype(FONT_BOLD, 54)
    font_body = ImageFont.truetype(FONT_REGULAR, 37)
    max_width = CONTENT_MAX_WIDTH

    h_lines = _wrap(draw, headline, font_headline, max_width)
    b_lines = _wrap(draw, body, font_body, max_width) if body else []
    # gap aumentado (era 40) para dar mais respiro entre headline e corpo
    block_h = _block_height(len(h_lines), len(b_lines), font_headline.size, font_body.size, 1.2, 1.4, 96)
    if b_lines:
        block_h += 36  # espaco extra para a linha divisoria

    top = 170
    bottom = HEIGHT - 170
    y = top + max(0, (bottom - top - block_h) / 2)

    y = _draw_wrapped(draw, headline, font_headline, MARGIN_X, y, max_width, WHITE, line_spacing=1.2)
    if body:
        y += 56  # espaco antes da linha divisoria (era 18)
        _divider(draw, MARGIN_X, y, 64, accent)
        y += 74  # espaco depois da linha divisoria, antes do corpo (era 36)
        _draw_wrapped(draw, body, font_body, MARGIN_X, y, max_width, WHITE_SOFT, line_spacing=1.4)
    return img


def render_closing_slide(headline, body, account):
    accent = account["accent_color"]
    img = _base_slide(account["brand_color"], accent)
    draw = ImageDraw.Draw(img)
    _left_accent_bar(draw, accent)

    font_headline = ImageFont.truetype(FONT_BOLD, 50)
    font_body = ImageFont.truetype(FONT_REGULAR, 35)
    max_width = CONTENT_MAX_WIDTH

    h_lines = _wrap(draw, headline, font_headline, max_width)
    b_lines = _wrap(draw, body, font_body, max_width) if body else []
    block_h = _block_height(len(h_lines), len(b_lines), font_headline.size, font_body.size, 1.2, 1.4, 40)

    has_author = bool(account.get("author_name"))
    reserved_bottom = 220 if has_author else 0
    top = 170
    bottom = HEIGHT - 170 - reserved_bottom
    y = top + max(0, (bottom - top - block_h) / 2)

    y = _draw_wrapped(draw, headline, font_headline, MARGIN_X, y, max_width, WHITE, line_spacing=1.2)
    if body:
        _draw_wrapped(draw, body, font_body, MARGIN_X, y + 40, max_width, WHITE_SOFT, line_spacing=1.4)

    if has_author:
        # Assinatura sem numero de OAB (pedido do Rafael): nome, titulo/especialidade e,
        # por pedido posterior, mencao explicita ao escritorio em todo fechamento.
        divider_y = HEIGHT - 300
        _divider(draw, MARGIN_X, divider_y, 64, accent)

        font_name = ImageFont.truetype(FONT_MEDIUM, 30)
        font_meta = ImageFont.truetype(FONT_REGULAR, 26)
        font_firm = ImageFont.truetype(FONT_REGULAR, 24)

        name_y = divider_y + 26
        draw.text((MARGIN_X, name_y), account["author_name"], font=font_name, fill=WHITE)

        title_y = name_y + 40
        firm_y = _draw_wrapped(draw, account["author_title"], font_meta, MARGIN_X, title_y, CONTENT_MAX_WIDTH, WHITE_SOFT, line_spacing=1.25)

        draw.text((MARGIN_X, firm_y + 8), "Escritorio Rafael Rocha e Santos Advocacia", font=font_firm, fill=WHITE_SOFT)
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
            img = render_content_slide(slide["headline"], slide["body"], account, slide_number=i + 1)
        draw = ImageDraw.Draw(img)
        _footer(draw, i, total, account["ig_username"], account["accent_color"])
        filename = "slide_" + str(i + 1).zfill(2) + ".png"
        path = os.path.join(output_dir, filename)
        img.save(path, "PNG")
        paths.append(path)
    return paths
