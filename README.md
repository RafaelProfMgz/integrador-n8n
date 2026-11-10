# n8n Social Publishing

Projeto Docker para automacoes sociais. Inclui n8n + PostgreSQL, modelos de foto no Instagram profissional/Facebook e modelos de verificacao de conta/publicacao de texto no X. Os modelos iniciam em simulacao, sem chamadas externas.

## Iniciar

Requisitos: Docker Engine com Compose, Python 3; Node.js para os testes locais.

```sh
python3 scripts/setup.py
docker compose config --quiet
docker compose up -d --wait --wait-timeout 180
```

Abra <http://localhost:5680> e crie o usuario proprietario. `setup.py` gera senha do banco e chave de criptografia em `.env` privado e preserva configuracao existente.

Os modelos Meta originais foram importados e simulados; a migracao desses modelos para `$env` esta pendente de aplicacao. Para os novos modelos X, veja o guia de configuracao abaixo. Para uma nova instalacao, no editor n8n, use **Import from File** para `workflows/facebook-photo.json` e `workflows/instagram-photo.json`. Execute **Inicio manual** com os valores originais para ver a previa. Nao e preciso token para simular. Para publicacao real, siga [configuracao Meta](docs/meta-setup.md).

## Conteudo

- [Chatbot editorial com OpenAI](docs/chatbot.md)
- [Subagente de imagem para publicacao](docs/image-agent.md)
- [Monitor e skills de comentarios do Alpendre](docs/comment-workflows.md)
- [Arquitetura e evolucao](docs/architecture.md)
- [Configurar Instagram/Facebook](docs/meta-setup.md)
- [Configurar X: conta e publicacao de texto](docs/x-setup.md)
- [Operacao, backup e restauracao](docs/operations.md)
- [MCP no Codex e instalacao da skill](docs/mcp.md)
- [Regras para agentes](AGENTS.md)
- [Skill do projeto](skills/n8n-social-publishing/SKILL.md)
- [Fontes e licenciamento](docs/sources-and-license.md)

## Validar e desenvolver

```sh
python3 scripts/build_workflows.py
python3 scripts/build_chat_workflows.py
python3 -m unittest discover -s tests
docker compose config --quiet
```

Edite os modelos pelo gerador `scripts/build_workflows.py`; regenere os JSON. Alteracoes feitas na interface precisam voltar ao repositorio sem tokens, IDs privados nem dados de execucao fixados.

## Escopo atual

Inclui templates HTTP para fotos, validacao de entrada, simulacao, aprovacao local e verificacao do status de container Instagram. IDs e tokens Meta precisam ser preenchidos exclusivamente no `.env`; os modelos usam referencias `$env` e nao requerem cadastro de Credentials no editor. Chamadas reais nao foram feitas.

Agendamento editorial, aprovacao persistente, fila com deduplicacao, midias hospedadas e conectores YouTube/TikTok sao proximas etapas. No X, upload de midia e renovacao OAuth ainda nao estao implementados. Os modelos nao oferecem garantia de envio unico; consulte a plataforma antes de repetir uma execucao real.

## Conversar para publicar

O workflow **Editorial - chatbot de publicacoes** conversa, prepara textos por rede e pede confirmacao da previa antes de chamar os tres subworkflows de publicacao. Preencha `OPENAI_API_KEY` no `.env`, aplique somente o servico editorial e abra o chat pelo editor do workflow. O modo inicial e simulacao. Veja o [guia do chatbot](docs/chatbot.md).

O chatbot tambem chama o subagente dedicado de imagem: `SIMULAR IMAGEM: descricao` testa; `GERAR IMAGEM: descricao` solicita a geracao OpenAI. Consulte o [guia de imagem](docs/image-agent.md) para chave, arquivo binario e URL publica.

## Responder a comunidade

Os workflows de comentarios encontram posts recentes proprios, classificam comentarios pelas skills do Alpendre e montam uma fila de revisao. Leitura/envio reais comecam desligados. Ha adaptadores para Instagram, Facebook e X; os detalhes de permissoes, modo automatico e aprovacao estao no [guia de comentarios](docs/comment-workflows.md).
# integrador-n8n
