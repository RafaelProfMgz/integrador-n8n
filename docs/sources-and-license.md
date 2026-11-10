# Fontes e licenciamento

Consultadas para esta entrega:

- [Instalacao Docker informada](https://docs.n8n.io/deploy/host-n8n/install-options/install-with-docker): a pagina direciona ao Compose recomendado.
- [Docker Compose n8n](https://docs.n8n.io/deploy/host-n8n/install-options/install-using-docker-compose)
- [MCP integrado n8n](https://docs.n8n.io/connect/connect-to-n8n-mcp-server.md)
- [MCP Codex](https://learn.chatgpt.com/docs/extend/mcp)
- [Licenca Community n8n](https://docs.n8n.io/n8n-community-license)
- [Licenca upstream](https://github.com/n8n-io/n8n/blob/master/LICENSE.md)
- [Instagram API, colecao oficial Meta](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)

O n8n e source-available/fair-code e a Community usa Sustainable Use License; nao deve ser descrito como MIT ou open source OSI. A documentacao permite usos internos de negocio e pessoais sob suas condicoes. Oferecer n8n hospedado ou acesso a clientes pode exigir acordo comercial; confirme o caso concreto na licenca e FAQs oficiais antes de transformar a instalacao em servico a terceiros.

As imagens conservam suas licencas upstream. Esta entrega nao escolhe uma licenca de distribuicao para o codigo original do usuario nem altera os avisos do n8n.

A implementacao do chatbot tambem usa a [documentacao oficial OpenAI de Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) e os nodes oficiais Chat Trigger/Execute Sub-workflow do n8n. A chave OpenAI e configurada separadamente no `.env`; nao faz parte da licenca n8n.
