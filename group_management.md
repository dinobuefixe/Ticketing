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
- Tag SemVer (ex.: `v1.0.0`) enviada **antes** da sessão 19. Commits depois disso não contam.
- Objetivo: projeto a correr de um clone limpo uma semana antes da sessão 19.

## 3. Como trabalhamos

Cada pessoa tem uma **parte completa** do projeto. A parte mexe em PostgreSQL, MongoDB, Redis e na app. Assim as três partes avançam ao mesmo tempo e cada pessoa faz commits nas quatro áreas.

| Parte | Pessoa | Fluxos | O que tem |
|---|---|---|---|
| Setup | M1 | — | Docker, base de dados, migrações, MongoDB e Redis prontos |
| 1. Lugares e reservas | M1 | F1, F2 | Locais, lugares, performances, preços, clientes, holds |
| 2. Compra e bilhetes | M2 | F3, F4, F5, F6 | Encomendas, bilhetes, pagamentos, promo codes, check-ins |
| 3. Dados e relatórios | M3 | F7 | Índices, seed, exportação, pipelines, Redis rebuild, runner de concorrência |

### Regras para trabalharmos sem bloqueios

1. **Dia 1 (2 horas, os três juntos):** lemos este ficheiro e acordamos os nomes das tabelas, coleções, chaves Redis e endpoints. Os endpoints já estão em `app/main.py`.
2. **Migrações com números reservados:** M1 usa `0001` a `0009`, M2 usa `0010` a `0019`, M3 usa `0020` a `0029`.
3. **M1 publica as tabelas base primeiro** (até ao fim do dia 2). M2 só começa as migrações de compra depois disso.
4. **Chaves Redis e coleções Mongo com prefixo da parte** (ex.: `hold:`, `sales:`, `report:`).
5. **Um branch por pessoa**, um PR por tarefa grande, merge com "Create a merge commit" ou "Rebase and merge".
6. **Se mudares um nome partilhado**, avisa os outros no grupo antes do push.
7. **Reunião de 15 minutos por dia** para dizer o que fizeste, o que bloqueia e o que vem a seguir.

## 3.1 Tabelas do PostgreSQL

São 16 tabelas (o README pede pelo menos 10). A coluna "Dona" diz quem escreve a migração que a cria.

| # | Tabela | O que guarda | Dona |
|---|---|---|---|
| 1 | `organisers` | Empresa, NIF (9 dígitos, único), email (único), telefone | M1 |
| 2 | `venues` | Nome (único), cidade, morada, capacidade máxima | M1 |
| 3 | `gates` | Portas de um local (nome único dentro do local) | M1 |
| 4 | `sections` | Secções de um local, sentadas ou standing, capacidade standing | M1 |
| 5 | `seats` | Lugares de uma secção: fila, número, acessível, visão reduzida | M1 |
| 6 | `events` | Organizador, título, categoria, idade mínima, descrição e detalhes por categoria em `jsonb` | M1 |
| 7 | `performances` | Evento, local, início, fim, abertura de vendas, estado | M1 |
| 8 | `section_prices` | Preço de cada secção em cada performance (`numeric`, nunca negativo) | M1 |
| 9 | `customers` | Nome, email (único), hash da password, data de nascimento, telefone, data de registo | M1 |
| 10 | `holds` | Reserva temporária de um cliente para uma performance, com `expires_at` | M1 |
| 11 | `hold_items` | Lugares (ou número de lugares em standing) de cada reserva. Tabela de associação | M1 |
| 12 | `orders` | Cliente, performance, estado, total, código promocional usado | M2 |
| 13 | `tickets` | Encomenda, performance, lugar ou secção, preço pago, código de 12 caracteres, estado | M2 |
| 14 | `payments` | Encomenda, montante, método, estado, data, referência do fornecedor (única) | M2 |
| 15 | `promo_codes` | Código (único), percentagem ou valor fixo, validade, evento, máximo de usos, usos atuais | M2 |
| 16 | `scan_records` | Cada leitura à porta: código lido, porta, funcionário, data, resultado | M2 |

**Decisão sobre os detalhes por categoria:** ficam numa coluna `jsonb` da tabela `events`. Assim não precisamos de mudar o esquema para cada nova categoria. A justificação vai em `docs/mongodb.md` e `docs/postgres.md`.

## 3.2 Migrações

Cada migração é um ficheiro em `postgres/migrations/`, numerado. A ordem é a do número. Os intervalos reservados são: M1 `0000` a `0009`, M2 `0010` a `0019`, M3 `0020` a `0029`.

| Ficheiro | Dono | O que faz |
|---|---|---|
| `0000_empty` | M1 | Migração vazia, só para provar que o Alembic funciona (setup S7) |
| `0001_venues_and_gates` | M1 | Cria `organisers`, `venues`, `gates` |
| `0002_sections_and_seats` | M1 | Cria `sections` e `seats` (com FK para `venues`, `ON DELETE RESTRICT`) |
| `0003_events_performances_prices` | M1 | Cria `events`, `performances`, `section_prices` |
| `0004_customers_holds` | M1 | Cria `customers`, `holds`, `hold_items` |
| `0005_constraints_venues` | M1 | UNIQUE do nome do local e da porta; CHECK do NIF (9 dígitos) e dos valores não negativos; enums de categoria, idade e estado |
| `0006_no_overlapping_performances` | M1 | EXCLUDE com `btree_gist` que impede duas performances sobrepostas no mesmo local |
| `0010_orders_tickets_payments` | M2 | Cria `orders`, `tickets`, `payments` |
| `0011_promo_codes_scan_records` | M2 | Cria `promo_codes` e `scan_records` |
| `0012_ticket_rules` | M2 | Índice parcial único em `tickets (performance_id, seat_id) WHERE status IN ('valid','used')`, para nunca vender um lugar duas vezes |
| `0013_promo_and_money_rules` | M2 | CHECK de percentagem entre 1 e 100 e de "percentagem ou valor, nunca ambos"; trigger que impede usar um código acima do máximo |
| `0014_standing_capacity` | M2 | Trigger que impede mais bilhetes `valid` ou `used` do que a capacidade de uma secção standing |
| `0020_indexes` | M3 | Índices para as queries frequentes do brief e para as FKs que justificam |
| `0021_grants` | M3 | `GRANT` para os roles app e leitura, `ALTER DEFAULT PRIVILEGES`, `REVOKE UPDATE, DELETE` em `scan_records` |

**Regra:** cada migração é pequena e tem um nome que diz o que faz. Se uma migração ficar com mais de uma responsabilidade, separa-a.

**Nota sobre o setup:** o passo 2 do `setup.sh` (S8) aplica todas as migrações como owner. Por isso, a migração `0021_grants` tem de estar pronta antes do primeiro teste de clone limpo, ou o role app não consegue ler as tabelas.

## 4. Setup do projeto (M1, ~14 h)

Estas tarefas são pré-requisito de tudo. Ficam prontas nos dois primeiros dias.

| # | Tarefa | Ficheiro(s) | Feito quando | Horas |
|---|---|---|---|---|
| S1 | Criar as pastas da raiz e o `.gitignore` | `app/`, `postgres/`, `mongodb/`, `redis/`, `scripts/`, `docs/`, `.gitignore` | As pastas existem e `.env` está no `.gitignore` | 1 |
| S2 | Criar o `.env.example` | `.env.example` | Tem todas as variáveis do `compose.yml`, com `change-me` como valor | 1 |
| S3 | Criar o `compose.yml` com os quatro serviços | `compose.yml` | `docker compose config` não dá erro e `docker compose up -d` arranca os quatro | 2 |
| S4 | Criar o Dockerfile e as dependências da app | `app/Dockerfile`, `app/requirements.txt` | `docker compose build app` termina sem erro | 1 |
| S5 | Criar o endpoint de saúde | `app/main.py` | `GET /health` devolve `{"status": "ok"}` | 1 |
| S6 | Criar a base de dados e os roles (como superuser) | `scripts/setup.sh`, passo 1 | `psql` com o role app liga-se à base `ticketing` | 2 |
| S7 | Configurar o Alembic e a primeira migração vazia | `postgres/alembic.ini`, `postgres/env.py`, `postgres/migrations/0000_empty.py` | `alembic upgrade head` corre sem erro | 2 |
| S8 | Aplicar migrações e grants (como owner) | `scripts/setup.sh`, passo 2 | Os roles app e leitura conseguem `SELECT` nas tabelas | 1 |
| S9 | Criar o utilizador, coleções e índices do MongoDB (como root) | `scripts/setup.sh`, passo 3 | `mongosh` com o utilizador da app lista a base `ticketing` | 2 |
| S10 | Configurar o Redis com password e persistência | `compose.yml` | `redis-cli ping` com a password devolve `PONG` | 1 |
| S11 | Testar o clone limpo | — | Os comandos da secção 6 correm do zero sem erro | 1 |

**Regras do `setup.sh`:**

- Corre em três passos, nesta ordem: superuser (base e roles), owner (migrações), root do Mongo (utilizador, coleções, índices).
- Pode ser corrido duas vezes seguidas sem erro.
- Lê todas as passwords do `.env`. Nada escrito no script.
- A app nunca liga como `postgres` nem `root`.

## 5. Tarefas por parte

Horas são estimativas. Cada tarefa tem um "feito quando", para saberes sem dúvida se acabou.

### Parte 1: Lugares e reservas (M1, ~48 h)

| # | Tarefa | Ficheiro(s) | Feito quando | Horas |
|---|---|---|---|---|
| 1 | Criar as tabelas base: locais, secções, lugares, organizadores, eventos, performances, preços, clientes | `postgres/migrations/0001` a `0003` | `alembic upgrade head` cria as tabelas numa base vazia | 10 |
| 2 | Criar as regras: nome de local único, lugar único por secção, performances sem sobreposição, capacidade standing | `postgres/migrations/0004` a `0006` | Inserir duas performances sobrepostas no mesmo local dá erro | 6 |
| 3 | Criar o seed de locais, lugares, eventos e performances | `postgres/seed/part1.sql` | As contagens batem com o brief | 4 |
| 4 | F1: mapa de lugares lido do Redis | `app/routes/seat_map.py` | O segundo pedido ao mesmo mapa não gera nenhum `SELECT` no log | 6 |
| 5 | F2: criar holds com todas as regras | `app/routes/holds.py` | O 7.º bilhete é recusado e o 11.º pedido no mesmo minuto é recusado | 10 |
| 6 | Guardar cada tentativa de hold no MongoDB | `mongodb/hold_attempts.py` | Cada tentativa gera um documento, e o índice TTL tem 90 dias | 5 |
| 7 | Teste de concorrência "mesmo lugar" (50 clientes) | `app/tests/test_same_seat.py` | A versão real sai com 0 e a versão ingénua sai com 1 | 4 |
| 8 | Documentar a Parte 1 | `docs/postgres.md`, secção de holds em `docs/redis.md` | Cada tabela e regra tem uma linha a explicar | 3 |

### Parte 2: Compra e bilhetes (M2, ~55 h)

| # | Tarefa | Ficheiro(s) | Feito quando | Horas |
|---|---|---|---|---|
| 1 | Criar as tabelas: encomendas, bilhetes, pagamentos, códigos promocionais, check-ins | `postgres/migrations/0010` a `0012` | `alembic upgrade head` cria as tabelas sem erro | 10 |
| 2 | Criar as regras: bilhete único por lugar, limite de códigos, valores não negativos, sem UPDATE nem DELETE nos check-ins | `postgres/migrations/0013` a `0015` | Um bilhete duplicado para o mesmo lugar dá erro | 6 |
| 3 | F3: checkout com pagamento simulado e código promocional | `app/routes/checkout.py` | Pagar com `simulate=approved` cria bilhetes `valid`, e `declined` mantém a encomenda `pending` | 10 |
| 4 | F4 e F6: cancelar encomenda e cancelar performance | `app/routes/cancel.py` | O reembolso cria um pagamento `refunded` e os bilhetes ficam `cancelled` | 6 |
| 5 | F5: check-in | `app/routes/checkin.py` | Bilhete já usado é recusado, e cada leitura fica registada | 4 |
| 6 | Contadores e lista "trending now" no Redis | `redis/trending.lua` | Cada venda atualiza os contadores | 4 |
| 7 | Coleção de vendas por performance no MongoDB, com exportação e pipeline do relatório 1 | `mongodb/sales.py`, `mongodb/pipelines/report1.json` | O pipeline devolve vendas e receita por secção | 5 |
| 8 | Testes de concorrência "últimos lugares" (100 clientes) e código promocional | `app/tests/test_last_places.py`, `app/tests/test_promo.py` | Em 10 lugares, exatamente 10 pagamentos passam | 4 |
| 9 | Seed de encomendas, pagamentos, bilhetes e check-ins | `postgres/seed/part2.sql` | Os volumes batem com o brief | 6 |
| 10 | Documentar a Parte 2 | `docs/concurrency.md` (parte 2) | Cada cenário tem a explicação do mecanismo | 3 |

### Parte 3: Dados e relatórios (M3, ~47 h)

| # | Tarefa | Ficheiro(s) | Feito quando | Horas |
|---|---|---|---|---|
| 1 | Criar os índices e três `EXPLAIN (ANALYZE, BUFFERS)`, com e sem índice | `postgres/migrations/0020`, `docs/postgres.md` | Cada índice tem uma query que o justifica | 6 |
| 2 | Fazer o `seed.sh` que chama o seed de PostgreSQL, a exportação e o rebuild | `scripts/seed.sh` | Corre do início ao fim em menos de 5 minutos | 4 |
| 3 | Exportar PostgreSQL para MongoDB, com o role de leitura | `mongodb/export_reports.py` | Corre duas vezes sem erro e atualiza as coleções | 4 |
| 4 | Pipelines dos relatórios 2 a 6 e validadores das coleções de relatório | `mongodb/pipelines/report2.json` a `report6.json` | Cada pipeline devolve dados e tem amostra em `docs/mongodb.md` | 8 |
| 5 | Redis: script de rebuild, script de verificação e prova de cache | `redis/rebuild.py`, `redis/verify.py` | Após `FLUSHALL`, rebuild e verify saem com 0 | 6 |
| 6 | F7: endpoints dos relatórios | `app/routes/reports.py` | Cada endpoint devolve JSON | 4 |
| 7 | Runner de concorrência | `scripts/run_concurrency.py` | Imprime modo, sucessos, recusas e 5xx, e sai com 0 ou 1 | 5 |
| 8 | Documentar mongo, redis e runbook | `docs/mongodb.md`, `docs/redis.md`, `docs/runbook.md` | Os três documentos existem e cada chave e coleção está descrita | 10 |

### Trabalho comum (cada pessoa, ~6 h)

- `README.md`: como correr, tabela de autores, stack e porquê, lista de endpoints.
- `docs/architecture.md`: que motor é fonte de verdade de cada dado, e o que acontece se a escrita no segundo motor falhar.
- `docs/ai-usage.md`: uma entrada por uso de IA relevante, e a declaração no fim.
- Revisão dos PRs dos outros.

### Totais

| Pessoa | Setup | Parte | Trabalho comum | Total |
|---|---|---|---|---|
| M1 | 14 | 48 | 6 | ~68 h |
| M2 | — | 55 | 6 | ~61 h |
| M3 | — | 47 | 6 | ~53 h |

M1 tem mais trabalho por causa do setup. Se for preciso equilibrar, M3 pode passar a fazer o seed de locais (tarefa 3 da Parte 1, 4 h).

## 6. Como correr o projeto de um clone limpo

Estes são os comandos que o README vai ter. Quem clonar o repositório deve conseguir correr tudo apenas com Docker e uv.

```bash
cp .env.example .env
docker compose up -d
./scripts/setup.sh
./scripts/seed.sh
```

Depois, o teste de concorrência com o comando que estiver no README.

## 7. Git

Cada pessoa precisa de commits próprios e não triviais em **cada uma** destas áreas:

| Área | Caminho |
|---|---|
| PostgreSQL | `postgres/` |
| MongoDB | `mongodb/` |
| Redis | `redis/` |
| App | `app/` |

Com a divisão por partes, cada pessoa já toca nas quatro. Mesmo assim, verifica antes da entrega (substituir o email e a tag):

```bash
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- postgres/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- mongodb/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- redis/ | wc -l
git log v1.0.0 --no-merges --author="email@example.com" --oneline -- app/ | wc -l
```

Não contam: merges, linhas `Co-authored-by`, commits só de formatação, e commits com email que não está na tabela de autores. Penalização: −2 pontos por área em falta.

- **Desativar squash merge:** Settings → General → Pull Requests → desmarcar "Allow squash merging".
- **Nunca** fazer `git push --force` no `main`.

## 8. Ordem de trabalho

| Semana | M1 | M2 | M3 |
|---|---|---|---|
| 1 | Setup S1 a S11 | Ler o contrato. Rascunho das tabelas de compra | Ler o contrato. Rascunho dos índices e dos pipelines |
| 2 | Migrações base (Parte 1, tarefas 1 e 2). F1 e F2 | Migrações de compra (tarefas 1 e 2). F3 | Exportação (tarefa 3). Primeiro pipeline (tarefa 4) |
| 3 | Teste "mesmo lugar" (tarefa 7) | F4, F5, F6 e trending (tarefas 4 a 6) | F7, rebuild e verify do Redis (tarefas 5 e 6). `seed.sh` (tarefa 2) |
| 4 | Revisão dos PRs | Testes "últimos lugares" e código promocional (tarefa 8) | Runner de concorrência (tarefa 7) |
| Sessões 17–18 | Documentação da Parte 1 e verificação de commits | Documentação da Parte 2 e verificação de commits | Documentação das coleções e do runbook |
| Antes da sessão 19 | Clone limpo | Clone limpo | Cronometrar o seed. Tag `v1.0.0` |

## 9. Riscos

- **M2 espera pelas tabelas base de M1.** Mitigação: M1 entrega as migrações base até ao fim do dia 2.
- **Seed lento.** Mitigação: usar `COPY` e medir cedo com volumes pequenos.
- **Concorrência difícil de reproduzir.** Mitigação: começar com 5 clientes e só depois 50 e 100.
- **Documentação no fim.** Mitigação: cada pessoa escreve a documentação da sua parte enquanto programa.
- **Estimativas baixas.** Revê as horas no fim da semana 1.

## 10. Checklist final

- [ ] Clone limpo: `cp .env.example .env`, `docker compose up -d`, `./scripts/setup.sh`, `./scripts/seed.sh`.
- [ ] `setup.sh` corre duas vezes seguidas sem erro.
- [ ] Migrações aplicam-se a uma base vazia.
- [ ] Seed em menos de 5 minutos, com as constraints ativas.
- [ ] F1 a F7 funcionam através da app.
- [ ] `FLUSHALL`, rebuild e verify do Redis saem com 0.
- [ ] Três pipelines do Mongo a correr, com amostras em `docs/mongodb.md`.
- [ ] Três `EXPLAIN` com e sem índice.
- [ ] A app não liga como `postgres` nem `root`.
- [ ] Sem passwords reais no Git (`git log -p | grep -i password`).
- [ ] Os 8 documentos obrigatórios existem, incluindo `docs/ai-usage.md` com a declaração.
- [ ] Cada pessoa tem commits não triviais nas quatro áreas.
- [ ] Squash merge desativado.
- [ ] Tag SemVer enviada antes da sessão 19.