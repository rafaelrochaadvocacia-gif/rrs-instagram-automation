"""
Renderiza os slides de um carrossel como imagens PNG 1080x1350, usando HTML/CSS +
Playwright (Chromium headless) no lugar do desenho direto em PIL usado antes. Segue
a linguagem visual do sistema "Gerador de Carrosseis Instagram": fundos claros e
escuros alternados para dar ritmo, barra de progresso e seta de arrastar embutidas
na propria imagem, pilula de categoria e selo de marca (iniciais) na capa, e
slide final em gradiente de marca com assinatura do autor (quando a conta
tiver autor).

As fontes continuam sendo as mesmas ja usadas pelo escritorio (Poppins Bold/Medium/
Regular, em assets/fonts/), embutidas como base64 direto no HTML -- sem nenhuma
dependencia de rede (nada de Google Fonts), para o pipeline continuar confiavel
independente do acesso a internet do runner.

A assinatura da funcao publica (render_carousel) e identica a versao anterior em
PIL, entao render_draft.py e o restante do pipeline continuam funcionando sem
nenhuma mudanca.
"""
import base64
import colorsys
import html
import io
import os

from playwright.sync_api import sync_playwright
from PIL import Image

WIDTH, HEIGHT = 1080, 1350
VIEW_W, VIEW_H = 420, 525
SCALE = WIDTH / VIEW_W

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
FONT_BOLD = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
FONT_MEDIUM = os.path.join(FONTS_DIR, "Poppins-Medium.ttf")
FONT_REGULAR = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "logo", "logo_mark_web.png")

WHITE = "#FFFFFF"
WHITE_MUTED = "rgba(255,255,255,0.62)"
DARK_TEXT = "#1A1918"
DARK_TEXT_SOFT = "#5C5750"

_font_cache = {}
_watermark_cache = {}


def _font_data_uri(path):
    if path not in _font_cache:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        _font_cache[path] = f"data:font/ttf;base64,{b64}"
    return _font_cache[path]


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(c)))):02X}" for c in rgb)


def _lighten(hex_color, amount):
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount))


def _darken(hex_color, amount):
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex((r * (1 - amount), g * (1 - amount), b * (1 - amount)))


def _blend(hex_a, hex_b, t):
    a, b = _hex_to_rgb(hex_a), _hex_to_rgb(hex_b)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _is_warm(hex_color):
    r, g, b = _hex_to_rgb(hex_color)
    h, _s, _v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return h <= 0.17 or h >= 0.92


def derive_palette(account):
    """A partir da cor de destaque (accent_color) da conta, deriva a paleta
    completa de tokens usada no novo sistema visual (ver projeto "Gerador de
    Carrosseis Instagram")."""
    primary = account["accent_color"]
    warm = _is_warm(primary)
    return {
        "primary": primary,
        "light": _lighten(primary, 0.22),
        "dark": _darken(primary, 0.32),
        "light_bg": "#F7F3EC" if warm else "#F2F4F7",
        "light_border": "#EAE3D6" if warm else "#E1E5EA",
        "dark_bg": _blend("#141210" if warm else "#0E1420", primary, 0.10),
    }


def _gradient(palette):
    return f"linear-gradient(165deg, {palette['dark']} 0%, {palette['primary']} 50%, {palette['light']} 100%)"


def _watermark_data_uri(tint_hex, opacity=0.10):
    """Le o logo do escritorio (assets/logo/logo_mark_web.png), aplica uma cor
    solida (tint_hex) usando apenas o formato/alfa original da marca como
    mascara, e reduz a opacidade -- para usar como marca d'agua discreta no
    fundo da capa. Cacheia por combinacao de cor/opacidade."""
    cache_key = (tint_hex, opacity)
    if cache_key in _watermark_cache:
        return _watermark_cache[cache_key]
    if not os.path.exists(LOGO_PATH):
        _watermark_cache[cache_key] = None
        return None
    logo = Image.open(LOGO_PATH).convert("RGBA")
    _r, _g, _b, alpha = logo.split()
    tint_rgb = _hex_to_rgb(tint_hex)
    solid = Image.new("RGBA", logo.size, tint_rgb + (0,))
    scaled_alpha = alpha.point(lambda p: int(p * opacity))
    solid.putalpha(scaled_alpha)
    buf = io.BytesIO()
    solid.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    _watermark_cache[cache_key] = data_uri
    return data_uri


def _fmt_body(text):
    """Escapa o texto e transforma quebras de linha explicitas (\\n) em <br>,
    preservando a formatacao em paragrafos curtos que o autor escreveu -- ao
    contrario da versao PIL anterior, que colapsava as quebras manuais."""
    if not text:
        return ""
    escaped = html.escape(text)
    return escaped.replace("\n\n", "<br><br>").replace("\n", "<br>")


def _progress_and_arrow(index, total, is_light, ig_username, show_arrow):
    track_color = "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.14)"
    fill_color = "#1A1918" if is_light else "#FFFFFF"
    label_color = "rgba(0,0,0,0.4)" if is_light else "rgba(255,255,255,0.55)"
    handle_color = "rgba(0,0,0,0.55)" if is_light else "rgba(255,255,255,0.7)"
    pct = ((index + 1) / total) * 100

    footer = f"""
    <div style="position:absolute;left:0;right:0;bottom:0;padding:0 28px 20px;z-index:10;">
      <div style="font-size:11px;font-weight:500;color:{handle_color};margin-bottom:10px;">@{html.escape(ig_username)}</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <div style="flex:1;height:3px;background:{track_color};border-radius:2px;overflow:hidden;">
          <div style="height:100%;width:{pct:.2f}%;background:{fill_color};border-radius:2px;"></div>
        </div>
        <span style="font-size:11px;color:{label_color};font-weight:500;">{index + 1}/{total}</span>
      </div>
    </div>
    """

    if not show_arrow:
        return footer, ""

    arrow_bg = "rgba(0,0,0,0.06)" if is_light else "rgba(255,255,255,0.08)"
    arrow_stroke = "rgba(0,0,0,0.28)" if is_light else "rgba(255,255,255,0.4)"
    arrow = f"""
    <div style="position:absolute;right:0;top:0;bottom:0;width:44px;z-index:9;display:flex;align-items:center;justify-content:center;background:linear-gradient(to right,transparent,{arrow_bg});">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M9 6l6 6-6 6" stroke="{arrow_stroke}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    """
    return footer, arrow


def _logo_lockup(account, palette, is_light):
    initial = account["page_name"].strip()[0].upper()
    name_color = DARK_TEXT if is_light else WHITE
    return f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:28px;">
      <div style="width:40px;height:40px;border-radius:50%;background:{palette['primary']};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
        <span style="font-family:'Poppins';font-weight:700;font-size:17px;color:#FFFFFF;">{html.escape(initial)}</span>
      </div>
      <span style="font-family:'Poppins';font-weight:600;font-size:13px;letter-spacing:0.3px;color:{name_color};">{html.escape(account['page_name'])}</span>
    </div>
    """


def _tag_pill(text, color):
    return f"""<span style="display:inline-block;font-family:'Poppins';font-weight:600;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{color};margin-bottom:16px;">{html.escape(text)}</span>"""


def _divider(color):
    return f"""<div style="width:56px;height:3px;background:{color};margin:18px 0 22px;border-radius:2px;"></div>"""


def _signature_block(account, is_light, bottom_px):
    """Bloco de assinatura do fechamento -- posicionado de forma absoluta,
    ancorado a uma distancia fixa do rodape, para NUNCA se sobrepor ao
    headline/corpo do slide (independente do tamanho do texto do slide)."""
    name_color = DARK_TEXT if is_light else WHITE
    meta_color = DARK_TEXT_SOFT if is_light else WHITE_MUTED
    divider_color = "rgba(0,0,0,0.12)" if is_light else "rgba(255,255,255,0.18)"
    return f"""
    <div style="position:absolute;left:34px;right:34px;bottom:{bottom_px}px;padding-top:14px;border-top:1px solid {divider_color};z-index:2;">
      <div style="font-family:'Poppins';font-weight:600;font-size:15px;color:{name_color};margin-bottom:3px;">{html.escape(account['author_name'])}</div>
      <div style="font-family:'Poppins';font-weight:400;font-size:12px;color:{meta_color};line-height:1.35;">{html.escape(account['author_title'])}</div>
      <div style="font-family:'Poppins';font-weight:400;font-size:12px;color:{meta_color};line-height:1.35;">Escritorio Rafael Rocha e Santos Advocacia</div>
    </div>
    """


FOOTER_RESERVE = 74  # espaco reservado no rodape (@handle + barra + contador)
SIGNATURE_RESERVE = 92  # espaco extra reservado acima do rodape para a assinatura


DRAFTS_PUBLISHED_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts", "published")


def _cover_is_dark(account_key):
    """Alterna a cor de fundo da capa entre clara e escura a cada novo post
    dessa conta -- conta quantos posts ja foram publicados (drafts/published/
    {account_key}_*.json): quantidade par usa capa clara, impar usa capa
    escura. Assim a alternancia se mantem correta sozinha, sem precisar
    guardar nenhum estado extra."""
    if not os.path.isdir(DRAFTS_PUBLISHED_DIR):
        return False
    count = sum(
        1
        for fname in os.listdir(DRAFTS_PUBLISHED_DIR)
        if fname.startswith(f"{account_key}_") and fname.endswith(".json")
    )
    return count % 2 == 1


def _slide_html(index, total, headline, body, account, palette, fonts, cover_is_dark=False):
    is_first = index == 0
    is_last = index == total - 1
    has_author = bool(account.get("author_name"))
    show_signature = is_last and has_author

    if is_first:
        is_light = not cover_is_dark
        bg = palette["dark_bg"] if cover_is_dark else palette["light_bg"]
        justify = "center"
        tag_color = palette["light"] if cover_is_dark else palette["primary"]
    elif is_last:
        bg = _gradient(palette)
        is_light = False
        justify = "flex-start"
        tag_color = "rgba(255,255,255,0.65)"
    else:
        is_light = index % 2 == 0
        bg = palette["light_bg"] if is_light else palette["dark_bg"]
        justify = "center"
        tag_color = palette["primary"] if is_light else palette["light"]

    heading_color = DARK_TEXT if is_light else WHITE
    body_color = DARK_TEXT_SOFT if is_light else WHITE_MUTED
    accent_bar = f"""<div style="position:absolute;left:0;top:0;bottom:0;width:6px;background:{palette['primary']};z-index:3;"></div>"""

    # A pilula de categoria e o selo de marca aparecem so na capa -- repeti-los
    # no fechamento so consumiria espaco (que o fechamento precisa para a
    # assinatura) sem agregar, ja que a marca ja foi apresentada no slide 1.
    tag_html = ""
    logo_html = ""
    watermark_html = ""
    if is_first:
        tag_html = _tag_pill(account["practice_area"].upper(), tag_color)
        logo_html = _logo_lockup(account, palette, is_light)
        # Marca d'agua do logo do escritorio no fundo da capa, a pedido do
        # Rafael -- tom neutro e opacidade baixa para nao competir com o texto.
        wm_uri = _watermark_data_uri(DARK_TEXT_SOFT if is_light else WHITE, opacity=0.10)
        if wm_uri:
            watermark_html = (
                f'<img src="{wm_uri}" style="position:absolute;top:52%;left:50%;'
                f'transform:translate(-50%,-50%);width:320px;z-index:1;pointer-events:none;" />'
            )

    # Fechamento usa um headline um pouco menor (mesma proporcao da versao
    # anterior em PIL) para sobrar mais espaco vertical para corpo + assinatura.
    headline_size = "24px" if is_last else "29px"

    body_html = ""
    divider_html = ""
    if body:
        if not is_first:
            divider_html = _divider(palette["primary"] if is_light else palette["light"])
        body_html = f"""<p style="font-family:'Poppins';font-weight:400;font-size:14.5px;line-height:1.55;color:{body_color};margin-top:{'10px' if is_first else '0'};">{_fmt_body(body)}</p>"""

    # A area de headline/corpo fica em uma caixa de posicao absoluta, com uma
    # margem inferior reservada para o rodape (e, no fechamento, tambem para a
    # assinatura) -- assim o texto nunca pode se sobrepor a esses elementos,
    # nao importa o quao longo seja o slide. overflow:hidden e uma rede de
    # seguranca final caso algum slide venha com texto excepcionalmente longo.
    bottom_reserve = FOOTER_RESERVE + (SIGNATURE_RESERVE if show_signature else 0)
    top_pad = 48 if is_last else 64
    signature_html = _signature_block(account, is_light, FOOTER_RESERVE + 10) if show_signature else ""

    footer_html, arrow_html = _progress_and_arrow(
        index, total, is_light, account["ig_username"], show_arrow=not is_last
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
  @font-face {{ font-family:'Poppins'; src:url({fonts['bold']}) format('truetype'); font-weight:700; }}
  @font-face {{ font-family:'Poppins'; src:url({fonts['medium']}) format('truetype'); font-weight:500; }}
  @font-face {{ font-family:'Poppins'; src:url({fonts['regular']}) format('truetype'); font-weight:400; }}
  * {{ margin:0; padding:0; box-sizing:border-box; -webkit-font-smoothing:antialiased; }}
  html, body {{ width:{VIEW_W}px; height:{VIEW_H}px; overflow:hidden; }}
</style></head>
<body>
  <div style="position:relative;width:{VIEW_W}px;height:{VIEW_H}px;background:{bg};overflow:hidden;font-family:'Poppins',sans-serif;">
    {accent_bar}
    {watermark_html}
    <div style="position:absolute;top:0;left:0;right:0;bottom:{bottom_reserve}px;padding:{top_pad}px 34px 12px;overflow:hidden;display:flex;flex-direction:column;justify-content:{justify};z-index:2;">
      {tag_html}
      {logo_html}
      <h1 style="font-family:'Poppins';font-weight:700;font-size:{headline_size};letter-spacing:-0.3px;line-height:1.16;color:{heading_color};">{_fmt_body(headline)}</h1>
      {divider_html}
      {body_html}
    </div>
    {signature_html}
    {footer_html}
    {arrow_html}
  </div>
</body></html>"""


def render_carousel(content, account, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    slides = content["slides"]
    total = len(slides)
    palette = derive_palette(account)
    cover_is_dark = _cover_is_dark(account["key"])
    fonts = {
        "bold": _font_data_uri(FONT_BOLD),
        "medium": _font_data_uri(FONT_MEDIUM),
        "regular": _font_data_uri(FONT_REGULAR),
    }

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": VIEW_W, "height": VIEW_H},
            device_scale_factor=SCALE,
        )
        for i, slide in enumerate(slides):
            slide_html = _slide_html(
                i, total, slide["headline"], slide.get("body", ""), account, palette, fonts,
                cover_is_dark=cover_is_dark,
            )
            page.set_content(slide_html, wait_until="load")
            page.wait_for_timeout(150)
            filename = "slide_" + str(i + 1).zfill(2) + ".png"
            path = os.path.join(output_dir, filename)
            page.screenshot(path=path, clip={"x": 0, "y": 0, "width": VIEW_W, "height": VIEW_H})
            paths.append(path)
        browser.close()
    return paths
