# Automação de carrosséis no Instagram — RRS Advocacia

Publica automaticamente um carrossel jurídico (gerado por IA) em 4 contas do Instagram,
3x por semana (segunda/quarta/sexta, 11h de Brasília), via GitHub Actions.

## Como funciona

1. O GitHub Actions "acorda" no horário agendado (`.github/workflows/publish.yml`).
2. Para cada conta, roda `scripts/main.py`, que:
   - gera o tema e o texto dos slides com o Claude Code CLI (usando sua assinatura
     Pro/Max, sem custo de API por token), seguindo o estilo da casa e as regras de
     publicidade da OAB (ver `scripts/generate_content.py`);
   - desenha as imagens dos slides (`scripts/render_carousel.py`);
   - sobe as imagens no Cloudinary e publica o carrossel no Instagram
     (`scripts/publish_instagram.py`).

Nenhum segredo (token, chave de API) fica salvo no código — tudo vem dos **GitHub
Secrets** do repositório, configurados uma única vez.

## Passo a passo para colocar no ar

### 1. Criar conta no GitHub (gratuita)
Acesse github.com → "Sign up" → siga o cadastro.

### 2. Criar o repositório
No GitHub, clique em "New repository". Nome sugerido: `rrs-instagram-automation`.
Marque como **Privado** (importante, mesmo sem segredos no código). Não adicione README
nem .gitignore no assistente (já estão aqui).

### 3. Enviar este código para o repositório
No seu computador (ou peça para eu te ajudar), dentro desta pasta:
```
git init
git add .
git commit -m "Automação de carrosséis Instagram"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/rrs-instagram-automation.git
git push -u origin main
```

### 4. Gerar o token do Claude Code (usa sua assinatura Pro/Max, sem cobrança por token)
Este projeto usa sua assinatura do Claude em vez de uma chave de API paga por uso. No seu
computador:
1. Instale o Claude Code, se ainda não tiver: `curl -fsSL https://claude.ai/install.sh | bash`
   (Mac/Linux/WSL) ou veja claude.com/download para Windows.
2. Rode `claude` e faça login com a conta que tem a assinatura Pro/Max/Team.
3. Rode `claude setup-token` — ele abre o navegador para autorizar e depois imprime um
   token no terminal (começa diferente de uma chave de API comum). Copie esse token.

Esse token vale por 1 ano e é só para uso em CI/scripts — não expõe sua senha.

### 5. Configurar os GitHub Secrets
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie estes 5 segredos (nome exato à esquerda, valor à direita):

| Nome do segredo | Valor |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | o token que você gerou no passo 4 com `claude setup-token` |
| `CLOUDINARY_CLOUD_NAME` | `ydunkl0` |
| `CLOUDINARY_API_KEY` | ver arquivo `.env` que preparei (não incluído no repositório) |
| `CLOUDINARY_API_SECRET` | ver arquivo `.env` que preparei (não incluído no repositório) |
| `INSTAGRAM_ACCOUNTS_JSON` | conteúdo do arquivo `SECRET_INSTAGRAM_ACCOUNTS_JSON.txt` que preparei — copie o arquivo inteiro e cole como valor do segredo |

**Atenção ao limite de uso:** como o robô roda com sua assinatura (não com uma chave
paga à parte), o consumo de 12 carrosséis/mês entra na mesma cota de uso do seu plano
Pro/Max. Para esse volume não deve ser um problema, mas se você usar bastante o Claude
Code para outras coisas no mesmo período, vale acompanhar pelo `/status` no terminal.

**Importante:** os arquivos `.env` e `SECRET_INSTAGRAM_ACCOUNTS_JSON.txt` contêm dados
sensíveis e **não devem** ir para o repositório (o `.gitignore` já bloqueia o `.env`;
o segundo arquivo fica fora da pasta do repositório de propósito — apague-o do seu
computador depois de colar o conteúdo no GitHub Secrets).

### 6. Testar manualmente
No repositório: aba **Actions** → "Publicar carrossel no Instagram" → **Run workflow**.
Isso publica imediatamente (sem esperar o agendamento) — bom para conferir se está tudo
certo antes de deixar rodando sozinho.

### 7. Pronto
A partir daqui, o robô publica sozinho 3x por semana, para as 4 contas, sem você
precisar fazer nada.

## Editar temas ou frequência

- **Temas por conta:** edite a lista `topics` em `config/accounts.json`.
- **Frequência/horário:** edite a linha `cron` em `.github/workflows/publish.yml`
  (formato `minuto hora dia mês dia-da-semana`, em UTC).
- **Cores da marca:** edite `brand_color`/`accent_color` em `config/accounts.json`.

## Renovação de tokens

- **Tokens das Páginas do Facebook/Instagram** (`INSTAGRAM_ACCOUNTS_JSON`): duram cerca
  de 60 dias. Quando expirarem, as publicações vão falhar (você verá isso na aba Actions
  do GitHub, com um X vermelho). Nesse caso, me chame de novo para gerar novos tokens.
- **Token do Claude Code** (`CLAUDE_CODE_OAUTH_TOKEN`): dura 1 ano. Perto de expirar,
  rode `claude setup-token` de novo e atualize o segredo no GitHub.
