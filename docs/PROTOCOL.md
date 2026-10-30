# Transporte ChimpiShare v1

Esta especificação descreve a transferência IPv4 local posterior à recepção AirDrop
Ela não descreve nem implementa AWDL, BLE, mDNS AirDrop ou negociação Apple

## Sessão

O operador inicia um receptor numa interface IPv4 e porta específicas
Cada início gera um token aleatório de 32 bytes e um certificado TLS efêmero

Convite:

```text
chimpishare://IPV4:PORTA/v1#TOKEN_BASE64URL:SHA256_CERTIFICADO_DER
```

O token tem 43 caracteres base64url e a impressão digital tem 64 caracteres hex
O cliente valida o certificado por essa impressão digital após o handshake e
antes de transmitir credenciais ou dados HTTP
O segredo vai em `Authorization: Bearer TOKEN` dentro do TLS
A confiança depende de obter o convite correto por um canal controlado pelo usuário

O receptor exige um único Content-Length e não aceita Transfer-Encoding
Todas as respostas fecham a conexão
O servidor limita a quantidade de conexões simultâneas e oferece uma transferência
por vez, incluindo a oferta que aguarda confirmação

## GET /v1/info

Autenticação obrigatória
Retorna `app`, `version` e `max_bytes`

## POST /v1/offers

Autenticação obrigatória, JSON de no máximo 8 KiB:

```json
{"name":"Arquivo.png","size":12345,"sha256":"64 caracteres hexadecimais minúsculos"}
```

O servidor valida nome, tamanho, limite e espaço disponível
A confirmação manual tem prazo de até 90 segundos
Uma oferta aceita retorna HTTP 201 com `id` e o nome final sanitizado
A autorização vale por 120 segundos para começar o upload, é vinculada ao IPv4 da
oferta e só pode ser utilizada uma vez

## PUT /v1/files/ID

Autenticação obrigatória, bytes do arquivo com Content-Length exato
O conteúdo é gravado incrementalmente em uma pasta temporária na pasta de destino
O SHA-256 precisa corresponder à oferta
Só depois da conferência o servidor publica o diretório completo com nome único

HTTP 201 contém `name`, `size` e `sha256`
O cliente só informa sucesso após validar essa resposta
Sem confirmação final não se pode assumir entrega — se a conexão cair após a
gravação, o arquivo pode ter sido salvo sem o remetente receber a confirmação
Uma nova tentativa é uma nova transferência, podendo gerar uma cópia adicional

## Limites

Sem retomada, transferência de pastas, pareamento persistente, descoberta de rede,
fan-out automático, autenticação Apple ou transferência direta para iOS
As permissões do sistema operacional protegem a pasta local e o material TLS
Não há sandbox para programas externos como OpenDrop
