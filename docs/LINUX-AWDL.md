# Ponte Linux experimental

O ChimpiShare implementa a etapa de encaminhamento e um adaptador de processo
A recepção AirDrop em Linux é feita por OWL + OpenDrop, que são externos
Ver a interface `awdl0` não prova compatibilidade com o iPhone/iPad/macOS atual

## Antes de tentar

OWL foi arquivado em **12 de outubro de 2026** e não é mais mantido
Seu README exige uma placa com **monitoramento ativo e injeção de quadros**
Monitoramento comum, Wi-Fi Direct ou apenas Bluetooth não comprovam suporte

O projeto recomenda o Atheros AR9280 usado nos testes originais
Não se pode inferir suporte de outra placa apenas por ter um nome parecido
Compatibilidade precisa ser verificada no conjunto placa + driver + kernel

Use uma máquina Linux física e **Ethernet ou uma segunda placa Wi-Fi para a LAN**
O README do OWL informa que a placa usada por ele não mantém a conexão ao AP
O adaptador do ChimpiShare bloqueia WSL
Uma VM só seria candidata com acesso físico apropriado ao rádio por passthrough,
o que permanece fora do escopo de validação desta versão

## Preparação de referência

Consulte os READMEs atuais dos projetos antes de instalar
Estes comandos são uma referência para um laboratório Debian/Ubuntu com placa
dedicada já identificada — não são executados pelo ChimpiShare

Dependências de build descritas pelo OWL, mais ferramentas de desenvolvimento:

```sh
sudo apt install git cmake build-essential libpcap-dev libev-dev libnl-3-dev libnl-genl-3-dev libnl-route-3-dev
git clone --recursive https://github.com/seemoo-lab/owl.git
cmake -S owl -B owl/build
cmake --build owl/build
sudo cmake --install owl/build
```

O código é antigo e pode exigir ajustes para o compilador/kernel atual
Este projeto não validou esse build e não instala um fork alternativo por conta própria

Prepare OpenDrop em um ambiente Python separado, com as bibliotecas de sistema
que ele exige, incluindo uma versão compatível de libarchive
O projeto original documenta a instalação por `pip install opendrop`
Confirme a compatibilidade da versão de Python escolhida com esse projeto externo
O comando `opendrop` desse ambiente precisa estar no PATH da sessão que abre o
ChimpiShare — ative o ambiente correspondente antes de iniciar a interface

Identifique o nome da **placa dedicada**, então use o formato documentado pelo OWL:

```sh
sudo owl -i NOME_DA_PLACA_DEDICADA
```

Não copie o placeholder literalmente e não escolha a placa que mantém sua LAN
Respeite os canais permitidos na sua região — o ChimpiShare não altera os canais
OWL, e não o aplicativo, cria a interface virtual `awdl0`

## Testar a primeira etapa separadamente

1. Execute `python -m chimpishare doctor` e confira os pré-requisitos
2. No ChimpiShare, escolha uma pasta dedicada em **Ponte AirDrop**
3. Inicie a opção Linux experimental e leia o aviso sobre aceitação automática
4. No dispositivo Apple, abra AirDrop e verifique se o receptor aparece
5. Envie somente um arquivo de teste que você controla
6. Confirme na ponte o nome, o tamanho e se o recebimento terminou
7. Se a descoberta ou a transferência falhar, pare OpenDrop e investigue a
   etapa AWDL/OpenDrop — o transporte HTTPS não corrige esse problema

O app executa apenas `opendrop receive`, sem shell, dentro de uma pasta nova da
sessão escolhida pelo usuário
Ele não inicia OWL como administrador, não extrai certificados da conta Apple,
não modifica drivers e não representa o resultado do diagnóstico como sucesso AirDrop

## Encaminhar para Windows ou outro Linux

No destino, inicie o receptor e copie o convite
Na ponte, escolha o arquivo recebido, cole o convite e envie
O destino confirma manualmente a segunda transferência
Use Ethernet ou a outra placa Wi-Fi para essa conexão

OpenDrop recebe e extrai os arquivos de acordo com o comportamento do próprio
projeto — a pasta de sessão organiza os resultados, mas não é uma sandbox do sistema
Use essa integração experimental somente em ambiente de teste que você controla

## Fontes primárias

- https://github.com/seemoo-lab/owl
- https://github.com/seemoo-lab/owl/blob/master/README.md
- https://github.com/seemoo-lab/opendrop/blob/master/README.md
