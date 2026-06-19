cpf_size = 11
sequence_size = 9
validator_number = 10


def cpf_validator(cpf):
    if len(set(cpf)) == 1 or len(cpf) != cpf_size:
        return f'O cpf {cpf} não é válido'

    digito1 = cpf[9]
    digito2 = cpf[10]
    primo = 11

    sequencia = ''
    for digito in cpf:
        if len(sequencia) < sequence_size:
            sequencia += digito

    def primeiro_validador(sequencia):
        soma = 0
        indice = 0

        for i in range(10, 1, -1):
            soma += int(sequencia[indice]) * i
            indice += 1

        valor = primo - (soma % primo)
        if valor >= validator_number:
            return 0
        return valor

    def segundo_validador(sequencia, primeiro_validador):
        para_str = str(primeiro_validador)
        sequencia += para_str

        soma = 0
        indice = 0

        for i in range(11, 1, -1):
            soma += int(sequencia[indice]) * i
            indice += 1

        valor = primo - (soma % primo)
        if valor >= validator_number:
            return 0
        return valor

    if int(digito1) == int(primeiro_validador(sequencia)) and int(digito2) == int(
        segundo_validador(sequencia, primeiro_validador(sequencia))
    ):
        return f'O cpf {cpf} é válido'
    else:
        return f'O cpf {cpf} não é válido'
