import os

DEFAULT_ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'doggo-backend.class.fabricadesoftware.ifc.edu.br']
DEFAULT_FRONTEND_ORIGINS = ['http://localhost:5173', 'http://localhost:3000', 'https://doggo-frontend.vercel.app']
# Origem do frontend (Vite) aberto a partir de outro aparelho da rede local, ex.: celular em http://<MY_IP>:5173
LAN_FRONTEND_ORIGIN = 'http://{ip}:5173'

TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def env_bool(name: str, default: bool) -> bool:
    """Lê uma variável de ambiente booleana. Ausente usa `default`; qualquer valor fora de TRUE_VALUES é falso."""
    valor = os.getenv(name)
    if valor is None:
        return default
    return valor.strip().lower() in TRUE_VALUES


def env_list(name: str, default: list[str]) -> list[str]:
    """Lê uma lista separada por vírgulas, sem espaços e sem itens vazios. Ausente ou em branco usa `default`."""
    valor = os.getenv(name)
    if valor is None or not valor.strip():
        return list(default)
    return [item.strip() for item in valor.split(',') if item.strip()]


def with_dev_ip(items: list[str], ip: str | None, *, debug: bool, template: str = '{ip}') -> list[str]:
    """Devolve `items` com `template` (preenchido com `ip`) acrescentado, para testar pela rede local em DEBUG.

    Fora de DEBUG, ou sem `ip`, a lista segue idêntica: um IP de rede nunca vira host ou origem confiável em produção.
    Não duplica entradas e não altera a lista recebida.
    """
    ip = (ip or '').strip()
    if not debug or not ip:
        return list(items)
    entrada = template.format(ip=ip)
    return [*items, entrada] if entrada not in items else list(items)
