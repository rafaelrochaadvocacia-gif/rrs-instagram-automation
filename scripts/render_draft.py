"""
Cria o rascunho VISUAL (imagens ja renderizadas e hospedadas no Cloudinary) a partir de
um carrossel cujo TEXTO (topico, slides e legenda) ja foi escrito pelo Claude no Cowork
e aprovado -- com ou sem edicoes -- por Rafael, diretamente no chat.

Este script e a segunda etapa do fluxo em duas etapas pedido por Rafael:
  1) O texto e pesquisado e escrito pelo Claude no Cowork (sem nenhuma chamada de IA
     nesta etapa do pipeline em si -- a copy ja chega pronta e aprovada).
  2) Este script renderiza as imagens com esse texto exatamente como aprovado (nenhuma
     reescrita, nenhuma chamada a IA aqui -- so renderizacao deterministica via PIL) e
     salva o rascunho visual completo em drafts/pending/{account_key}.json, no MESMO
     formato ja usado por edit_draft.yml e publish_draft.yml. Ou seja, a partir daqui o
     restante do pipeline (segunda revisao com imagens, e publicacao) continua
     funcionando exatamente como antes, sem nenhuma mudanca.

Espera receber em APPROVED_CONTENT (JSON) os campos: topic, slides (lista de
{headline, body}) e caption -- exatamente o que foi aprovado no chat.
"""
import json
import os
import tempfile
from datetime import datetime, timezone

from publish_instagram import upload_to_cloudinary
from render_carousel import render_carousel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "accounts.json")
DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts", "pending")


def load_accounts() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["accounts"]


def run(account_key: str, approved_content: dict):
    accounts = load_accounts()
    account = next((a for a in accounts if a["key"] == account_key), None)
    if account is None:
        raise SystemExit(f"Conta desconhecida: {account_key}")

    topic = approved_content["topic"]
    slides = approved_content["slides"]
    caption = approved_content["caption"]

    content = {"topic": topic, "slides": slides, "caption": caption}

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"[{account_key}] renderizando slides com o texto aprovado por Rafael...")
        image_paths = render_carousel(content, account, tmp_dir)

        print(f"[{account_key}] subindo imagens no Cloudinary...")
        image_urls = [upload_to_cloudinary(p) for p in image_paths]

    draft = {
        "account_key": account_key,
        "page_name": account["page_name"],
        "ig_username": account["ig_username"],
        "topic": topic,
        "slides": slides,
        "caption": caption,
        "image_urls": image_urls,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": 1,
    }

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    out_path = os.path.join(DRAFTS_DIR, f"{account_key}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)

    print(f"[{account_key}] rascunho visual salvo em {out_path}")
    print(f"[{account_key}] imagens: " + " | ".join(image_urls))


if __name__ == "__main__":
    key = os.environ.get("ACCOUNT_KEY")
    if not key:
        raise SystemExit("Defina ACCOUNT_KEY (env var).")
    raw = os.environ.get("APPROVED_CONTENT")
    if not raw:
        raise SystemExit("Defina APPROVED_CONTENT (env var, JSON).")
    approved = json.loads(raw)
    run(key, approved)
