"""
Transforma cada artigo novo do blog em um carrossel para o Instagram (e a Pagina do
Facebook vinculada), com revisao automatica antes da publicacao.

Fluxo de cada execucao (workflow blog_to_carousel.yml, diario):
  1. Se existir o arquivo PAUSAR na raiz do repositorio, nao faz nada.
  2. Le o feed do blog e separa os artigos ainda nao registrados em state/blog_posts.json.
  3. Escolhe a conta pela categoria do artigo (config/blog_pipeline.json) e processa no
     maximo N artigos por conta por execucao -- os demais ficam para as proximas.
  4. Redator (Claude) escreve o carrossel so com base no artigo; o carrossel e renderizado;
     o revisor (outra chamada do Claude) confere texto e imagens. Se reprovar, o redator
     corrige e o ciclo se repete ate review_max_rounds vezes.
  5. Modo "automatico" + aprovado: publica no Instagram e no Facebook.
     Modo "sombra", ou reprovado: deixa em drafts/pending/ e abre uma issue no GitHub
     pedindo a decisao de Rafael (a issue chega por e-mail).

Uso:
  python blog_to_carousel.py             -> execucao normal
  python blog_to_carousel.py --baseline  -> marca todos os artigos atuais do feed como ja
                                            vistos, sem gerar nada (usar uma vez, na instalacao)
Variavel opcional FORCE_POST_URL: processa esse artigo do feed mesmo que ja registrado.
"""
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone

import requests

from blog_source import fetch_article_text, fetch_feed
from generate_content import SYSTEM_PROMPT, _run_claude_code, parse_json_reply, signing_rules
from publish_draft import facebook_caption
from publish_instagram import upload_to_cloudinary
from render_carousel import render_carousel
from review_carousel import format_feedback, review_carousel

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PIPELINE_CONFIG = os.path.join(ROOT, "config", "blog_pipeline.json")
ACCOUNTS_CONFIG = os.path.join(ROOT, "config", "accounts.json")
STATE_PATH = os.path.join(ROOT, "state", "blog_posts.json")
PENDING_DIR = os.path.join(ROOT, "drafts", "pending")
PAUSE_FILE = os.path.join(ROOT, "PAUSAR")
MAX_ATTEMPTS = 3

WRITER_PROMPT_TEMPLATE = """Transforme o artigo do blog abaixo em um carrossel de Instagram \
(8 a 10 slides) para a conta {page_name} (@{ig_username}), area "{practice_area}". O mesmo \
carrossel tambem sera publicado na Pagina do Facebook da conta.

FONTE UNICA: use SOMENTE informacoes que estao no artigo. Nao acrescente lei, artigo, sumula, \
prazo, valor, percentual, data, requisito ou documento que nao esteja nele, e nao transforme em \
regra obrigatoria o que o artigo trata como possibilidade. Selecione o que for mais util e \
interessante para quem rola o feed -- o carrossel nao precisa (nem deve) resumir o artigo inteiro.

{author_line}
Regra de assinatura da legenda: {signing_instruction}

LEGENDA (campo "caption"), em paragrafos curtos separados por linha em branco (\\n\\n):
(1) gancho que funciona sozinho; (2) contexto especifico do tema; (3) o insight principal, \
reforcando autoridade tecnica sem jargao; (4) convite a comentar, salvar ou compartilhar; \
(5) convite sobrio para falar com a equipe, sem forcar venda, com a assinatura conforme a regra \
acima; (6) uma frase avisando que o artigo completo esta no blog e pode ser lido pelo QR Code do \
ultimo slide; (7) ultima linha com 10 a 15 hashtags em portugues (amplas, nichadas, juridicas e \
locais de Juiz de Fora/MG). Nao coloque link nem endereco de site na legenda. Nunca inclua numero \
de registro na OAB na legenda.

SLIDES: slide 1 e a capa (headline forte e especifico, ate 8 palavras, body vazio). Slides do \
meio: headline curto + body de 1-2 frases (ate 220 caracteres), UMA ideia concreta por slide. \
Ultimo slide: fechamento que prioriza salvar/compartilhar/comentar antes do convite a contato, \
com body de no maximo 160 caracteres -- a parte de baixo desse slide e ocupada automaticamente \
pelo QR Code do artigo e pela assinatura, entao nao escreva no slide "escaneie o QR Code" nem \
repita a assinatura.
{feedback_block}
Formato de resposta (JSON estrito, sem markdown):
{{"topic": "tema em poucas palavras", "slides": [{{"headline": "...", "body": "..."}}], "caption": "..."}}

ARTIGO -- "{article_title}":
{article_text}"""

FEEDBACK_BLOCK = """
VERSAO ANTERIOR (reprovada pelo revisor):
{previous}

{feedback}
"""


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def account_for_post(post: dict, cfg: dict) -> str | None:
    title = post["title"].lower()
    for rule in cfg["category_map"]:
        if not set(rule["categories"]) & set(post["categories"]):
            continue
        keywords = rule.get("title_keywords")
        if keywords and not any(k.lower() in title for k in keywords):
            continue
        return rule["account"]
    return None


def write_carousel(account, post, article_text, model, previous=None, feedback=""):
    author_line, signing_instruction = signing_rules(account)
    feedback_block = ""
    if previous:
        feedback_block = FEEDBACK_BLOCK.format(
            previous=json.dumps(previous, ensure_ascii=False, indent=2), feedback=feedback
        )
    prompt = WRITER_PROMPT_TEMPLATE.format(
        page_name=account["page_name"],
        ig_username=account["ig_username"],
        practice_area=account["practice_area"],
        author_line=author_line,
        signing_instruction=signing_instruction,
        feedback_block=feedback_block,
        article_title=post["title"],
        article_text=article_text,
    )
    content = parse_json_reply(_run_claude_code(SYSTEM_PROMPT, prompt, timeout=300, model=model))
    if not 5 <= len(content.get("slides", [])) <= 10:
        raise ValueError(f"Redator devolveu {len(content.get('slides', []))} slides (esperado 8 a 10)")
    content["qr_url"] = post["link"]
    return content


def verify_qr(image_path: str, expected_url: str):
    import cv2

    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(image_path))
    if decoded != expected_url:
        raise RuntimeError(f"QR Code do ultimo slide leva a '{decoded}', esperado '{expected_url}'")


def open_issue(title: str, body: str):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print(f"[aviso] sem GITHUB_TOKEN/GITHUB_REPOSITORY -- issue nao criada: {title}")
        return None
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body},
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json()["html_url"]
    print(f"[issue] {url}")
    return url


def review_markdown(review: dict) -> str:
    lines = [f"**Parecer do revisor:** {'APROVADO' if review.get('aprovado') else 'REPROVADO'} "
             f"(nota {review.get('nota', '?')}/10)", "", review.get("resumo", "")]
    if review.get("problemas"):
        lines += ["", "| Onde | Gravidade | Problema | Correção sugerida |", "|---|---|---|---|"]
        for p in review["problemas"]:
            cells = [str(p.get(k, "")).replace("|", "/").replace("\n", " ")
                     for k in ("onde", "gravidade", "descricao", "correcao")]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def draft_issue_body(draft: dict, reason: str) -> str:
    images = "\n".join(f"![slide {i}]({u})" for i, u in enumerate(draft["image_urls"], 1))
    return f"""{reason}

**Conta:** {draft['page_name']} (@{draft['ig_username']})
**Artigo:** [{draft['source_post']['title']}]({draft['source_post']['link']})

{review_markdown(draft['review'])}

### Como decidir
- **Publicar:** aba *Actions* → **Publicar rascunho aprovado no Instagram** → *Run workflow* → conta `{draft['account_key']}`.
- **Descartar:** aba *Actions* → **Descartar rascunho pendente** → *Run workflow* → conta `{draft['account_key']}`.

Enquanto este rascunho estiver pendente, nenhum outro carrossel desta conta é gerado.

### Legenda do Instagram
```
{draft['caption']}
```

### Legenda do Facebook
```
{facebook_caption(draft)}
```

### Slides
{images}
"""


def process_post(post, account, cfg, mode) -> str:
    key = account["key"]
    print(f"\n[{key}] artigo: {post['title']}")
    article_text = fetch_article_text(post["link"])

    content = write_carousel(account, post, article_text, cfg["writer_model"])
    rounds = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for round_no in range(cfg["review_max_rounds"] + 1):
            out_dir = os.path.join(tmp_dir, f"v{round_no}")
            os.makedirs(out_dir)
            image_paths = render_carousel(content, account, out_dir)
            verify_qr(image_paths[-1], post["link"])
            review = review_carousel(account, post, article_text, content, image_paths, cfg["reviewer_model"])
            rounds.append(review)
            print(f"[{key}] revisao {round_no + 1}: {'aprovado' if review['aprovado'] else 'reprovado'} -- {review.get('resumo', '')}")
            if review["aprovado"] or round_no == cfg["review_max_rounds"]:
                break
            content = write_carousel(account, post, article_text, cfg["writer_model"],
                                     previous=content, feedback=format_feedback(review))

        print(f"[{key}] subindo imagens no Cloudinary...")
        image_urls = [upload_to_cloudinary(p) for p in image_paths]

    draft = {
        "account_key": key,
        "page_name": account["page_name"],
        "ig_username": account["ig_username"],
        "topic": content.get("topic", post["title"]),
        "slides": content["slides"],
        "caption": content["caption"],
        "qr_url": post["link"],
        "image_urls": image_urls,
        "generated_at": now_iso(),
        "origin": "blog",
        "mode": mode,
        "source_post": {k: post[k] for k in ("title", "link", "categories")},
        "review": review,
        "review_rounds": len(rounds),
    }
    save_json(os.path.join(PENDING_DIR, f"{key}.json"), draft)

    if review["aprovado"] and mode == "automatico":
        from publish_draft import run as publish_pending

        published = publish_pending(key)
        if published.get("facebook_error"):
            open_issue(f"[{key}] Publicado no Instagram, mas falhou no Facebook",
                       f"Artigo: {post['link']}\n\nErro do Facebook:\n```\n{published['facebook_error']}\n```")
        return "publicado"

    reason = ("Modo sombra: o revisor **aprovou**, mas a publicação aguarda a sua confirmação."
              if review["aprovado"] else
              f"O revisor **reprovou** o carrossel depois de {len(rounds)} rodada(s). Nada foi publicado.")
    open_issue(f"[{key}] Carrossel aguardando decisão: {draft['topic']}", draft_issue_body(draft, reason))
    return "aguardando_aprovacao" if review["aprovado"] else "reprovado"


def main():
    cfg = load_json(PIPELINE_CONFIG)
    accounts = {a["key"]: a for a in load_json(ACCOUNTS_CONFIG)["accounts"]}
    state = load_json(STATE_PATH, {"posts": {}})
    posts_state = state["posts"]
    feed = fetch_feed(cfg["feed_url"])
    print(f"feed: {len(feed)} artigos")

    if "--baseline" in sys.argv:
        for post in feed:
            posts_state.setdefault(post["link"], {"status": "baseline", "title": post["title"], "at": now_iso()})
        save_json(STATE_PATH, state)
        print(f"baseline gravado: {len(posts_state)} artigos marcados como ja vistos")
        return 0

    if os.path.exists(PAUSE_FILE):
        print("Arquivo PAUSAR encontrado -- nada sera gerado ou publicado.")
        return 0

    forced = (os.environ.get("FORCE_POST_URL") or "").strip()
    if forced and not any(p["link"] == forced for p in feed):
        raise SystemExit(f"FORCE_POST_URL nao esta entre os {len(feed)} artigos mais recentes do feed: {forced}")

    queue: dict[str, list[dict]] = {}
    for post in reversed(feed):
        if forced and post["link"] != forced:
            continue
        entry = posts_state.get(post["link"])
        retry = entry and entry["status"] == "erro" and entry.get("attempts", 0) < MAX_ATTEMPTS
        if entry and not retry and not forced:
            continue
        key = account_for_post(post, cfg)
        if key is None:
            posts_state[post["link"]] = {"status": "ignorado", "title": post["title"],
                                         "categories": post["categories"], "at": now_iso()}
            continue
        account = accounts.get(key)
        if not account or not account.get("enabled", True):
            posts_state[post["link"]] = {"status": "sem_conta", "account": key, "title": post["title"], "at": now_iso()}
            continue
        queue.setdefault(key, []).append(post)

    failures = 0
    for key, posts in queue.items():
        if os.path.exists(os.path.join(PENDING_DIR, f"{key}.json")):
            print(f"[{key}] ja existe rascunho pendente de decisao -- {len(posts)} artigo(s) aguardam a proxima execucao")
            continue
        for post in posts[: cfg["max_per_account_per_run"]]:
            previous = posts_state.get(post["link"]) or {}
            try:
                status = process_post(post, accounts[key], cfg, cfg["mode"])
                posts_state[post["link"]] = {"status": status, "account": key, "title": post["title"], "at": now_iso()}
            except Exception as e:
                failures += 1
                attempts = previous.get("attempts", 0) + 1 if previous.get("status") == "erro" else 1
                traceback.print_exc()
                posts_state[post["link"]] = {"status": "erro", "account": key, "title": post["title"],
                                             "attempts": attempts, "error": str(e)[:500], "at": now_iso()}
                if attempts >= MAX_ATTEMPTS:
                    open_issue(f"[{key}] Falha ao gerar carrossel do artigo (desisti após {attempts} tentativas)",
                               f"Artigo: {post['link']}\n\nÚltimo erro:\n```\n{str(e)[:1500]}\n```")
            save_json(STATE_PATH, state)

    save_json(STATE_PATH, state)
    if not queue:
        print("Nenhum artigo novo para processar.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
