# CLAUDE.md — Backend do DOGGO

Backend Django + Django REST Framework do **DOGGO — Dog Services**, uma plataforma que conecta tutores de cães a
passeadores. O foco do produto é o Dog Walking.

Antes de qualquer tarefa, leia o `contexto.md` na raiz do workspace (visão do produto, estados do serviço, regras
de avaliação, WebSocket, variáveis de ambiente). O código e os testes são a referência final: confira-os antes de
afirmar que algo existe.

## Estrutura

```text
doggo-backend/
├── app/               # settings.py (por variáveis de ambiente), env.py, urls.py, asgi.py, pagination.py
├── core/              # todo o domínio
│   ├── models/        # um arquivo por entidade, exportado no __init__.py
│   ├── serializers/   # idem
│   ├── views/         # idem (ViewSets e APIViews)
│   ├── services/      # regras de negócio: service_flow, booking, service_events, redis_service, location_service
│   ├── repositories/  # acesso ao banco do fluxo assíncrono de localização (LocationRepository)
│   ├── consumers/     # WebSocket do passeio (ServiceConsumer) + routing.py
│   ├── middleware/    # autenticação JWT do WebSocket (token na query string)
│   ├── validators/    # CPF
│   ├── utils/         # cálculos geográficos (haversine, path_distance)
│   ├── permissions.py # permissões de objeto
│   ├── admin.py
│   └── tests/         # testes e helpers
├── uploader/          # imagens e documentos enviados (app próprio)
├── scripts/           # utilitários (cria_api.py, simulate_walk.py, set_my_ip.py)
└── pyproject.toml
```

- Código novo de domínio vai em `core/`. **Não crie apps Django novos.** Não crie camadas novas (`use_cases/` etc.)
  sem necessidade concreta.
- **Regras de negócio ficam em `core/services/`**, não nas views. As views validam a entrada, aplicam permissões e
  delegam. A máquina de estados do passeio vive em `core/services/service_flow.py`.
- Fluxo de uma API: **Model → Serializer → ViewSet → Router → URL** (`router.register(...)` em `app/urls.py`).
- Nos `__init__.py`, mantenha o estilo `from .x import A, B`. O ruff ignora esses arquivos; não rode `--fix` neles.
  Tudo que for criado em `models/`, `serializers/` ou `views/` deve ser exportado no `__init__.py` correspondente.
- Mensagens de erro da API em português.

## Comandos (do `pyproject.toml`)

Use PDM. Confira `pyproject.toml` antes de assumir um comando.

| Comando | O que faz |
|---|---|
| `pdm test` | `python manage.py test` — a suíte inteira |
| `pdm check` | `ruff check` — lint (só verifica) |
| `pdm format` | `ruff format` no projeto inteiro. **Antes** roda `ruff check --fix` em tudo; evite, e formate só os seus arquivos |
| `pdm dev` | `runserver`. **Antes** roda `scripts/set_my_ip.py`, que reescreve a linha `MY_IP` do `.env` |
| `pdm serve` | Daphne em `0.0.0.0:8000` (ASGI: HTTP + WebSocket), como em produção |
| `pdm migrate` | `migrate`. **Antes** roda `makemigrations`; **depois** gera o diagrama `core.png` (`graph_models`) |
| `pdm createsuperuser`, `pdm shell`, `pdm shellp` | utilitários do Django |
| `pdm loaddata`, `pdm dumpdata` | importa `core.json` / exporta dados |
| `pdm cria_api` | gerador de API (`scripts/cria_api.py`) |

Cuidados:

- Para subir o servidor **sem** mexer no `.env`: `pdm run python manage.py runserver`.
- Nunca sobrescreva o `.env`. Variáveis novas vão para `.env.exemplo`.
- As configurações **não carregam** sem `SECRET_KEY`, a menos que `DEBUG` esteja ligado (aí usa uma chave insegura de
  desenvolvimento). Em um shell sem `.env`, use por exemplo `DEBUG=True pdm test` (bash) ou
  `$env:DEBUG='True'; pdm test` (PowerShell).
- `db.sqlite3`, `dump.json` e `media/` não são versionados nesta branch (estão no `.gitignore`). Nunca apague,
  restaure ou sobrescreva o `db.sqlite3` de alguém; os testes usam banco próprio e não o tocam.
- **Backup antes de trocar de branch ou fazer merge.** Branches que ainda versionam esses arquivos (por exemplo
  `main` e `REFACTOR-34`) sobrescrevem `db.sqlite3`, `dump.json` e `media/` no `git checkout`; voltar para esta
  branch os apaga, e o merge desta branch os remove de quem não os modificou. Antes de um `checkout` para essas
  branches ou de um merge, copie os três para fora do repositório. O histórico antigo não foi reescrito: ele ainda
  contém esses arquivos, com dados pessoais e hashes de senha.
- Variáveis de ambiente (`DEBUG`, `SECRET_KEY`, `MODE`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `AUTH_THROTTLE_RATE`, `NUM_PROXIES`...): `contexto.md`, seção 11.2.
- `NUM_PROXIES` (padrão `0` com `DEBUG` ligado, `1` com `DEBUG` falso) diz ao DRF quantos proxies reversos há na frente
  da aplicação; é o que impede forjar `X-Forwarded-For` para escapar do throttle de login e cadastro. Em produção
  atrás de um único proxy, mantenha `1`.
- Teste pelo celular/LAN: o `MY_IP` (gravado no `.env` por `pdm dev`) só é aceito com `DEBUG=True`; nesse caso entra em
  `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` (`http://<MY_IP>:5173`). Com `DEBUG` falso é ignorado.
- `SECRET_KEY` também é exigida no build de produção (`build.sh` roda `collectstatic`), não só na execução.

## Model

- Classe no singular; campos no singular. `__str__` sempre.
- `ForeignKey` com `on_delete` pensado: `CASCADE` (filho some com o pai), `PROTECT` (histórico não pode sumir) ou
  `SET_NULL` + `null=True, blank=True`. Sempre `related_name`. Serviços, avaliações e pagamentos usam `PROTECT`.
- Opções fixas com `models.TextChoices`/`IntegerChoices` dentro do model (ex.: `Service.Status`).
- Unicidade com `Meta.constraints = [models.UniqueConstraint(...)]` ou `OneToOneField` (ex.: `Review.service`).
- Depois de mudar um model: `pdm run python manage.py makemigrations` e revise o arquivo gerado. Prefira migrations
  aditivas e nunca apague ou reescreva migrations existentes.
- O usuário (`core.User`) entra por **email**; **não existe campo `role`**. Os perfis são `user.client_profile` (tutor)
  e `user.provider_profile` (passeador), e a mesma conta pode ter os dois.

## Serializers

- `fields` sempre explícito (tupla); nada de `'__all__'` em código novo.
- Serializers separados por finalidade quando o contrato muda (lista, detalhe, escrita). Ex.: `ProviderSerializer`
  (lista), `ProviderDetailSerializer` (detalhe público, sem email, telefone nem serviços) e `ProviderRegisterSerializer`
  (escrita).
- Campo exibido mas não gravável: `read_only=True`. Campos de privilégio (`is_staff`, `is_superuser`, `groups`...)
  são sempre somente leitura.
- Gravação em mais de uma tabela: `@transaction.atomic`.
- Validação com `validate_<campo>` e `validate(self, attrs)`, levantando `ValidationError` em português.
- Ação customizada com entrada própria: `Serializer` dedicado (ex.: `ServiceRateSerializer`).
- Nunca aceite do frontend id de autor, dono ou permissão como prova de autorização.

## ViewSets e autorização

```python
class XViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, XPermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']  # restrinja o que não deve existir

    def get_queryset(self):       # SEMPRE restringe ao que o usuário pode ver
        ...
```

Padrão de autorização do DOGGO:

1. **Participação filtra o queryset.** `get_queryset` devolve só o que o usuário pode ver (ex.: serviços em que ele é
   tutor ou passeador). Quem não participa recebe **404**, em qualquer ação.
2. **Papel errado é 403.** O participante sem o papel exigido naquele recurso (ex.: o tutor tentando `confirm`)
   recebe **403**. O papel vale **por serviço**, não é global.
3. **Estado inválido é 409.** Transição inválida para o status atual, fora da janela do `start` ou conflito de agenda
   recebe **409** (`Conflict`, em `service_flow.py`), com mensagem em português.
4. **Exclusão bloqueada é 409.** Registro com vínculos `PROTECT` (serviços, avaliações, pagamentos): capture
   `ProtectedError` e levante `Conflict`. Nunca deixe estourar 500.
5. Recursos públicos de leitura (prestadores, tipos de serviço) usam permissões de objeto (`IsProfileOwnerOrReadOnly`)
   ou `AllowAny` só na leitura; a escrita é do dono ou da equipe.

Outras regras:

- Ações extras: `@action(detail=True|False, methods=[...])` + `@extend_schema(...)` com `request` e `responses`.
- Filtros: valide parâmetros (ex.: `provider_id` não numérico é 400) e evite N+1 com `select_related` /
  `prefetch_related` / `annotate`.
- Dados privados não vão para serializers públicos (email, telefone, localização de clientes).
- Atualize a documentação OpenAPI (`@extend_schema`) quando mudar um contrato.

## Fluxo do passeio (`core/services/service_flow.py`)

Status (`Service.Status`, inteiros; compare sempre com `Service.Status.<NOME>`, nunca com string):
1 Em análise, 2 Confirmado, 3 Em andamento, 4 Concluído, 5 Cancelado, 6 Recusado.

| Ação | Rota | De → Para | Quem |
|---|---|---|---|
| `confirm` | `POST /api/services/{id}/confirm/` | 1 → 2 | passeador do serviço |
| `reject` | `POST .../reject/` | 1 → 6 | passeador |
| `cancel` | `POST .../cancel/` | 1 ou 2 → 5 | tutor ou passeador |
| `start` | `POST .../start/` | 2 → 3, de 30 min antes do início até o fim agendado | passeador |
| `complete` | `POST .../complete/` | 3 → 4 | passeador |
| `rate` | `POST .../rate/` | 4 (sem mudar status) | tutor, uma vez |
| `route` | `GET .../route/` | qualquer | tutor ou passeador |

- Cada transição roda em `transaction.atomic()` com `select_for_update()` e publica o evento `walk_*` com
  `transaction.on_commit` (falha na publicação é logada e não desfaz a transição).
- `complete` grava `finished_at` e `distance_meters` e, após o commit, limpa as chaves do Redis do serviço.
- Para criar ou alterar uma transição: mude `service_flow.py`, a action no `ServiceViewSet` (só delega), o
  `@extend_schema` e os testes. Não reimplemente regras de status na view.
- `PUT` e `DELETE` de serviço não existem; desistir é `cancel`.

## WebSocket e Redis

- Rota `ws/services/<id>/`, token JWT na query string, consumer em `core/consumers/service_location.py`.
  Códigos de fechamento: 4001 (não autenticado), 4003 (não participa do serviço), 4004 (serviço inexistente).
- Tutor e passeador recebem os eventos em qualquer status; só o passeador envia localização, e só com o serviço em
  andamento (3).
- Cliente Redis assíncrono compartilhado por processo: `get_shared_redis()` em `core/services/redis_service.py`.
  Chaves temporárias (TTL de 1 hora): `doggo:service:{id}:location`, `:saved_location` e `:distance`.
- Antes de alterar essa área, leia `contexto.md` seção 9. Não mude TTL, intervalos de gravação (10 s / 10 m) nem o
  formato das mensagens sem justificar.

## Testes

- `APITestCase` em `core/tests/`, um arquivo por assunto. Helpers em `core/tests/helpers.py`: `make_user`,
  `make_client`, `make_service_type`, `make_provider`, `make_pet`, `make_service`, `add_availability`, `FakeRedis`,
  `FlowTestCase` (tutor, passeador, estranho, pet e serviço em análise prontos; `auth()` e `action_url()`) e
  `raises()`.
- Use `raises(Exc)` no lugar de `assertRaises`: o ruff proíbe `assertRaises` (regra PT027) e o `pytest` não é
  dependência do projeto (a suíte roda com `python manage.py test`).
- Não dependa de Redis real: use o channel layer em memória, `FakeRedis` ou `unittest.mock`. Testes que gravam
  arquivo usam `override_settings(STORAGES=...)` com `django.core.files.storage.InMemoryStorage`.
- Cubra, para cada endpoint: sem login (401), fora do recurso (404), papel errado (403), caminho feliz, validação
  (400) e estado inválido (409).
- Teste isolado: `pdm run python manage.py test core.tests.<modulo> -v 2`.

## Verificação antes de dizer que terminou

1. `pdm test` — a suíte inteira.
2. `pdm run python manage.py makemigrations --check --dry-run` — nenhuma migration pendente.
3. `pdm check` — ruff.
4. Se mudou contrato de API: `pdm run python manage.py spectacular --validate --file <arquivo>`. Hoje o esquema
   tem 0 erros e alguns avisos de type hint antigos; não introduza novos erros nem avisos.

Estilo (ruff): linha de até 120 colunas, aspas simples, regras `I, F, E, W, PL, PT`; `migrations/`, `__init__.py` e
`manage.py` são excluídos. Rode `ruff format` e `ruff check --fix` apenas nos arquivos que você alterou (via
`pdm run ruff ...`), nunca com `pdm format`, que atua no projeto inteiro.

## Commits

Mensagens com prefixo: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `style:`. Não faça commit, push ou
merge sem pedido explícito. Nunca inclua `.env`, credenciais, `db.sqlite3`, `dump.json` ou `media/` em commits.
