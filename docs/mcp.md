# Conexao MCP e skill

`https:///mcp-server/http` esta incompleto: falta o host. Para esta instancia local, use `http://localhost:5680/mcp-server/http`. Se o cliente estiver em outro computador/container, localhost aponta para ele proprio; use uma URL da instancia acessivel ao cliente.

Depois de criar o usuario proprietario, abra **Settings > Instance-level MCP**, habilite o acesso e copie a Server URL em **Connect a client**. Conceda acesso apenas aos workflows desejados; evite exposicao automatica de todos os novos workflows. O MCP integrado do n8n e diferente do projeto comunitario externo tambem chamado n8n-mcp; aqui esse e apenas o nome escolhido para a conexao.

## Codex com OAuth

```sh
codex mcp add n8n-mcp --url http://localhost:5680/mcp-server/http
codex mcp login n8n-mcp
codex mcp list
```

Conclua o login no navegador e revise os acessos. A conexao global `n8n-mcp` foi registrada nesta entrega com a URL local acima. A autenticacao OAuth ficou pendente da criacao do proprietario e habilitacao do MCP. Depois dessas etapas, execute `codex mcp login n8n-mcp`; nao precisa adicionar o servidor novamente.

## Alternativa com token

Use o token da aba API key do MCP, que nao deve ser confundido com o Page Access Token da Meta nem com uma API key REST generica do n8n. Exporte `N8N_MCP_TOKEN` no ambiente do processo que inicia o Codex, usando um gerenciador de segredos ou entrada oculta, sem registrar o valor em comandos versionados.

```sh
codex mcp add n8n-mcp --url http://localhost:5680/mcp-server/http --bearer-token-env-var N8N_MCP_TOKEN
```

O `.env` do Compose nao e carregado automaticamente pelo aplicativo Codex. Reinicie o cliente com a variavel disponivel quando necessario. Em producao, copie a URL HTTPS real do painel, configurando corretamente o proxy.

## Skill local

A skill versionada esta em `skills/n8n-social-publishing/SKILL.md`. `AGENTS.md` orienta os agentes deste repositorio a usa-la. Para descoberta automatica no Codex, fora do ambiente restrito atual:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/n8n-social-publishing" ~/.agents/skills/n8n-social-publishing
```

Execute na raiz do projeto. Se o destino ja existir, inspecione-o antes de alterar; nao substitua outra skill. Reinicie o Codex se necessario. Nesta sessao `.agents` e `.codex` do projeto sao montados como somente leitura. A skill foi instalada por link em `~/.codex/skills/n8n-social-publishing`, apontando para a pasta versionada. Reinicie o Codex para atualizar a descoberta, se necessario; o caminho explicito de AGENTS.md ja esta disponivel.

Fontes: [MCP n8n](https://docs.n8n.io/connect/connect-to-n8n-mcp-server.md) e [MCP Codex](https://learn.chatgpt.com/docs/extend/mcp).
