# Gestão do grupo: Projeto A (Ticketing)

Ficheiro interno da equipa. Não é entregue ao formador. Os documentos do projeto (`README.md`, `docs/*.md`) são escritos em inglês; este ficheiro pode ser em português.

## 1. Equipa

| Nome | Utilizador GitHub | Email de `git config user.email` |
|---|---|---|
| Dinis | dinobuefixe | |
| Sabrina | sabsushi | |
| Cris | CrisAxe | |

O email tem de ser o mesmo em todas as máquinas de onde cada um faz commits. O formador verifica commits por este email.

## 2. Datas

- Início do projeto: quando recebermos o brief.
- Sessões 17 e 18: trabalho em aula.
- Sessão 19: 11/11 (confirmar com o formador).
- **Tag de entrega** (SemVer, ex.: `v1.0.0`): empurrada **antes** do início da sessão 19. Commits e tags depois disso não contam.

## 3. Regras de trabalho

- **Responsabilidade partilhada.** Ninguém é dono de um motor. Cada membro escreve código e schema em PostgreSQL, MongoDB, Redis e na app.
- Cada tarefa tem um **responsável** e um **revisor**. Os papéis rodam, para que cada membro seja responsável por pelo menos uma tarefa em cada área.
- Cada membro tem de explicar aos outros as partes que não escreveu antes da sessão 18.
- Ninguém faz `git push --force` no `main` depois de outros terem feito push.
- Squash merge desativado: Settings → General → Pull Requests → desmarcar "Allow squash merging".
- Usar merge commit ou rebase and merge nos PRs.

## 4. Git: o que conta

Cada membro precisa de commits próprios e não triviais em cada uma destas áreas:

| Área | Caminhos |
|---|---|
| PostgreSQL | `postgres/` |
| MongoDB | `mongodb/` |
| Redis | `redis/` |
| App | `app/` |

- Não contam: merges, linhas `Co-authored-by`, commits só de formatação, comentários, nomes de ficheiros ou ficheiros gerados, e commits com email fora da tabela.
- Commits em `docs/`, `scripts/` ou na raiz são bem-vindos, mas não contam para nenhuma área.
- Penalização: −2 pontos por área em falta, por membro.


## 5. Estrutura do repositório

Na raiz, obrigatoriamente:

```
compose.yml
.env.example
.gitignore          (inclui .env)
README.md
app/
postgres/
mongodb/
redis/
scripts/            (setup.sh, seed.sh, outros)
docs/
```

Podemos acrescentar pastas, mas não mover estas.

## 6. Requisitos técnicos (checklist)

### Geral
- [ ] Stack escolhida e justificada no README: FastAPI, SQLAlchemy com Alembic, pymongo e redis-py.
- [ ] Tudo a correr com `docker compose`. Comandos do README funcionam só com Docker e uv.
- [ ] Portas 5432, 27017 e 6379. Parar o ambiente do módulo antes.
- [ ] Clone limpo: `cp .env.example .env` → `docker compose up -d` → `./scripts/setup.sh` → `./scripts/seed.sh` → teste de concorrência.
- [ ] Sem passwords no Git (`git log -p | grep -i password` sem resultados reais).

### PostgreSQL
- [ ] Pelo menos 10 tabelas, em 3FN. Desnormalizações escritas em `docs/postgres.md`.
- [ ] `numeric` para dinheiro, `timestamptz` para momentos, `date` para dias, enums com CHECK ou tabela de referência.
- [ ] Toda a tabela tem PK. Toda a relação tem FK com `ON DELETE` justificado. N:N com tabela de associação.
- [ ] Regras da lista "Where the rules are enforced" (primeira lista) impostas pela base de dados: UNIQUE, CHECK, EXCLUDE, índice parcial único, trigger ou REVOKE.
- [ ] Regras da segunda lista: onde são impostas (base de dados ou app) está escrito em `docs/postgres.md`.
- [ ] Migrações do zero: Alembic, com SQL cru para CHECK, EXCLUDE, triggers e grants. Nada de `create_all()` nem SQL manual no psql.
- [ ] Três `EXPLAIN (ANALYZE, BUFFERS)` com e sem índice, em pelo menos 3 queries frequentes, nenhuma servida só por PK ou UNIQUE. Feito com `DROP INDEX` dentro de transação revertida.
- [ ] Indexação de FKs documentada (quais e porquê).
- [ ] Transação crítica documentada em `docs/concurrency.md` (nível de isolamento e locks).
- [ ] Três papéis: owner (migrações), app (sem superuser, sem CREATE, sem DROP, sem UPDATE/DELETE onde for append-only), leitura (relatórios e exportação). Criados pelo `setup.sh`.
- [ ] Registos de check-in nunca atualizados nem apagados pelo role da app.

### MongoDB
- [ ] Pelo menos 3 coleções. Para cada uma, `docs/mongodb.md` diz o que guarda, porque está no MongoDB, se é fonte de verdade ou derivada, e um exemplo de documento.
- [ ] Validador `$jsonSchema` com `validationLevel: "strict"` e `validationAction: "error"` em todas.
- [ ] Decisão embed/referência documentada para cada relação.
- [ ] Índices para as queries da app e dos pipelines, incluindo TTL de 90 dias no registo de tentativas de hold.
- [ ] `explain("executionStats")` com e sem índice, pelo menos numa query.
- [ ] Exportação PostgreSQL → MongoDB (`mongodb/`) com o role de leitura. Corre no seed e pode ser repetida.
- [ ] Pelo menos 3 pipelines de agregação guardadas em `mongodb/`, cada uma com a pergunta e uma amostra de output em `docs/mongodb.md`.
- [ ] Utilizador da app com `readWrite` só na base do projeto. Root só no `setup.sh`.

### Redis
- [ ] Convenção de nomes de chaves em `docs/redis.md` (ex.: `event:{performance_id}:seats`).
- [ ] Para cada padrão: estrutura, exemplo, TTL (ou razão para não ter), comandos, classe (fonte de verdade, derivada ou efémera).
- [ ] TTL definido atomicamente (`SET ... EX` ou MULTI/EXEC). Nunca em dois comandos separados.
- [ ] Script de rebuild (`redis/`) que recria as chaves derivadas a partir de PostgreSQL ou MongoDB.
- [ ] Script de verificação que sai com 1 se houver diferenças e 0 se não houver.
- [ ] `seed.sh` popula o Redis pelo rebuild, não diretamente.
- [ ] Prova de cache para os fluxos marcados "read from Redis": output de `MONITOR` ou log da app, ao lado do log do PostgreSQL (`log_statement = 'all'`) sem queries para esse pedido. Em `docs/redis.md`.
- [ ] `requirepass` com password vinda do `.env`.
- [ ] Limites por minuto com janela fixa: `INCR` + `EXPIRE` no mesmo MULTI/EXEC ou Lua.

### Concorrência
- [ ] Versão ingénua que mostra a condição de corrida, e versão real que mantém a regra.
- [ ] Teste através da API. Fixtures que reiniciam o estado antes de cada execução.
- [ ] Pedidos recusados por regra devolvem 4xx (409 normalmente) com mensagem. Qualquer 5xx conta como falha no modo real.
- [ ] Saída por cenário: modo, sucessos, recusas, 5xx e se a regra se mantém. Sai com 1 se a regra falhar ou houver 5xx.
- [ ] `docs/concurrency.md` com 3 execuções por cenário e modo. Dois cenários = 12 saídas.

### App (mini app)
- [ ] Implementa todos os fluxos obrigatórios do brief: F1 a F7.
- [ ] Usa os três motores nos fluxos, como descrito em `docs/architecture.md`.
- [ ] Corre como serviço(s) no `compose.yml` (API, worker ou ambos).
- [ ] Endpoints documentados: OpenAPI ou lista no README com um `curl` por endpoint.
- [ ] Quem age é indicado por id (caminho, corpo ou header `X-User-Id`). Escolher uma forma e usar em todo o lado.
- [ ] Sem autenticação.
- [ ] Queries parametrizadas em SQL e MongoDB. Sem f-strings com input do pedido.
- [ ] Datas, horas e "hoje" em `Europe/Lisbon`. Momentos em `timestamptz`.
- [ ] Estados que mudam com o tempo (hold expira, performance começa): calculados na leitura, por worker, ou ambos. Escrito em `docs/architecture.md`.
- [ ] Pagamento simulado com `simulate=approved|declined`.
- [ ] Liga-se ao PostgreSQL com o role da app, ao MongoDB com o user `readWrite`, e ao Redis com password. Nunca como `postgres` ou `root`.

### Seed
- [ ] `scripts/seed.sh` carrega PostgreSQL e MongoDB, corre a exportação e o rebuild do Redis.
- [ ] Volumes do brief (ver secção 7).
- [ ] Determinístico (semente fixa). Dois clones limpos produzem os mesmos dados.
- [ ] Datas relativas ao dia em que corre.
- [ ] Dados realistas e não uniformes (alguns clientes compram muito mais, alguns eventos vendem muito mais).
- [ ] Respeita todas as constraints e regras. Não desativa triggers nem constraints.
- [ ] Corre em menos de 5 minutos. Usar `COPY` ou inserções em lote.

### Segurança e runbook
- [ ] `docs/architecture.md` tem secção de segurança: roles, users, o que podem fazer e porquê.
- [ ] `docs/runbook.md`: para cada motor, o que é copiado, com que frequência, com que ferramenta, onde fica, comandos exatos de backup e restauro, como se verifica o restauro, RTO e RPO justificados pelo negócio.
- [ ] Redis: decidir se se faz backup ou se se reconstrói, e porquê.
- [ ] Explicar o que se perde de vez se cada motor desaparecer.

## 7. Volumes do seed

| Dado | Volume |
|---|---|
| Locais | 30, em pelo menos 8 cidades |
| Lugares | ~150.000 + secções de lotação |
| Organizadores | 200 |
| Eventos | 1.500 |
| Performances | 4.000 (de 12 meses atrás a 6 meses à frente) |
| Clientes | 100.000 |
| Encomendas | ~450.000 |
| Bilhetes | pelo menos 1.000.000 |
| Pagamentos | um por encomenda paga, mais recusados e reembolsos |
| Check-ins | a maioria dos bilhetes de performances passadas |
| Registo de tentativas (Mongo) | pelo menos 50.000 documentos nos últimos 90 dias |

## 8. Documentos obrigatórios

Todos com este nome exato, em inglês.

| Ficheiro | Responsável principal | Revisor | Estado |
|---|---|---|---|
| `README.md` | | | |
| `docs/postgres.md` | | | |
| `docs/mongodb.md` | | | |
| `docs/redis.md` | | | |
| `docs/architecture.md` | | | |
| `docs/concurrency.md` | | | |
| `docs/runbook.md` | | | |
| `docs/ai-usage.md` | | | |

O `README.md` tem: descrição do projeto, como correr de um clone limpo, como correr o teste de concorrência, stack e porquê, ER em Mermaid, lista de endpoints ou link para OpenAPI, como se indica quem age, tabela de autores e links para `docs/`.

**`docs/ai-usage.md`**: uma entrada por uso relevante de IA, com: quem, ferramenta e modelo, para quê, o que se manteve, o que se mudou, o que se rejeitou e porquê, como se verificou, e erros encontrados. Termina com a declaração:

> We, [Membro 1], [Membro 2] and [Membro 3], declare that we understand and can explain all the code, schemas and documents in this repository, including those produced with the help of AI tools.

## 9. Concorrência: cenários obrigatórios

1. **Mesmo lugar** (F2 e depois F3): 1 performance `on_sale`, 50 clientes, todos pedem o mesmo lugar ao mesmo tempo. Exatamente 1 hold com sucesso e 49 recusados. O vencedor paga com `simulate=approved`. No fim, exatamente 1 bilhete `valid` para esse lugar.
2. **Últimos lugares** (F2 e F3): secção standing com 10 lugares livres, 100 clientes, cada um reserva 1 e paga logo. No fim, exatamente 10 encomendas `paid` e exatamente tantos bilhetes `valid` como a capacidade.
3. Opcional: código promocional usado no máximo de vezes.

Começar sempre com 5 clientes e só depois 50 e 100.

## 10. Tarefas por elemento

O README proíbe que um membro seja dono de um motor. Por isso, as tarefas estão agrupadas por elemento, mas cada uma tem um **responsável** e um **revisor**. Cada tarefa tem também um **número de ordem** global (1 a 35), que indica a sequência em que deve ser feita. Tarefas com o mesmo número de semana podem ser feitas em paralelo.

Membros: **Dinis**, **Sabrina** e **Cris** (substituir pelos nomes reais na tabela de autores).

As horas são estimativas e tendem a estar abaixo do real.

### PostgreSQL (66 h: Dinis 22, Sabrina 20, Cris 24)

| Ordem | Tarefa | Horas | Responsável | Revisor |
|---|---|---|---|---|
| 1 | Modelo ER e lista de tabelas (3FN, tipos, chaves) | 6 | Dinis | Sabrina |
| 6 | Migrações do esquema (10+ tabelas, FKs com ON DELETE justificado) | 10 | Sabrina | Cris |
| 7 | Constraints: UNIQUE, CHECK, NIF, enums, valores não negativos | 10 | Cris | Dinis |
| 13 | EXCLUDE de sobreposição e triggers de capacidade standing | 8 | Dinis | Sabrina |
| 8 | Roles e grants (owner, app, leitura) e REVOKE nos registos de check-in | 4 | Sabrina | Cris |
| 14 | Transações de checkout e de cancelamento/reembolso | 10 | Cris | Dinis |
| 17 | Seed de PostgreSQL com COPY e volumes do brief | 8 | Dinis | Cris |
| 22 | Índices e EXPLAIN (ANALYZE, BUFFERS) com e sem índice | 6 | Sabrina | Dinis |
| 30 | `docs/postgres.md` e parte PostgreSQL de `docs/concurrency.md` | 4 | Cris | Sabrina |

### MongoDB (26 h: Dinis 10, Sabrina 10, Cris 6)

| Ordem | Tarefa | Horas | Responsável | Revisor |
|---|---|---|---|---|
| 3 | Desenho das coleções e decisão embed/referência | 4 | Dinis | Sabrina |
| 9 | Validadores `$jsonSchema` (strict, error) e índices, incluindo TTL de 90 dias | 5 | Sabrina | Cris |
| 18 | Exportação PostgreSQL → MongoDB com o role de leitura | 6 | Dinis | Cris |
| 20 | 3 pipelines de agregação em `mongodb/`, com amostras de output | 6 | Cris | Dinis |
| 19 | Seed do registo de tentativas de hold (50.000+ documentos) | 2 | Sabrina | Dinis |
| 29 | `docs/mongodb.md` | 3 | Sabrina | Cris |

### Redis (18 h: Dinis 6, Sabrina 6, Cris 6)

| Ordem | Tarefa | Horas | Responsável | Revisor |
|---|---|---|---|---|
| 4 | Convenção de chaves e classificação (fonte, derivada, efémera) | 3 | Sabrina | Dinis |
| 10 | Holds com TTL atómico e contador de 10 tentativas por minuto | 6 | Cris | Sabrina |
| 16 | Script de rebuild e script de verificação | 4 | Dinis | Cris |
| 27 | Prova de cache (MONITOR e log do PostgreSQL) | 2 | Dinis | Sabrina |
| 28 | `requirepass` e `docs/redis.md` | 3 | Sabrina | Cris |

### FastAPI (47 h: Dinis 16, Sabrina 16, Cris 15)

| Ordem | Tarefa | Horas | Responsável | Revisor |
|---|---|---|---|---|
| 2 | Estrutura da app e `compose.yml` com os serviços | 5 | Dinis | Sabrina |
| 5 | Ligações aos três motores, configuração por `.env` | 3 | Sabrina | Cris |
| 11 | F1: mapa de lugares lido do Redis | 4 | Sabrina | Dinis |
| 12 | F2: holds com todas as regras | 6 | Dinis | Cris |
| 15 | F3: checkout com pagamento simulado e código promocional | 6 | Sabrina | Dinis |
| 23 | F4 e F6: cancelamentos e reembolsos | 5 | Cris | Sabrina |
| 24 | F5: check-in | 3 | Sabrina | Cris |
| 25 | Listagem de encomendas (20 por página) | 2 | Dinis | Sabrina |
| 26 | F7: endpoints dos relatórios | 3 | Dinis | Cris |
| 31 | Testes de concorrência, versão ingénua e versão real | 8 | Cris | Dinis |
| 32 | Documentação de endpoints (OpenAPI ou lista no README) | 2 | Cris | Sabrina |

### Transversal (24 h: Dinis 8, Sabrina 8, Cris 8)

| Ordem | Tarefa | Horas | Responsável | Revisor |
|---|---|---|---|---|
| 21 | `setup.sh` e `seed.sh` (orquestração, seed abaixo de 5 min) | 6 | Dinis | Sabrina |
| 33 | Runbook, RTO/RPO e secção de segurança em `docs/architecture.md` | 6 | Sabrina | Cris |
| 34 | `README.md` e `docs/ai-usage.md` | 6 | Cris | Dinis |
| 35 | Git, revisões cruzadas e integração final | 6 | Todos (2 h cada) | — |

### Resumo por pessoa

| Pessoa | PostgreSQL | MongoDB | Redis | FastAPI | Transversal | Total |
|---|---|---|---|---|---|---|
| Dinis | 22 | 10 | 6 | 16 | 8 | 62 h |
| Sabrina | 20 | 10 | 6 | 16 | 8 | 60 h |
| Cris | 24 | 6 | 6 | 15 | 8 | 59 h |

### Sequência global

Os números de ordem seguem esta sequência, respeitando as dependências:

1. **Semana 1 (fundações):** 1 modelo ER, 2 estrutura e `compose.yml`, 3 desenho das coleções, 4 convenção de chaves Redis.
2. **Semana 2 (esquema e primeiras regras):** 5 ligações aos motores, 6 migrações, 7 constraints, 8 roles, 9 validadores MongoDB, 10 holds com TTL, 11 F1, 12 F2, 13 EXCLUDE e triggers.
3. **Semana 3 (compra e dados):** 14 transações de checkout e cancelamento, 15 F3, 16 rebuild e verificação do Redis, 17 seed PostgreSQL, 18 exportação para MongoDB, 19 seed do registo de tentativas, 20 pipelines, 21 `setup.sh` e `seed.sh`.
4. **Semana 4 (cancelamentos, concorrência e índices):** 22 índices e EXPLAIN, 23 F4 e F6, 24 F5, 25 listagem de encomendas, 26 F7, 27 prova de cache, 28 `requirepass`, 31 testes de concorrência.
5. **Sessões 17 e 18 (documentação e revisão):** 29 `docs/mongodb.md`, 30 `docs/postgres.md`, 32 documentação de endpoints, 33 runbook, 34 `README.md` e `docs/ai-usage.md`, 35 Git e integração.
6. **Antes da sessão 19:** clone limpo, cronometrar o seed e enviar a tag SemVer.

## 11. Riscos

- **Esquema tardio.** Se o schema não estiver fechado cedo, bloqueia a app e o Redis. Fechar a primeira versão na semana 1.
- **Commits desequilibrados.** Verificar as quatro áreas por membro a cada semana, não só no fim.
- **Seed lento ou com constraints desligadas.** Testar cedo com volume reduzido e medir o tempo.
- **Concorrência difícil de reproduzir.** Começar com 5 clientes.
- **Documentação no fim.** Escrever cada documento junto com o código a que diz respeito.
- **Discussão individual.** Cada membro tem de conseguir explicar qualquer ficheiro, não só o que escreveu.

## 12. Checklist final

- [ ] Projeto a correr de um clone limpo com os comandos do README, só com Docker e uv.
- [ ] Migrações aplicam-se a uma base vazia, pelo role owner.
- [ ] Seed em menos de 5 minutos, com constraints ativas, exportação e rebuild do Redis.
- [ ] Todos os fluxos obrigatórios funcionam através da app.
- [ ] Regras da primeira lista impostas pelo PostgreSQL.
- [ ] `FLUSHALL` → rebuild → verify sai com 0.
- [ ] Prova de cache em `docs/redis.md`.
- [ ] 3 pipelines a correr, com output em `docs/mongodb.md`.
- [ ] Pelo menos 3 `EXPLAIN` com e sem índice.
- [ ] A app não liga como `postgres` nem `root`.
- [ ] Sem passwords reais no histórico do Git.
- [ ] Todos os 8 documentos existem e estão completos, incluindo a declaração.
- [ ] Cada membro tem commits não triviais nas quatro áreas.
- [ ] Squash merge desativado.
- [ ] Tag SemVer enviada antes da sessão 19.