"""
Orquestra o pipeline completo para UMA conta por execução:
1. Escolhe a conta da vez (rotação round-robin salva em state/last_index.txt)
2. Gera o conteúdo do carrossel (Claude)
3. Renderiza os slides (Pillow)
4. Sobe as imagens (Cloudinary) e publica no Instagram (Graph API)

Cada conta publica na sua própria cadência: o workflow do GitHub Actions roda este
script uma vez por conta a cada execução agendada (ver .github/workflows/publish.yml),
passando ACCOUNT_KEY como variável de ambiente.
"""
import json
import os
import sys
import tempfile

from generate_content import generate_carousel_content
from publish_instagram import publish_from_local_files
from render_carousel import render_carousel

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "accounts.json")


def load_accounts() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["accounts"]


def load_secrets_for_account(account_key: str) -> dict:
    """
    Lê o secret INSTAGRAM_ACCOUNTS_JSON (definido no GitHub Actions), que é uma lista
    de objetos {"key": ..., "page_access_token": ..., "ig_business_id": ...}, e retorna
    os dados da conta pedida.
    """
    raw = os.environ["INSTAGRAM_ACCOUNTS_JSON"]
    data = json.loads(raw)
    for entry in data:
        if entry["key"] == account_key:
            return entry
    raise KeyError(f"Conta '{account_key}' não encontrada em INSTAGRAM_ACCOUNTS_JSON")


def run(account_key: str):
    accounts = load_accounts()
    account = next((a for a in accounts if a["key"] == account_key), None)
    if account is None:
        raise SystemExit(f"Conta desconhecida: {account_key}")

    secrets = load_secrets_for_account(account_key)

    print(f"[{account_key}] gerando conteúdo...")
    content = generate_carousel_content(account)
    print(f"[{account_key}] tema: {content['topic']}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"[{account_key}] renderizando slides...")
        image_paths = render_carousel(content, account, tmp_dir)

        print(f"[{account_key}] publicando no Instagram...")
        media_id = publish_from_local_files(
            ig_business_id=secrets["ig_business_id"],
            access_token=secrets["page_access_token"],
            image_paths=image_paths,
            caption=content["caption"],
        )
        print(f"[{account_key}] publicado! media_id={media_id}")


if __name__ == "__main__":
    key = os.environ.get("ACCOUNT_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not key:
        raise SystemExit("Defina ACCOUNT_KEY (env var) ou passe a chave da conta como argumento.")
    run(key)
