"""
Revisor independente dos carrosseis gerados a partir de artigos do blog.

Roda numa chamada separada do Claude Code CLI, que nao escreveu o carrossel, recebe o
artigo original como unica fonte de verdade e abre as imagens ja renderizadas (ferramenta
Read) para conferir o resultado visual. O carrossel so e aprovado sem nenhum problema
classificado como "bloqueante" -- a regra e aplicada aqui no codigo, nao so no parecer.
"""
import json

from generate_content import _run_claude_code, parse_json_reply, signing_rules

REVIEW_SYSTEM_PROMPT = """Voce e o revisor final das publicacoes de Instagram e Facebook do \
escritorio Rafael Rocha e Santos Advocacia (Juiz de Fora - MG). Nada e publicado sem a sua \
aprovacao, e o que voce aprovar vai ao ar com o nome do escritorio e dos advogados. Voce nao \
escreveu o carrossel: revise com olhar critico, como um socio cuidadoso revisaria o trabalho \
de um estagiario talentoso. Seja rigoroso no que importa e nao invente problemas cosmeticos.

Classifique cada problema como:
- "bloqueante": impede a publicacao. Use para: violacao das regras de publicidade da OAB; \
afirmacao juridica (lei, artigo, sumula, prazo, valor, percentual, data, requisito, documento) \
que nao esteja no artigo-fonte ou que o contradiga; requisito apresentado como obrigatorio \
quando o artigo usa linguagem de possibilidade; assinatura com autor ou titulo errado; numero \
de OAB na legenda; texto cortado, sobreposto ou ilegivel nas imagens; erro de portugues \
visivel; slide fora de ordem ou sem sentido; link do artigo ausente ou diferente do informado.
- "ajuste": melhoraria a publicacao, mas nao impede (gancho mais forte, frase mais curta, \
hashtag melhor).

REGRAS DA OAB (Estatuto, Codigo de Etica e Disciplina, Provimento 205/2021): proibido \
prometer ou insinuar resultado ("garantimos", "voce vai ganhar", "com certeza consegue"); \
mercantilizacao (preco, honorarios, promocao, oferta, "gratis" como isca, urgencia artificial, \
"ultimas vagas"); superlativos autopromocionais ("o melhor", "o mais"); comparacao com outros \
escritorios ou advogados; casos reais identificaveis, depoimentos ou resultados obtidos; \
captacao ostensiva ou apelo emocional exagerado. Permitido: informar e educar, linguagem de \
possibilidade ("pode ter direito"), convite sobrio para conversa "sem compromisso".

FIDELIDADE AO ARTIGO: o artigo-fonte e a unica fonte de verdade. Confira cada dado concreto do \
carrossel e da legenda contra ele. Se um dado nao estiver no artigo, e bloqueante, mesmo que \
voce acredite que esteja correto.

IMAGENS: abra TODAS as imagens com a ferramenta Read, na ordem, antes de dar o parecer. \
Verifique legibilidade, texto cortado ou saindo da area, sobreposicao com a logo ou a barra de \
progresso, contraste e erros de digitacao.

Responda SOMENTE com JSON valido, sem markdown:
{"aprovado": true|false,
 "nota": 0-10,
 "problemas": [{"onde": "slide N" | "legenda" | "geral", "gravidade": "bloqueante" | "ajuste",
   "descricao": "o que esta errado", "correcao": "como corrigir, de forma concreta"}],
 "resumo": "1-2 frases com o parecer geral"}
"aprovado" so pode ser true se nao houver nenhum problema bloqueante."""

REVIEW_PROMPT_TEMPLATE = """Revise o carrossel abaixo antes da publicacao.

CONTA: {page_name} (@{ig_username}) -- area: {practice_area}
{author_line}
Regra de assinatura da legenda: {signing_instruction}
LINK DO ARTIGO (deve aparecer na legenda exatamente assim): {article_url}

IMAGENS RENDERIZADAS (abra todas com Read, nesta ordem):
{image_list}

CARROSSEL (texto dos slides e legenda):
{carousel_json}

ARTIGO-FONTE -- "{article_title}":
{article_text}"""


def review_carousel(account: dict, post: dict, article_text: str, content: dict,
                    image_paths: list[str], model: str) -> dict:
    author_line, signing_instruction = signing_rules(account)
    prompt = REVIEW_PROMPT_TEMPLATE.format(
        page_name=account["page_name"],
        ig_username=account["ig_username"],
        practice_area=account["practice_area"],
        author_line=author_line,
        signing_instruction=signing_instruction,
        article_url=post["link"],
        image_list="\n".join(f"{i}. {p}" for i, p in enumerate(image_paths, 1)),
        carousel_json=json.dumps(
            {"slides": content["slides"], "caption": content["caption"]}, ensure_ascii=False, indent=2
        ),
        article_title=post["title"],
        article_text=article_text,
    )
    raw = _run_claude_code(
        REVIEW_SYSTEM_PROMPT,
        prompt,
        allowed_tools="Read",
        max_turns=len(image_paths) + 6,
        timeout=600,
        model=model,
    )
    review = parse_json_reply(raw)
    problems = review.get("problemas") or []
    blocking = [p for p in problems if p.get("gravidade") == "bloqueante"]
    review["problemas"] = problems
    review["aprovado"] = bool(review.get("aprovado")) and not blocking
    return review


def format_feedback(review: dict) -> str:
    lines = [f"- [{p.get('gravidade')}] {p.get('onde')}: {p.get('descricao')} -> {p.get('correcao')}"
             for p in review.get("problemas", [])]
    return "O revisor reprovou a versao anterior. Corrija TODOS os pontos bloqueantes e, quando fizer sentido, os ajustes:\n" + "\n".join(lines)
