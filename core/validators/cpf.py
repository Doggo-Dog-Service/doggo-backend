cpf_size = 11
sequence_size = 9
validator_number = 10
primo = 11


def _digito_verificador(digitos):
    """Calcula o dígito verificador dos `digitos` com pesos decrescentes até 2."""
    soma = sum(int(digito) * peso for digito, peso in zip(digitos, range(len(digitos) + 1, 1, -1), strict=True))
    valor = primo - (soma % primo)
    if valor >= validator_number:
        return 0
    return valor


def is_valid_cpf(cpf):
    """Retorna True se `cpf` tem exatamente 11 dígitos, não são todos iguais e os verificadores conferem."""
    if not (cpf.isascii() and cpf.isdigit()) or len(cpf) != cpf_size or len(set(cpf)) == 1:
        return False

    primeiro = _digito_verificador(cpf[:sequence_size])
    segundo = _digito_verificador(cpf[:sequence_size] + str(primeiro))
    return int(cpf[sequence_size]) == primeiro and int(cpf[sequence_size + 1]) == segundo


def cpf_validator(cpf):
    if is_valid_cpf(cpf):
        return f'O cpf {cpf} é válido'
    return f'O cpf {cpf} não é válido'
