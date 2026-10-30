# Verificação do código e dos pacotes — ChimpiShare 0.1.0

Data: 29/10/2026

## Verificação do código-fonte

**32 testes passaram, sem falhas ou testes ignorados**

Ambiente: Linux, Python 3.12.14, cryptography 50.0.2
Comando: `python3 -m unittest discover -s tests -v`
Duração da execução final: 2,675 segundos

As integrações criaram receptores HTTPS locais em `127.0.0.1`, com certificados
novos e arquivos temporários reais

| Comportamento | Resultado |
| --- | --- |
| PNG preservado byte a byte | Passou |
| Arquivo binário com múltiplos blocos e progresso | Passou |
| Arquivo vazio e nome Unicode | Passaram |
| Mesmo nome em duas transferências sem sobrescrita | Passou |
| Recusa no destino | Passou |
| Token de outra sessão | Rejeitado antes de pedir confirmação |
| Certificado diferente do convite | Rejeitado |
| Conteúdo com SHA-256 incorreto | Rejeitado e temporários removidos |
| Upload interrompido | Temporários removidos |
| Tentativa de escapar da pasta pelo nome | Rejeitada |
| Nome reservado do Windows | Sanitizado |
| Arquivo acima do limite | Rejeitado |
| Autorização expirada ou reutilizada | Rejeitada |
| Tamanho incompatível, Content-Length repetido e chunked | Rejeitados |
| Receptor ocupado | Nova oferta recusada até liberar/expirar |
| Conexão TLS parada | Outro cliente atendido normalmente |
| Link simbólico e named pipe | Rejeitados |
| Nova sessão | Token e certificado diferentes |
| Fila da ponte | Filtragem e estabilidade verificadas |
| Diagnóstico com interface AWDL presente | Não afirma compatibilidade Apple verificada |
| Idiomas | Chaves, parâmetros e cobertura das mensagens conferidos |
| Preferências | Persistência, override e fallback conferidos |

Outros comandos executados com sucesso:

- `python3 -m compileall -q chimpishare scripts run_gui.py`
- `python3 -m chimpishare --version` retornou `0.1.0`
- `python3 -m chimpishare doctor` retornou o diagnóstico do ambiente
- `sh -n scripts/build_unix.sh`

O diagnóstico real não encontrou OpenDrop, OWL ou interface `awdl0`

## Compilação e execução do programa empacotado

O workflow de publicação executa o próprio programa congelado por PyInstaller em
Windows x64, Linux x64, macOS Intel e macOS Apple Silicon
O relatório específico de cada compilação acompanha o pacote em `checks.json`

- `self-test`: inicia dois lados do transporte local, transfere um arquivo e
  compara todos os bytes e seu SHA-256
- `gui-smoke`: abre a interface Tk, verifica as três abas e as dimensões e fecha
  sem iniciar o receptor AirDrop ou gravar preferências
- O processo é iniciado fora da pasta de instalação, sem PYTHONPATH/PYTHONHOME
  e com os diretórios Python removidos do PATH
- Empacotamento dos downloads exige os relatórios da execução do binário
- O instalador NSIS é compilado no Windows após a verificação do aplicativo

Essas verificações não equivalem a testar um computador limpo sem Python instalado

## Limites da verificação inicial e testes manuais pendentes

| Item | Estado |
| --- | --- |
| Recepção a partir de iPhone/iPad/Mac por AWDL | Não executada — sem hardware Apple/AWDL |
| Descoberta do receptor no AirDrop atual | Não executada |
| OpenDrop e OWL reais | Não instalados nem executados |
| Transferência entre dois computadores físicos | Não executada — teste de transporte foi local |
| Renderização e interação da interface Tk | Não executadas — sem servidor gráfico / DISPLAY |
| Windows x64 sem Python instalado | Não executado — sem Windows no ambiente |
| Build PyInstaller e compilação NSIS | Resultados posteriores nos relatórios de cada pacote |
| macOS, bundle .app e AirDrop nativo | Não executados — sem macOS |
| Instalação, atualização e desinstalação | Não executadas |
| Assinatura digital / notarização | Não realizadas |

Os testes do transporte não comprovam compatibilidade com uma versão específica
de iOS, driver de Wi-Fi ou sistema operacional de destino
Os relatórios iniciais acima descrevem o ambiente local do protótipo
Para afirmar a execução de um pacote nativo específico, consulte o `checks.json`
distribuído junto desse pacote e a execução correspondente do workflow
