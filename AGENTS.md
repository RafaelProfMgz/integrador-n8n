# Regras do projeto

Objetivo: operar n8n em Docker para publicacoes sociais, iniciando com fotos no Instagram e em Paginas do Facebook. Responder em portugues.

Leia `docs/architecture.md` para decisoes, `docs/meta-setup.md` para integracao Meta, `docs/x-setup.md` para X, `docs/chatbot.md` para o chatbot e `docs/operations.md` para operacao. Para trabalhar nos workflows, use `skills/n8n-social-publishing/SKILL.md`.

- IDs, configuracao e segredos das plataformas ficam exclusivamente em `.env` local; os workflows usam referencias `$env`; nunca valores literais em workflows, exemplos, logs ou commits. App ID/Secret ficam apenas no arquivo local enquanto nao houver fluxo de OAuth que os use. Tokens entram somente no header HTTP, nunca no JSON de saida de nodes. Nao exibir `docker compose config` sem `--quiet` quando houver segredos.
- Use APIs oficiais. Facebook significa Pagina; Instagram usa conta profissional vinculada a Pagina na modalidade Facebook Login escolhida.
- Novos workflows ficam inativos e em dry-run. Publicacao real exige conteudo, conta e autorizacao definidos pelo usuario; autorizacoes ja dadas na sessao continuam validas.
- Exportar JSON sem credenciais e sem pinData. Manter expressoes n8n, nomes das etapas e contratos coerentes.
- Nao adicionar retry automatico a POST de publicacao: timeout pode esconder sucesso remoto. Reconciliar IDs antes de repetir.
- Nao anunciar idempotencia, agendamento, aprovacao persistente ou integracao implementada se existir apenas desenho no documento.
- Nao alterar tabelas internas do n8n. Uma futura fila editorial usa banco/usuario proprios.
- Fixar versao n8n; atualizar com backup e leitura de release notes. Nunca executar `down -v` como rotina.
- Validar Compose com `docker compose config --quiet`; scripts Python com compilacao e testes comportamentais pertinentes. Validar importacao e dry-run no n8n quando Docker estiver acessivel.
- Manter a skill versionada em `skills/`; este ambiente monta `.agents` e `.codex` como somente leitura. Instalacao global e configuracao MCP ficam descritas em `docs/mcp.md`.

- No chatbot, o modelo so altera o rascunho: nao recebe ferramentas de publicacao, tokens sociais nem controle da flag approved. Confirmacao, revisao, destinos e consumo unico do codigo sao geridos por `services/editorial/app.py`.
- Preserve o volume editorial e os registros de tentativas, inclusive apos timeout. Nao refaca posts incertos nem execute o smoke test sobre o chatbot publicado/em uso.

- Para gerar imagens em runtime, consulte `docs/image-agent.md`. O subagente so gera um JPEG por descricao; nao escolhe destinos, nao escreve legendas e nao publica. Use `request_id` estavel em retries; nunca repita automaticamente uma tentativa incerta ou anuncie uma URL interna como publica.

- Para comentarios da comunidade, leia `docs/comment-workflows.md` e `response-skills/book-community/SKILL.md`. Nao invente servicos ou cronogramas do Alpendre. As skills iniciais sao deterministicas; caso sem contexto vai para revisao.
- O modulo `community` usa tokens do `.env` exclusivamente em seu proprio ambiente e nao exige `$env` no n8n. Preserve opt-outs, deduplicacao, revalidacao e estados incertos. Nao habilite agendamento/envio real como efeito de uma instalacao de modelos.
