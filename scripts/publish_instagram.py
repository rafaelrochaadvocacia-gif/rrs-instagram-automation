"""
Sobe as imagens do carrossel no Cloudinary (para obter URLs publicas) e publica o
carrossel na conta do Instagram correspondente via Instagram Graph API (Facebook Login
for Business), usando um Page Access Token obtido na hora a partir do token permanente
do System User. Tambem publica o mesmo carrossel como post de multiplas fotos na
Pagina do Facebook vinculada, usando o mesmo Page Access Token.
"""
import json
import os
import time

import requests

GRAPH_API_VERSION = "v25.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def refresh_page_access_token(page_id: str, system_user_token: str) -> str:
    """Troca o token do System User (permanente, nunca expira) por um Page Access
    Token novo. Tokens de Pagina derivados ficam com validade curta (poucas horas)
    mesmo vindo de um System User permanente -- por isso buscamos um novo a cada
    publicacao, em vez de reutilizar um token de pagina salvo previamente."""
    resp = requests.get(
        f"{GRAPH_API_BASE}/{page_id}",
        params={"fields": "access_token", "access_token": system_user_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def upload_to_cloudinary(image_path: str) -> str:
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]

    import hashlib
    import random as _random

    timestamp = int(time.time())
    params_to_sign = f"timestamp={timestamp}"
    signature = hashlib.sha1(f"{params_to_sign}{api_secret}".encode()).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            files={"file": f},
            data={
                "api_key": api_key,
                "timestamp": timestamp,
                "signature": signature,
            },
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["secure_url"]

def _create_media_container(ig_business_id: str, image_url: str, access_token: str, is_carousel_item: bool) -> str:
    url = f"{GRAPH_API_BASE}/{ig_business_id}/media"
    payload = {
        "image_url": image_url,
        "access_token": access_token,
    }
    if is_carousel_item:
        payload["is_carousel_item"] = "true"
    resp = requests.post(url, data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]

def _wait_until_ready(container_id: str, access_token: str, timeout_s: int = 120):
    url = f"{GRAPH_API_BASE}/{container_id}"
    start = time.time()
    while time.time() - start < timeout_s:
        resp = requests.get(url, params={"fields": "status_code", "access_token": access_token}, timeout=30)
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} falhou ao processar")
        time.sleep(3)
    raise TimeoutError(f"Container {container_id} nao ficou pronto em {timeout_s}s")

def publish_carousel(ig_business_id: str, access_token: str, image_urls: list[str], caption: str) -> str:
    """Cria os containers de cada imagem, monta o carrossel e publica. Retorna o media id publicado."""
    child_ids = []
    for image_url in image_urls:
        child_id = _create_media_container(ig_business_id, image_url, access_token, is_carousel_item=True)
        child_ids.append(child_id)

    for child_id in child_ids:
        _wait_until_ready(child_id, access_token)

    carousel_url = f"{GRAPH_API_BASE}/{ig_business_id}/media"
    resp = requests.post(
        carousel_url,
        data={
            "media_type": "CAROUSEL",
            "caption": caption,
            "children": ",".join(child_ids),
            "access_token": access_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    carousel_container_id = resp.json()["id"]

    _wait_until_ready(carousel_container_id, access_token)

    publish_url = f"{GRAPH_API_BASE}/{ig_business_id}/media_publish"
    resp = requests.post(
        publish_url,
        data={"creation_id": carousel_container_id, "access_token": access_token},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]

def publish_from_local_files(ig_business_id: str, access_token: str, image_paths: list[str], caption: str) -> str:
    """Sobe as imagens locais no Cloudinary e publica o carrossel."""
    image_urls = [upload_to_cloudinary(p) for p in image_paths]
    return publish_carousel(ig_business_id, access_token, image_urls, caption)

def _get_page_id(access_token: str) -> str:
    """Descobre o ID da Pagina do Facebook a partir do proprio Page Access Token
    (uma Page Access Token, ao chamar /me, retorna os dados da propria Pagina)."""
    resp = requests.get(f"{GRAPH_API_BASE}/me", params={"access_token": access_token}, timeout=30)
    resp.raise_for_status()
    return resp.json()["id"]

def publish_facebook_carousel(access_token: str, image_urls: list[str], caption: str) -> str:
    """Publica o mesmo carrossel como um post de multiplas fotos na Pagina do Facebook
    vinculada ao Page Access Token. Retorna o ID do post publicado.

    Fluxo da Graph API: sobe cada foto sem publicar (published=false) para obter um
    media_fbid, depois cria um post no feed da Pagina anexando todos os media_fbid.
    """
    page_id = _get_page_id(access_token)

    media_ids = []
    for image_url in image_urls:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/photos",
            data={
                "url": image_url,
                "published": "false",
                "access_token": access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        media_ids.append(resp.json()["id"])

    attached_media = json.dumps([{"media_fbid": media_id} for media_id in media_ids])
    resp = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/feed",
        data={
            "message": caption,
            "attached_media": attached_media,
            "access_token": access_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]
"""
Sobe as imagens do carrossel no Cloudinary (para obter URLs públicas) e publica o
carrossel na conta do Instagram correspondente via Instagram Graph API (Facebook Login
for Business), usando o Page Access Token de longa duração da conta. Também publica o
mesmo carrossel como post de múltiplas fotos na Página do Facebook vinculada, usando o
mesmo Page Access Token (uma Page Access Token já autoriza ações na própria Página).
"""
import json
import os
import time

import requests

GRAPH_API_VERSION = "v25.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def upload_to_cloudinary(image_path: str) -> str:
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]

    import hashlib
    import random as _random

    timestamp = int(time.time())
    # Assinatura exigida pelo upload autenticado do Cloudinary
    params_to_sign = f"timestamp={timestamp}"
    signature = hashlib.sha1(f"{params_to_sign}{api_secret}".encode()).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            files={"file": f},
            data={
                "api_key": api_key,
                "timestamp": timestamp,
                "signature": signature,
            },
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()["secure_url"]


def _create_media_container(ig_business_id: str, image_url: str, access_token: str, is_carousel_item: bool) -> str:
    url = f"{GRAPH_API_BASE}/{ig_business_id}/media"
    payload = {
        "image_url": image_url,
        "access_token": access_token,
    }
    if is_carousel_item:
        payload["is_carousel_item"] = "true"
    resp = requests.post(url, data=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["id"]


def _wait_until_ready(container_id: str, access_token: str, timeout_s: int = 120):
    url = f"{GRAPH_API_BASE}/{container_id}"
    start = time.time()
    while time.time() - start < timeout_s:
        resp = requests.get(url, params={"fields": "status_code", "access_token": access_token}, timeout=30)
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} falhou ao processar")
        time.sleep(3)
    raise TimeoutError(f"Container {container_id} não ficou pronto em {timeout_s}s")


def publish_carousel(ig_business_id: str, access_token: str, image_urls: list[str], caption: str) -> str:
    """Cria os containers de cada imagem, monta o carrossel e publica. Retorna o media id publicado."""
    child_ids = []
    for image_url in image_urls:
        child_id = _create_media_container(ig_business_id, image_url, access_token, is_carousel_item=True)
        child_ids.append(child_id)

    for child_id in child_ids:
        _wait_until_ready(child_id, access_token)

    carousel_url = f"{GRAPH_API_BASE}/{ig_business_id}/media"
    resp = requests.post(
        carousel_url,
        data={
            "media_type": "CAROUSEL",
            "caption": caption,
            "children": ",".join(child_ids),
            "access_token": access_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    carousel_container_id = resp.json()["id"]

    _wait_until_ready(carousel_container_id, access_token)

    publish_url = f"{GRAPH_API_BASE}/{ig_business_id}/media_publish"
    resp = requests.post(
        publish_url,
        data={"creation_id": carousel_container_id, "access_token": access_token},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_from_local_files(ig_business_id: str, access_token: str, image_paths: list[str], caption: str) -> str:
    """Sobe as imagens locais no Cloudinary e publica o carrossel."""
    image_urls = [upload_to_cloudinary(p) for p in image_paths]
    return publish_carousel(ig_business_id, access_token, image_urls, caption)


def _get_page_id(access_token: str) -> str:
    """Descobre o ID da Página do Facebook a partir do proprio Page Access Token
    (uma Page Access Token, ao chamar /me, retorna os dados da propria Pagina)."""
    resp = requests.get(f"{GRAPH_API_BASE}/me", params={"access_token": access_token}, timeout=30)
    resp.raise_for_status()
    return resp.json()["id"]


def publish_facebook_carousel(access_token: str, image_urls: list[str], caption: str) -> str:
    """Publica o mesmo carrossel como um post de multiplas fotos na Pagina do Facebook
    vinculada ao Page Access Token. Retorna o ID do post publicado.

    Fluxo da Graph API: sobe cada foto sem publicar (published=false) para obter um
    media_fbid, depois cria um post no feed da Pagina anexando todos os media_fbid.
    """
    page_id = _get_page_id(access_token)

    media_ids = []
    for image_url in image_urls:
        resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/photos",
            data={
                "url": image_url,
                "published": "false",
                "access_token": access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        media_ids.append(resp.json()["id"])

    attached_media = json.dumps([{"media_fbid": media_id} for media_id in media_ids])
    resp = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/feed",
        data={
            "message": caption,
            "attached_media": attached_media,
            "access_token": access_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]
