---
name: n8n-social-publishing
description: Criar, revisar e operar workflows n8n deste projeto Docker para publicar conteudo social, com fotos em Instagram profissional/Facebook e verificacao de conta/publicacao de texto no X.
---

Leia `AGENTS.md` na raiz do projeto. Localize a raiz por `compose.yaml`; nao dependa do diretorio atual.

- Para infraestrutura e expansao, consulte `docs/architecture.md` e `docs/operations.md`.
- Para o chatbot, leia `docs/chatbot.md` e `services/editorial/app.py`. A IA prepara rascunhos; somente a confirmacao exata da previa cria jobs. Preserve o isolamento de sessoes, invalidacao de codigos, transacao de consumo e estados incertos. Regenere os subworkflows ao alterar os publicadores compartilhados.
- Para o subagente de imagem em runtime, leia `docs/image-agent.md`, `scripts/build_image_workflow.py` e `services/editorial/image_agent.py`. Preserve escopo somente imagem, modo dry-run, chave no ambiente do servico e registro de tentativa por request_id. Uma imagem nova exige nova previa; sem URL publica limpe o anexo anterior e informe a pendencia.
- Para comentarios das contas proprias, leia `docs/comment-workflows.md` e a skill de respostas em `response-skills/book-community/SKILL.md`. Preserve a separacao entre leitura, revisao e envio, a lista de posts/contas permitidos, opt-out e limite por interacao. O servico de comentarios nao usa `$env` no n8n nem um LLM.
- Para fotos Meta, leia `docs/meta-setup.md` e o JSON correspondente em `workflows/`. Para conexao do agente, leia `docs/mcp.md`.
- Para X, consulte `docs/x-setup.md` e os modelos `x-*.json`: use token OAuth 2.0 de usuario, nunca app-only Bearer Token. Confira `/2/users/me` contra `X_USER_ID` antes do POST; nao implemente refresh sem persistir tokens rotacionados.
- Preserve dry-run e workflow inativo ao criar ou exportar modelos. Se houver autorizacao de publicacao na sessao, aplique-a somente ao conteudo e contas abrangidos; caso contrario, prepare uma previa concreta antes de solicitar a liberacao final.
- IDs, versao Graph e tokens das plataformas sao configurados exclusivamente no `.env` da raiz. O Compose injeta apenas as variaveis necessarias no n8n; App ID/Secret ficam fora do container enquanto nao forem usados. Use `$env` nos parametros HTTP e tokens somente no header `Authorization: Bearer ...`; nao retorne tokens em nodes Code nem use access_token na URL. Preserve `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, necessario para essas expressoes. Esse acesso permite a editores de workflows ler o ambiente; limite a edicao a pessoas confiaveis.
- Valide versao Graph suportada, ID da conta e URL HTTPS publica da imagem. Nao invente permissoes nem endpoints; confira fontes oficiais quando adicionar formato ou plataforma.
- No Instagram, publique somente containers com status FINISHED. Se o processamento nao terminou, preserve o container ID e consulte novamente; nao reinicie automaticamente a criacao.
- Falha ambigua de POST exige reconciliacao com a plataforma antes de repetir. Os modelos manuais nao tem deduplicacao duravel; antes de automatizar agendas implemente registro persistente e exclusao mutua por destino.
- Para X, YouTube e TikTok, implemente adaptadores separados e seus OAuth/escopos/limites oficiais, preservando o contrato editorial documentado. Nao trate esses conectores como prontos.

Verifique `docker compose config --quiet`, `python3 -m unittest discover -s tests` e importacao/dry-run quando possivel. Relate separadamente verificacao estatica, execucao local e chamadas reais externas.
