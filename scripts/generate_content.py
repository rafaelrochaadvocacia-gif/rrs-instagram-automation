"""
Gera o conteudo textual de um carrossel juridico usando o Claude Code CLI (autenticado
com a assinatura Pro/Max/Team via CLAUDE_CODE_OAUTH_TOKEN -- sem custo por token de API),
seguindo o estilo da casa e as regras de publicidade da OAB (Provimento 205/2021).

O processo tem DUAS etapas:
  1. Pesquisa: o Claude pesquisa na web (WebSearch/WebFetch) as regras juridicas atuais
     do tema escolhido, com fontes, para evitar publicar informacao juridica incorreta
     ou desatualizada (ex.: exigencias documentais que na verdade nao sao obrigatorias).
  2. Redacao: o carrossel e escrito com base SOMENTE no que a pesquisa confirmou.

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

PRECISAO JURIDICA (critico -- erros aqui viram desinformacao publica com o nome do escritorio): \
nunca afirme um requisito, documento ou procedimento como obrigatorio se isso nao estiver \
confirmado na pesquisa fornecida no prompt. Em caso de duvida, use linguagem de possibilidade \
("normalmente", "pode ser necessario", "em geral") em vez de afirmar como regra absoluta. \
Exemplo de erro real ja cometido e que NUNCA deve se repetir: para isencao de Imposto de Renda \
por doenca grave, NAO e obrigatorio laudo medico oficial/pericial -- um laudo de medico \
particular tambem e aceito para instruir o pedido. Nao presuma exigencias assim sem checar.

Tom: tecnico mas acolhedor. O leitor geralmente chega com medo, duvida ou prejuizo \
financeiro. Informe com autoridade, acolha a angustia, mostre que ha um caminho legal \
seguro -- sem forcar a venda.

Responda SEMPRE em JSON valido, sem markdown, sem texto fora do JSON."""

RESEARCH_SYSTEM_PROMPT = """Voce e um pesquisador juridico que apura fatos para o escritorio Rafael \
Rocha e Santos Advocacia (Juiz de Fora - MG) antes da publicacao de conteudo educativo no Instagram. \
Sua unica funcao e pesquisar na web e resumir, de forma factual e com fontes, as regras juridicas \
atuais sobre o tema pedido -- para evitar que o escritorio publique informacao incorreta ou \
desatualizada com seu nome.

Regras:
- Pesquise em fontes oficiais e confiaveis: legislacao (planalto.gov.br), Receita Federal (gov.br), \
INSS (gov.br), STJ, STF, Banco Central, Codigo de Defesa do Consumidor, e sites juridicos \
reconhecidos (JusBrasil, Migalhas, Conjur) como apoio.
- Para cada afirmacao relevante, indique a fonte (lei, artigo, orgao ou site).
- Preste atencao especial a pontos que costumam ser mal compreendidos pelo publico leigo: quando \
um documento OFICIAL/publico e realmente exigido versus quando um documento PARTICULAR e aceito; \
prazos exatos; quem de fato tem direito; excecoes a regra geral.
- Se nao encontrar confirmacao clara para algo, diga explicitamente "nao encontrei confirmacao \
para X" em vez de supor ou inventar.
- Responda em texto corrido objetivo, em portugues, sem markdown."""

RESEARCH_PROMPT_TEMPLATE = """Pesquise na web para preparar o proximo carrossel de Instagram da area \
de atuacao "{practice_area}" do escritorio.

{topic_instruction}

Pesquise em profundidade sobre o tema escolhido:
- Requisitos legais atuais para o direito/beneficio em questao (lei, artigo, prazo)
- Documentos ou provas exigidas -- e se existem alternativas aceitas (ex.: laudo particular vs. \
laudo oficial/pericial, onde muita gente erra)
- Erros comuns de interpretacao do publico leigo sobre o tema
- Fontes oficiais consultadas

Responda EXATAMENTE neste formato (texto simples, sem markdown):
TEMA ESCOLHIDO: <tema em poucas palavras>
PESQUISA: <resumo factual, com fontes citadas inline>"""

USER_PROMPT_TEMPLATE = """Crie um carrossel de Instagram (5 a 7 slides) sobre o tema abaixo para a \
area de atuacao "{practice_area}" do escritorio.

Tema: {topic}

PESQUISA JURIDICA VERIFICADA (use como base factual do carrossel; NAO contradiga; se algo nao \
estiver confirmado aqui, use linguagem de possibilidade e nao afirme como regra geral):
{research}

{author_line}

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
  "caption": "legenda formatada em paragrafos curtos separados por linha em branco (\\n\\n dentro da string JSON), seguindo ESTA estrutura: (1) gancho de acolhimento em 1 frase curta; (2) paragrafo curto com o contexto/problema; (3) paragrafo curto com o diferencial ou insight principal do carrossel; (4) convite para falar com a equipe, 1-2 frases, sem forcar venda; (5) linha de CTA comecando com o emoji de envelope seguido de convite objetivo para mensagem no WhatsApp/direct; (6) ultima linha com 5 a 8 hashtags relevantes em portugues, separadas por espaco"
}}

Slide 1 e so capa (headline forte, body vazio). Os demais tem headline curto + body explicativo. \
Nunca prometa resultado, nunca use sensacionalismo. Nunca afirme exigencias documentais ou legais \
que nao estejam confirmadas na pesquisa acima.

Exemplo do formato exato esperado para o campo "caption" (siga esta estrutura de paragrafos curtos \
e quebras de linha, adaptando o conteudo ao tema do carrossel):

Quem enfrenta uma doenca grave ja lida com muita coisa.

Nao faz sentido perder tempo -- ou dinheiro -- por causa de um laudo medico que nao atende aos \
requisitos para o pedido de isencao do Imposto de Renda.

Entender a diferenca entre a via administrativa e a via judicial pode fazer toda a diferenca no \
resultado do seu pedido.

Se voce tem duvidas sobre o seu caso, fale com nossa equipe. Estamos prontos para analisar sua \
situacao e orientar voce sobre o melhor caminho.

[emoji de envelope] Envie uma mensagem no WhatsApp para uma conversa sem compromisso.

#Hashtag1 #Hashtag2 #Hashtag3 #Hashtag4 #Hashtag5 #Hashtag6 #Hashtag7 #Hashtag8

{signing_instruction}{extra_instruction_block}"""

EXTRA_INSTRUCTION_BLOCK = """

INSTRUCOES ADICIONAIS DO REVISOR HUMANO (aplique estas mudancas em relacao a versao anterior, \
tem prioridade sobre o resto): {extra_instruction}"""

FALLBACK_RESEARCH_NOTE = (
    "(Pesquisa automatica na web indisponivel nesta execucao: {error}. Redija com cautela extra -- "
    "use linguagem de possibilidade para qualquer requisito, prazo ou documento, evite afirmar como "
    "regra absoluta, e nao presuma exigencias documentais especificas, como a necessidade de laudo "
    "medico oficial quando um laudo particular pode ser aceito.)"
)


def _run_claude_code(
    system_prompt: str,
    user_prompt: str,
    allowed_tools: str = "",
    max_turns: int = 5,
    timeout: int = 180,
) -> str:
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
        "--max-turns", str(max_turns),
        "--allowedTools", allowed_tools,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p falhou (codigo {result.returncode})\n"
            f"stdout: {result.stdout[:2000]}\n"
            f"stderr: {result.stderr[:2000]}"
        )

    payload = json.loads(result.stdout)
    if payload.get("is_error"):
        raise RuntimeError(f"claude -p retornou erro: {payload}")
    return payload["result"]


def _parse_research(raw_text: str, fallback_topics: list[str]) -> tuple[str, str]:
    """Extrai (topico, resumo_pesquisa) da resposta da etapa de pesquisa. Se o formato
    esperado nao vier, cai em um topico aleatorio e usa o texto inteiro como pesquisa."""
    text = raw_text.strip()
    if "TEMA ESCOLHIDO:" in text and "PESQUISA:" in text:
        try:
            before, research = text.split("PESQUISA:", 1)
            topic = before.split("TEMA ESCOLHIDO:", 1)[1].strip().splitlines()[0].strip()
            research = research.strip()
            if topic and research:
                return topic, research
        except Exception:
            pass
    return random.choice(fallback_topics), text


def research_topic(practice_area: str, topics: list[str], forced_topic: str | None = None) -> tuple[str, str]:
    """Etapa 1: pesquisa na web as regras juridicas atuais do tema, com fontes.
    Retorna (topico_escolhido, resumo_da_pesquisa). Nunca lanca excecao -- em caso de
    falha (ex.: WebSearch indisponivel no ambiente), cai em um aviso de cautela para
    a etapa de redacao nao afirmar fatos nao verificados.

    Se forced_topic for passado (caso de regeneracao pedida por um revisor humano sobre
    um rascunho ja existente), a pesquisa e feita sobre esse tema especifico, sem escolher
    um novo."""
    if forced_topic:
        topic_instruction = f'O tema ja foi definido como: "{forced_topic}". Nao escolha outro tema.'
    else:
        topic_instruction = (
            f"Temas possiveis (escolha UM, de preferencia diferente dos ultimos usados): "
            f"{', '.join(topics)}"
        )
    prompt = RESEARCH_PROMPT_TEMPLATE.format(
        practice_area=practice_area,
        topic_instruction=topic_instruction,
    )
    fallback_topics = [forced_topic] if forced_topic else topics
    try:
        raw = _run_claude_code(
            RESEARCH_SYSTEM_PROMPT,
            prompt,
            allowed_tools="WebSearch,WebFetch",
            max_turns=12,
            timeout=240,
        )
        topic, research = _parse_research(raw, fallback_topics)
        if forced_topic:
            topic = forced_topic
        print(f"[pesquisa] ok -- tema: {topic}")
        print(f"[pesquisa] resumo (primeiros 500 chars): {research[:500]}")
        return topic, research
    except Exception as e:
        topic = forced_topic or random.choice(topics)
        print(f"[pesquisa] FALHOU, usando modo cauteloso sem pesquisa. Erro: {str(e)[:500]}")
        return topic, FALLBACK_RESEARCH_NOTE.format(error=str(e)[:300])


def generate_carousel_content(
    account: dict,
    recent_topics=None,
    forced_topic: str | None = None,
    extra_instruction: str = "",
) -> dict:
    """Gera o conteudo de um carrossel.

    forced_topic: quando informado (regeneracao pedida por revisor humano sobre um
        rascunho ja existente), mantem o mesmo tema em vez de sortear um novo.
    extra_instruction: feedback do revisor humano a ser aplicado nesta nova versao
        (ex.: "troque a assinatura", "corrija o slide 3, pesquise de novo esse ponto").
    """
    topics = account["topics"]
    if recent_topics:
        topics = sorted(topics, key=lambda t: t in recent_topics)

    topic, research = research_topic(account["practice_area"], topics, forced_topic=forced_topic)

    has_author = bool(account.get("author_name"))
    if has_author:
        author_line = f"Autor que assina: {account['author_name']}, {account['author_title']} - {account['author_oab']}"
        signing_instruction = "Assine o convite final com o nome do autor."
    else:
        author_line = "Este perfil publica em nome institucional do escritorio, sem assinatura de um advogado especifico."
        signing_instruction = "Nao assine com nome de pessoa nenhuma -- feche em nome do escritorio (ex: 'Fale com a nossa equipe')."

    extra_instruction_block = (
        EXTRA_INSTRUCTION_BLOCK.format(extra_instruction=extra_instruction.strip())
        if extra_instruction and extra_instruction.strip()
        else ""
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        practice_area=account["practice_area"],
        topic=topic,
        research=research,
        author_line=author_line,
        signing_instruction=signing_instruction,
        extra_instruction_block=extra_instruction_block,
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
