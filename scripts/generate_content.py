"""
Gera o conteudo textual de um carrossel juridico usando o Claude Code CLI (autenticado
com a assinatura Pro/Max/Team via CLAUDE_CODE_OAUTH_TOKEN -- sem custo por token de API),
seguindo o estilo da casa e as regras de publicidade da OAB (Provimento 205/2021).

Saida: dict com:
  - topic: tema escolhido do carrossel
  - slides: lista de dicts {"headline": str, "body": str} (uma por slide)
  - caption: legenda para o post (com CTA sobrio e hashtags)
"""
import json
import os
import random
import subprocess

SYSTEM_PROMPT = """Voce e o redator de conteudo para Instagram do escritorio Rafael Rocha e Santos \
Advocacia (Juiz de Fora - MG). Voce escreve carrosseis educativos e sobrios que seguem \
RIGOROSAMENTE as regras de publicidade da advocacia (Estatuto da OAB, Codigo de Etica, \
Provimento 205/2021 do CFOAB):

PODE: informar e educar sobre direitos, leis e prazos; mencionar areas de atuacao; usar \
exemplos hipoteticos rotulados como ilustracao; convidar para consulta "sem compromisso"; \
usar linguagem de possibilidade ("pode ter direito", "e possivel pleitear").

NAO PODE: prometer ou garantir resultado ("garantimos", "voce vai ganhar"); usar \
sensacionalismo, "promocao", "oferta", urgencia artificial de venda, superlativos vazios \
("o melhor advogado"); comparar-se a outros escritorios; divulgar valores de honorarios; \
usar casos reais identificaveis; garantir prazos como certos.

Tom: tecnico mas acolhedor. O leitor geralmente chega com medo, duvida ou prejuizo \
financeiro. Informe com autoridade, acolha a angustia, mostre que ha um caminho legal \
seguro -- sem forcar a venda.

Responda SEMPRE em JSON valido, sem markdown, sem texto fora do JSON."""

USER_PROMPT_TEMPLATE = """Crie um carrossel de Instagram (5 a 7 slides) sobre um dos temas abaixo \
para a area de atuacao "{practice_area}" do escritorio.

Temas possiveis (escolha um, de preferencia um pouco diferente dos ultimos usados): {topics}

Autor que assina: {author_name}, {author_title} - {author_oab}

Formato de resposta (JSON estrito):
{{
  "topic": "tema escolhido em poucas palavras",
  "slides": [
    {{"headline": "frase de ate 8 palavras, gancho forte para o slide 1 (capa)", "body": ""}},
    {{"headline": "titulo curto do ponto 2", "body": "1-2 frases explicando, ate 220 caracteres"}},
    {{"headline": "titulo curto do ponto 3", "body": "1-2 frases explicando, ate 220 caracteres"}},
    {{"headline": "titulo curto do ponto 4", "body": "1-2 frases explicando, ate 220 caracteres"}},
    {{"headline": "Vale a pena conversar com um advogado?", "body": "fechamento acolhedor + convite sutil para consulta, sem prometer resultado"}}
  ],
  "caption": "legenda para o post, 2-4 frases + convite para DM/WhatsApp sem ser vendedor + 5 a 8 hashtags relevantes em portugues no final"
}}

Slide 1 e so capa (headline forte, body vazio). Os demais tem headline curto + body explicativo. \
Nunca prometa resultado, nunca use sensacionalismo. Assine o convite final com o nome do autor."""


def _run_claude_code(system_prompt: str, user_prompt: str) -> str:
    """
    Chama o Claude Code CLI em modo nao interativo (-p) para gerar texto.
    Autentica via CLAUDE_CODE_OAUTH_TOKEN (assinatura Pro/Max/Team/Enterprise),
    gerado uma vez com `claude setup-token` -- sem custo de API por token.
    Nao usa --bare (bare mode ignora OAuth e exige ANTHROPIC_API_KEY).
    """
    cmd = [
        "claude",
        "-p", user_prompt,
        "--append-system-prompt", system_prompt,
        "--output-format", "json",
        "--model", "claude-sonnet-5",
        "--max-turns", "1",
        "--allowedTools", "",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        env=os.environ,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p falhou (codigo {result.returncode}): {result.stderr[:2000]}")

    payload = json.loads(result.stdout)
    if payload.get("is_error"):
        raise RuntimeError(f"claude -p retornou erro: {payload}")
    return payload["result"]


def generate_carousel_content(account: dict, recent_topics=None) -> dict:
    topics = account["topics"]
    if recent_topics:
        topics = sorted(topics, key=lambda t: t in recent_topics)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        practice_area=account["practice_area"],
        topics=", ".join(topics),
        author_name=account["author_name"],
        author_title=account["author_title"],
        author_oab=account["author_oab"],
    )

    text = _run_claude_code(SYSTEM_PROMPT, user_prompt).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text)
    return data


if __name__ == "__main__":
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "accounts.json")
    with open(cfg_path, encoding="utf-8") as f:
        accounts = json.load(f)["accounts"]
    account = random.choice(accounts)
    result = generate_carousel_content(account)
    print(json.dumps(result, ensure_ascii=False, indent=2))
