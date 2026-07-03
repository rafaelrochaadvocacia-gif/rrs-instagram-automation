"""
Publica no Instagram um rascunho ja aprovado por Rafael (drafts/pending/{account_key}.json).

As imagens ja estao hospedadas no Cloudinary (feito na etapa de geracao do rascunho),
entao aqui so criamos os containers do carrossel na Graph API e publicamos.

Depois de publicar com sucesso, move o rascunho de drafts/pending/ para
drafts/published/ (com timestamp), para manter historico e liberar o slot "pendente"
da conta para o proximo carrossel.
"""
import json
import os
import shutil
from datetime import datetime, timezone

from publish_instagram import publish_carousel

DRAFTS_PENDING_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts", "pending")
DRAFTS_PUBLISHED_DIR = os.path.join(os.path.dirname(__file__), "..", "drafts", "published")


def load_secrets_for_account(account_key: str) -> dict:
    raw = os.environ["INSTAGRAM_ACCOUNTS_JSON"]
    data = json.loads(raw)
    for entry in data:
        if entry["key"] == account_key:
            return entry
    raise KeyError(f"Conta '{account_key}' nao encontrada em INSTAGRAM_ACCOUNTS_JSON")


def run(account_key: str):
    draft_path = os.path.join(DRAFTS_PENDING_DIR, f"{account_key}.json")
    if not os.path.exists(draft_path):
        raise SystemExit(f"Nao ha rascunho pendente para '{account_key}' em {draft_path}")

    with open(draft_path, encoding="utf-8") as f:
        draft = json.load(f)

    secrets = load_secrets_for_account(account_key)

    print(f"[{account_key}] publicando carrossel aprovado -- tema: {draft['topic']}")
    media_id = publish_carousel(
        ig_business_id=secrets["ig_business_id"],
        access_token=secrets["page_access_token"],
        image_urls=draft["image_urls"],
        caption=draft["caption"],
    )
    print(f"[{account_key}] publicado! media_id={media_id}")

    os.makedirs(DRAFTS_PUBLISHED_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(DRAFTS_PUBLISHED_DIR, f"{account_key}_{stamp}.json")
    draft["published_at"] = datetime.now(timezone.utc).isoformat()
    draft["media_id"] = media_id
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    os.remove(draft_path)
    print(f"[{account_key}] rascunho movido para {dest}")


if __name__ == "__main__":
    key = os.environ.get("ACCOUNT_KEY")
    if not key:
        raise SystemExit("Defina ACCOUNT_KEY (env var).")
    run(key)
