import os

DEFAULT_ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'doggo-backend.class.fabricadesoftware.ifc.edu.br']
DEFAULT_FRONTEND_ORIGINS = ['http://localhost:5173', 'http://localhost:3000', 'https://doggo-frontend.vercel.app']

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
