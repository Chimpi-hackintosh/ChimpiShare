# 0.1.0 — 29/10/2026

- Transporte local HTTPS com convite efêmero, certificado fixado pelo convite,
  confirmação manual e conferência SHA-256
- Recepção sem sobrescrita, com publicação após conferência e limpeza de
  transferências interrompidas
- Interface Tkinter em português e inglês, com abas Receber, Enviar e Ponte AirDrop
- Fila de revisão para arquivos de uma pasta dedicada
- Seletor manual para arquivos aceitos pelo AirDrop nativo no macOS
- Adaptador Linux experimental que inicia OpenDrop externo quando configurado
- Diagnóstico separado de qualquer afirmação de compatibilidade AirDrop
- Scripts de build nativo e instalador NSIS x64 preparados
- Compilação por plataforma no GitHub, com execução do binário, teste da interface
  e relatórios anexados aos pacotes antes da publicação
- 32 testes automatizados aprovados no transporte local e componentes de suporte

Recepção AWDL e testes manuais de instalação ainda precisam da validação descrita
em TEST-REPORT.md — os resultados de abertura e transporte dos executáveis
acompanham os respectivos pacotes em `checks.json`
