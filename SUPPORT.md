# Aviso de suporte e atualizações

## Política

A partir de **04/11/2026 às 00h UTC**, versões abaixo da mínima declarada deixam de receber correções de segurança do proprietário

Antes dessa data o aviso informa que o suporte está prestes a terminar — depois informa que as atualizações de segurança terminaram

O texto explica o risco de falhas sem afirmar que o usuário ou o aplicativo já foi infectado

| Aplicativo | Versão publicada conferida em 02/11/2026 | Mínima |
| --- | --- | --- |
| ChimpiShare | v0.1.0 — prévia | 0.1.0 |

## Comportamento

- Detecta o idioma do sistema ou navegador — português, inglês, espanhol, francês, alemão, italiano, russo, chinês, japonês, coreano, árabe e hindi, com inglês como alternativa
- Compara versões numericamente e ignora sufixos de build quando o aplicativo só informa a série de versão
- Consulta somente dados públicos de suporte por HTTPS, com prazo limitado e catálogo local quando está sem internet
- Não envia arquivos, prompts, senhas, dados de hardware ou dados NFC
- Mostra a versão instalada e a mínima, com opções de atualizar, ver a tabela ou deixar para depois
- Abre a página oficial e preserva a decisão de baixar e instalar com o usuário

A tabela pública fica em [Apps e suporte](https://chimpi-hackintosh.github.io/ChimpiBlender-Online/support.html) depois que o PR do site for integrado e o Pages for publicado

## Distribuição e limites

**Alterar o repositório não altera binários já instalados** — versões antigas sem verificador precisam receber uma atualização manual inicial para passarem a consultar a política

Este PR entrega código e verificações — não equivale a um novo Release, atualização instalada ou site já implantado

As prévias continuam identificadas como prévias — os números da tabela vêm de lançamentos existentes e não foram inventados para esta alteração

O catálogo público não inclui repositórios privados

## Validação local desta alteração

`python -m unittest discover -s tests -v`: 40 testes aprovados

Os testes do aviso cobrem versões iguais e mais novas sem alerta, versões antigas com alerta, mudança exata de data, traduções, falha de rede e rejeição de links não oficiais

`CHIMPI_SUPPORT_CHECK=0` desliga a consulta opcional — os modos de smoke test também evitam rede e avisos durante a compilação


## Atualização do catálogo em 15/11/2026

A prévia pública `v1.1.0-preview.18` do ChimpiCode foi publicada em 15/11/2026 às 14:05:41 UTC e permanece classificada como prévia. O instalador Windows Setup tem o digest SHA-256 `sha256:e518703784c7f38143332c5a12e6ed96f6a0bf84ca0831ba40ca9f556bee020f`. A versão estável continua sendo `v1.0.0`.


## Atualização do catálogo em 15/11/2026

A prévia pública `v1.1.0-preview.21` do ChimpiCode foi publicada em 15/11/2026 às 14:22:46 UTC e permanece classificada como prévia. O instalador Windows Setup tem o digest SHA-256 `sha256:66784558333392705e5a8c4a3fb349ede6f46725083b3134e72ab037aad04bfa`. A versão estável continua sendo `v1.0.0`.
