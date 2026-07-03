"""
Gera um RASCUNHO de carrossel (conteudo + imagens ja hospedadas no Cloudinary) e salva
em drafts/pending/{account_key}.json -- SEM publicar no Instagram.

A publicacao so acontece depois que Rafael revisar o rascunho (imagens + legenda) e
aprovar, o que dispara o workflow "publish_draft.yml" separadamente.

Se a variavel de ambiente EXTRA_INSTRUCTION estiver definida (pedido de alteracao feito
por um revisor humano sobre um rascunho ja existente), este script:
  - reaproveita o mesmo tema do rascunho anterior (nao sorteia um tema novo)
  - aplica o feedback na nova geracao de conteudo
"""
import json
import os
import tempfile
from datetime import datetime, timezone

from generate_content import generate_carousel_content
from publish_instagram import upload_to_cloudinary
from render_carousel import render_carousel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "accounts.json")
DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts", "pending")


def load_accounts() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["accounts"]


def _existing_draft(account_key: str) -> dict | None:
    path = os.path.join(DRAFTS_DIR, f"{account_key}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def run(account_key: str, extra_instruction: str = ""):
    accounts = load_accounts()
    account = next((a for a in accounts if a["key"] == account_key), None)
    if account is None:
        raise SystemExit(f"Conta desconhecida: {account_key}")

    forced_topic = None
    previous = _existing_draft(account_key)
    if extra_instruction.strip():
        if previous:
            forced_topic = previous.get("topic")
            print(f"[{account_key}] pedido de alteracao recebido, mantendo tema: {forced_topic}")
        else:
            print(f"[{account_key}] pedido de alteracao recebido, mas nao havia rascunho anterior -- sorteando tema novo mesmo assim.")
    elif previous:
        print(f"[{account_key}] AVISO: ja existia um rascunho pendente (tema '{previous.get('topic')}') ainda nao aprovado -- ele sera substituido por este novo.")

    print(f"[{account_key}] gerando conteudo...")
    content = generate_carousel_content(account, forced_topic=forced_topic, extra_instruction=extra_instruction)
    print(f"[{account_key}] tema: {content['topic']}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"[{account_key}] renderizando slides...")
        image_paths = render_carousel(content, account, tmp_dir)

        print(f"[{account_key}] subindo imagens no Cloudinary...")
        image_urls = [upload_to_cloudinary(p) for p in image_paths]

    draft = {
        "account_key": account_key,
        "page_name": account["page_name"],
        "ig_username": account["ig_username"],
        "topic": content["topic"],
        "slides": content["slides"],
        "caption": content["caption"],
        "image_urls": image_urls,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": (previous.get("revision", 0) + 1) if (previous and extra_instruction.strip()) else 1,
    }

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    out_path = os.path.join(DRAFTS_DIR, f"{account_key}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)

    print(f"[{account_key}] rascunho salvo em {out_path} (revisao {draft['revision']})")
    print(f"[{account_key}] imagens: " + " | ".join(image_urls))


if __name__ == "__main__":
    key = os.environ.get("ACCOUNT_KEY")
    if not key:
        raise SystemExit("Defina ACCOUNT_KEY (env var).")
    extra = os.environ.get("EXTRA_INSTRUCTION", "")
    run(key, extra_instruction=extra)
