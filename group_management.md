# Gestão do grupo: Projeto A (Ticketing)

Ficheiro interno da equipa. Os documentos do projeto (README e docs/) são em inglês.

## 1. Equipa

| Membro | Nome | Utilizador GitHub | Email (git config user.email) |
|---|---|---|---|
| M1 | Dinis | dinobuefixe |  |
| M2 | Sabrina | sabsushi | sabrina.etic@gmail.com |
| M3 | Cris | CrisAxe | |

## 2. Datas

- Sessão 19 (entrega e demonstração): ____
- Tag SemVer (ex.: v1.0.0) enviada **antes** do início da sessão 19. Commits depois disso não contam.
- Objetivo: projeto a correr de um clone limpo uma semana antes da sessão 19.

## 3. Como trabalhamos os 3 ao mesmo tempo

Cada membro fica com uma **parte completa do projeto** (uma funcionalidade de ponta a ponta, que mexe em PostgreSQL, MongoDB, Redis e na app). Assim as três partes avançam em paralelo e cada pessoa faz commits nas quatro áreas, como exige o README.

| Parte | Pessoa | Fluxos | Dono de |
|---|---|---|---|
| 1. Lugares e reservas | M1 | F1, F2 | Locais, lugares, performances, preços, clientes, holds |
| 2. Compra e bilhetes | M2 | F3, F4, F5, F6 | Encomendas, bilhetes, pagamentos, promo codes, check-ins |
| 3. Dados e relatórios | M3 | F7 + scripts | Roles, índices, seed, relatórios, Redis rebuild/verify, concorrência (runner) |

### Regras para não nos bloquearmos

- **Contrato no dia 1 (2 h, os 3 juntos):** acordar os nomes das tabelas, das coleções Mongo, das chaves Redis e dos endpoints. Estão em `app/main.py`. Guardar o contrato no README.
- **Migrações com intervalos:** M1 usa 0001–0009, M2 usa 0010–0019, M3 usa 0020–0029. Assim não há conflitos.
- **M1 publica primeiro** as tabelas base (locais, performances, clientes) nos primeiros 1–2 dias. M2 e M3 trabalham em cima delas.
- **Redis e Mongo com prefixos próprios:** cada parte usa as suas chaves e coleções.
- **Um branch por pessoa**, PR para `main`, merge commit (nunca squash).
- **Se mudares um nome partilhado**, avisa os outros no grupo antes de fazer push.
- **Reunião de 15 minutos por dia** para sincronizar.

## 3.1 Setup do projeto (dia 1 e 2)

Antes de qualquer parte avançar, o projeto tem de arrancar de um clone limpo. Estas tarefas são pré-requisito de todas as partes e devem ficar prontas nos primeiros dois dias.

| # | Tarefa | Quem | Horas |
|---|---|---|---|
| S1 | Estrutura de pastas da raiz (`app/`, `postgres/`, `mongodb/`, `redis/`, `scripts/`, `docs/`), `.gitignore` e `.env.example` | M1 | 1 |
| S2 | `compose.yml` com `postgres`, `mongo`, `redis` e `app`, com healthchecks e portas em `127.0.0.1` (rascunho já feito) | M1 | 2 |
| S3 | Dockerfile e `requirements.txt` da app (rascunho já feito) e `/health` na API | M1 | 1 |
| S4 | `setup.sh`, passo 1 (como superuser): criar a base de dados, os roles owner, app e leitura, e as extensões `btree_gist` e `pg_trgm` | M1 | 2 |
| S5 | Alembic configurado com `MIGRATION_DATABASE_URL` (`alembic init`, `env.py`), com uma primeira migração vazia que aplica sem erros | M1 | 2 |
| S6 | `setup.sh`, passo 2 (como owner): aplicar as migrações; `ALTER DEFAULT PRIVILEGES` e grants para os roles app e leitura | M1 | 1 |
| S7 | `setup.sh`, passo 3 (como root do MongoDB): criar o utilizador da app com `readWrite` só na base do projeto, coleções e índices | M1 | 2 |
| S8 | Redis com `requirepass` e persistência AOF; a app liga-se aos três motores com as URLs do `.env` | M1 | 2 |
| S9 | Teste de clone limpo: `cp .env.example .env`, `docker compose up -d`, `./scripts/setup.sh` e `./scripts/seed.sh` (versão mínima) | M1 | 1 |

**Regras do `setup.sh`:**

- Corre em três passos, nesta ordem: superuser (base e roles), owner (migrações), root do Mongo (utilizador, coleções, índices).
- É idempotente: pode ser corrido duas vezes sem erro.
- Lê todas as passwords do `.env`, sem nada escrito no script.
- Nunca usa `postgres` nem `root` na app.

**Total:** cerca de 14 h, todas com M1. Como M1 tem também a Parte 1, o setup deve ficar pronto nos primeiros dois dias para que M2 e M3 possam começar a usar o projeto. M2 e M3 revêem o `setup.sh` quando estiver pronto, mas não o escrevem.

## 4. Tarefas por parte

Horas são estimativas. Os valores incluem testes básicos, mas não a leitura do README.

### Parte 1: Lugares e reservas (M1, ~48 h)

| # | Tarefa | Horas |
|---|---|---|
| 1 | Migrações base: locais, secções, lugares, organizadores, eventos, performances, preços, clientes | 10 |
| 2 | Regras no PostgreSQL: lugar único, capacidade standing, performances sem sobreposição | 6 |
| 3 | Seed de locais, lugares, eventos e performances | 4 |
| 4 | F1: mapa de lugares, lido do Redis | 6 |
| 5 | F2: holds com 10 minutos, máximo 6 bilhetes, idade mínima, limite de 10 tentativas/min | 10 |
| 6 | Log de tentativas de hold no MongoDB (validador, TTL de 90 dias, escrita pela app) | 5 |
| 7 | Teste de concorrência "mesmo lugar" (50 clientes) | 4 |
| 8 | `docs/postgres.md` (parte da Parte 1) e secção de holds em `docs/redis.md` | 3 |

### Parte 2: Compra e bilhetes (M2, ~55 h)

| # | Tarefa | Horas |
|---|---|---|
| 1 | Migrações: encomendas, bilhetes, pagamentos, códigos promocionais, check-ins | 10 |
| 2 | Regras no PostgreSQL: bilhete único por lugar, limite de capacidade, limite de códigos, valores não negativos | 6 |
| 3 | F3: checkout em transação, pagamento simulado (`simulate`), código promocional | 10 |
| 4 | F4 (cancelar encomenda) e F6 (cancelar performance com reembolsos) | 6 |
| 5 | F5: check-in (dia em Lisboa, só uma vez, registo de todas as leituras) | 4 |
| 6 | Redis: "trending now" e contadores de lugares livres por performance | 4 |
| 7 | MongoDB: coleção de vendas por performance (validador, export, pipeline do relatório 1) | 5 |
| 8 | Teste de concorrência "últimos lugares" (100 clientes) e teste do código promocional | 4 |
| 9 | Seed de encomendas, pagamentos, bilhetes e check-ins | 6 |
| 10 | `docs/concurrency.md` (parte da Parte 2) | 3 |

### Parte 3: Dados e relatórios (M3, ~52 h)

| # | Tarefa | Horas |
|---|---|---|
| 1 | Roles e grants (owner, app, leitura) e `scripts/setup.sh` | 5 |
| 2 | Índices e três `EXPLAIN (ANALYZE, BUFFERS)` com e sem índice, em `docs/postgres.md` | 6 |
| 3 | `scripts/seed.sh`: orquestra o seed, a exportação e o rebuild, abaixo de 5 minutos | 4 |
| 4 | Script de exportação PostgreSQL → MongoDB, com o role de leitura | 4 |
| 5 | Pipelines de relatórios 2 a 6 (mínimo 3) e validadores das coleções de relatório | 8 |
| 6 | Redis: script de rebuild, script de verificação e prova de cache (MONITOR e log) | 6 |
| 7 | F7: endpoints dos relatórios | 4 |
| 8 | Runner de concorrência (saída por cenário, código de saída 0 ou 1) | 5 |
| 9 | `docs/mongodb.md`, `docs/redis.md` e `docs/runbook.md` | 10 |

### Trabalho comum (cada membro, ~6 h)

- README: contrato, como correr, tabela de autores, stack e porquê, lista de endpoints.
- `docs/architecture.md`: fonte de verdade de cada dado, escrita em duas bases, expiração.
- `docs/ai-usage.md`: uma entrada por uso relevante de IA e a declaração final.
- Revisão cruzada dos PRs dos outros.

## 5. Git

Cada pessoa tem de ter commits próprios e não triviais em **cada uma** destas áreas:

| Área | Caminho |
|---|---|
| PostgreSQL | `postgres/` |
| MongoDB | `mongodb/` |
| Redis | `redis/` |
| App | `app/` |

Com esta divisão, cada parte já cobre as quatro áreas. Mesmo assim, verifica antes da entrega:

```bash
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- postgres/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- mongodb/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- redis/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- app/ | wc -l
```

Não contam: merges, `Co-authored-by`, commits só de formatação, e commits com email fora da tabela de autores. Penalização de −2 pontos por área em falta.

**Desativar squash merge:** Settings → General → Pull Requests → desmarcar "Allow squash merging".

**Nunca** fazer `git push --force` no `main`.

## 6. Ordem de trabalho

| Semana | M1 | M2 | M3 |
|---|---|---|---|
| 1 | Contrato (todos). Setup do projeto completo (secção 3.1) e migrações base | Modelo de encomendas (rascunho) e revisão do contrato | Validadores Mongo e revisão do `setup.sh` quando estiver pronto |
| 2 | F1 e F2 (com o log de tentativas) | Migrações de compra, regras, F3 | Índices, exportação, pipelines |
| 3 | Teste "mesmo lugar" | F4, F5, F6, trending | F7, rebuild e verify do Redis, `seed.sh` |
| 4 | Ajustes e revisão dos PRs | Teste "últimos lugares" e código promocional | Runner de concorrência, prova de cache |
| Sessões 17–18 | Documentação das partes e verificação de commits | Documentação das partes e verificação de commits | Runbook e documentação final |
| Antes da sessão 19 | Clone limpo e tag `v1.0.0` (quem fica com a tag decide em conjunto) | Clone limpo | Cronometrar o seed |

## 7. Riscos

- **M2 espera pelas tabelas base de M1.** Mitigação: M1 publica as migrações base no primeiro ou segundo dia.
- **Seed lento.** Mitigação: usar `COPY` e medir cedo com volumes reduzidos.
- **Concorrência difícil de reproduzir.** Mitigação: começar com 5 clientes, depois 50 e 100.
- **Documentação no fim.** Mitigação: cada pessoa escreve a documentação da sua parte enquanto programa.
- **Estimativas baixas.** As horas são grosseiras. Revê-las ao fim da semana 1.

## 8. Checklist final

- [ ] Clone limpo: `cp .env.example .env`, `docker compose up -d`, `./scripts/setup.sh`, `./scripts/seed.sh`.
- [ ] `setup.sh` corre duas vezes seguidas sem erro.
- [ ] Migrações aplicam-se a uma base vazia.
- [ ] Seed abaixo de 5 minutos, com as constraints ativas.
- [ ] F1 a F7 funcionam através da app.
- [ ] `FLUSHALL`, rebuild e verify do Redis sai com 0.
- [ ] Três pipelines Mongo a correr, com amostras em `docs/mongodb.md`.
- [ ] Três `EXPLAIN` com e sem índice.
- [ ] A app não liga como `postgres` nem `root`.
- [ ] Sem passwords reais no Git.
- [ ] Os 8 documentos obrigatórios existem, incluindo `docs/ai-usage.md` com a declaração.
- [ ] Cada membro tem commits não triviais nas quatro áreas.
- [ ] Squash merge desativado.
- [ ] Tag SemVer enviada antes da sessão 19.