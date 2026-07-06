"""
Aplica edicoes manuais feitas pelo revisor humano (Rafael) a um rascunho pendente,
usando o texto exatamente como ele escreveu -- SEM chamar o Claude Code CLI e SEM
qualquer reescrita por IA. Apenas re-renderiza as imagens com o novo texto e re-sobe
no Cloudinary, atualizando o rascunho em drafts/pending/{account_key}.json.
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


def run(account_key: str, edited_content: dict):
    accounts = load_accounts()
    account = next((a for a in accounts if a["key"] == account_key), None)
    if account is None:
        raise SystemExit(f"Conta desconhecida: {account_key}")

    draft_path = os.path.join(DRAFTS_DIR, f"{account_key}.json")
    if not os.path.exists(draft_path):
        raise SystemExit(f"Nao ha rascunho pendente para {account_key}")

    with open(draft_path, encoding="utf-8") as f:
        draft = json.load(f)

    new_slides = edited_content["slides"]
    new_caption = edited_content["caption"]

    if len(new_slides) != len(draft["slides"]):
        raise SystemExit(
            f"Numero de slides mudou ({len(draft['slides'])} -> {len(new_slides)}); "
            "esta ferramenta so aceita editar o texto dos slides existentes, nao adicionar/remover slides."
        )

    content = {"topic": draft["topic"], "slides": new_slides, "caption": new_caption}

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"[{account_key}] renderizando slides com o texto editado...")
        image_paths = render_carousel(content, account, tmp_dir)

        print(f"[{account_key}] subindo imagens no Cloudinary...")
        image_urls = [upload_to_cloudinary(p) for p in image_paths]

    draft["slides"] = new_slides
    draft["caption"] = new_caption
    draft["image_urls"] = image_urls
    draft["revision"] = draft.get("revision", 1) + 1
    draft["manually_edited_at"] = datetime.now(timezone.utc).isoformat()

    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)

    print(f"[{account_key}] rascunho atualizado (revisao {draft['revision']})")
    print(f"[{account_key}] imagens: " + " | ".join(image_urls))


if __name__ == "__main__":
    key = os.environ.get("ACCOUNT_KEY")
    if not key:
        raise SystemExit("Defina ACCOUNT_KEY (env var).")
    raw = os.environ.get("EDITED_CONTENT")
    if not raw:
        raise SystemExit("Defina EDITED_CONTENT (env var, JSON).")
    edited = json.loads(raw)
    run(key, edited)
