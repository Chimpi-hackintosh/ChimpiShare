# ChimpiShare 0.1.0 — primeira versão experimental

Ponte de arquivos da Apple para Windows e Linux

- Recepção e envio pela rede local com TLS, convite de sessão e confirmação manual
- Conferência SHA-256, proteção contra sobrescrita e limpeza de uploads interrompidos
- Interface em português e inglês
- Encaminhamento manual de arquivos recebidos pelo AirDrop nativo de um Mac
- Adaptador Linux experimental para OpenDrop externo com OWL e hardware compatível

## Downloads

- **Windows x64:** instalador `Setup-x64.exe` ou pacote portátil `windows-x64.zip`
- **Linux x64:** extraia o `linux-x64.tar.gz` e execute `ChimpiShare/ChimpiShare`
- **macOS Intel / Apple Silicon:** extraia o `.zip` da sua arquitetura e abra `ChimpiShare.app`
- **Fontes:** arquivo `source.zip`
- **Integridade:** compare com `SHA256SUMS.txt`

Os pacotes incluem o runtime Python e as dependências do transporte
OpenDrop, OWL e seus drivers não são incluídos
Linux e Windows podem trocar arquivos pela LAN mesmo sem esses componentes

## Compatibilidade AirDrop

A recepção AirDrop em Linux ainda depende de OWL/OpenDrop, do rádio Wi-Fi, do
driver e da versão do sistema Apple — a primeira etapa AWDL não foi validada com
um iPhone nesta versão
No Mac, o usuário aceita pelo AirDrop do sistema e seleciona o arquivo no aplicativo
A ponte Linux precisa de Ethernet ou de outro adaptador para encaminhar pela LAN

Cada pacote inclui o relatório `checks.json` com a execução do próprio binário
Os testes automatizados verificam o transporte e a abertura da interface, não uma
instalação completa em um computador limpo nem compatibilidade AWDL

Os executáveis não têm assinatura de uma autoridade certificadora
O bundle macOS utiliza a assinatura ad-hoc do empacotador, sem notarização Apple
Não há serviço em segundo plano ou inicialização automática
