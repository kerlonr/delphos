<p align="center">
  <img src="app/assets/delphos.png" alt="Delphos" width="160">
</p>

<h1 align="center">Delphos</h1>

<p align="center">
  Macropad 3x4 com encoder e tela OLED, firmware QMK e app próprio para Windows.<br>
  Mixer de volume por app, mute global do microfone, mídia por app e teclas configuráveis.
</p>

<p align="center">
  <a href="https://github.com/kerlonr/delphos/releases/latest"><img src="https://img.shields.io/github/v/release/kerlonr/delphos?label=download" alt="download"></a>
  <img src="https://img.shields.io/badge/firmware-QMK-blue" alt="QMK">
  <img src="https://img.shields.io/badge/app-Windows-0078D6" alt="Windows">
</p>

---

## O que faz

- **Mic mute global**: muta e desmuta todos os microfones do Windows. A tela mostra `ATIVO` ou `MUTADO`.
- **Volume por app**: o encoder ajusta o item selecionado (`Geral` ou um app com som aberto).
  Segure o clique e gire para trocar de app, ou use a tecla `Próximo app`.
- **Mídia por app**: Play/Pause, Próxima e Anterior agem no app selecionado. Dá para pausar o Spotify
  sem mexer no vídeo do navegador. Com `Geral`, vale a mídia que o Windows escolher.
- **Tela**: nome do app em letra grande, barra de volume e a música tocando rolando. O volume aparece
  grande enquanto o encoder gira.
- **Teclas configuráveis** direto no app, sem gravar firmware: 4 camadas, macros e ações no PC
  (abrir programa, site ou pasta).
- **Sem o app aberto**, o encoder controla o volume do Windows e as teclas de mídia funcionam normalmente.

## Instalação

1. Baixe o `Delphos.exe` na [última release](https://github.com/kerlonr/delphos/releases/latest).
2. Plugue o Delphos no USB e abra o `Delphos.exe`.
3. Em **Ajustes**, clique em **Atualizar firmware**. O firmware já vem embutido no app.
   - Se o teclado ainda estiver com o firmware antigo, o app pede para entrar no modo de gravação:
     aperte **2 vezes rápido** o botão de reset do Pro Micro (ou segure a tecla do canto superior
     esquerdo enquanto pluga o cabo).
4. Ainda em **Ajustes**, clique em **Instalar no PC** e marque **Iniciar com o Windows**.
   O app vai para a pasta de programas, aparece no menu Iniciar e abre escondido na bandeja.

Pronto. Fechar a janela deixa o app na bandeja; para sair, use *Sair* no ícone da bandeja.

> Não é preciso instalar VIA, QMK Toolbox, mixer de volume nem app de mute: o `Delphos.exe` faz tudo.

## Mapa padrão

```
,---------------------------.
|     OLED    |      | Play |  <- clique do encoder (segurar + girar = troca app)
|-------------+------+------|
|  MIC | Prev | Play | Next |
|------+------+------+------|
|  F14 |  F15 | F16  | F17  |
|------+------+------+------|
| Lock |  F18 | F19  | App> |
`---------------------------'
Encoder: Volume - / Volume +    Lock = Win+L
```

## O app

- **Teclas**: escolha a camada (0 a 3), clique numa tecla ou no encoder do desenho e escolha a função:
  Delphos, mídia, sistema, F-keys, letras, camadas (`TO`, `MO`, `TG`), um atalho gravado na hora ou
  qualquer código QMK em hexadecimal. Vale na hora. *Restaurar teclas padrão* volta ao mapa acima.
- **Macros**: a tecla digita um texto e/ou aperta teclas e atalhos, com esperas. Ficam gravadas no
  teclado (16 macros). O texto é digitado como num teclado americano.
- **Ação no PC**: a tecla abre um programa, um site ou uma pasta, ou muta o som de um app
  (teclas `Ação 1..16`, precisam do app aberto).
- **Mixer**: volume e mute de cada app, qual app o encoder controla, música tocando e microfones.
- **Ajustes**: iniciar com o Windows, passo do volume, atualizar firmware, instalar no PC,
  backup (exporta e importa as 4 camadas, macros e ações) e pasta do log.
- O desenho do teclado espelha a tela do Delphos, com a mesma fonte e layout do firmware.

Log: `%LOCALAPPDATA%\Delphos\log.txt`.

### Usar com o VIA

O firmware continua compatível com o [VIA](https://usevia.app). Baixe o `via.json` da
[release](https://github.com/kerlonr/delphos/releases/latest) e carregue em
*Settings > Show Design tab > Design > Load Draft Definition*.

## Desenvolvimento

### Firmware

Precisa do [QMK MSYS](https://msys.qmk.fm) com `qmk setup` feito.

```powershell
.\scripts\build.ps1   # compila e gera delphos_3x4_default.hex na raiz
.\scripts\flash.ps1   # coloca o teclado em modo de gravação (comando 0x43) e grava
```

O `build.ps1` liga a pasta do repo em `qmk_firmware\keyboards\delphos_3x4` (junction) e roda
`qmk compile -kb delphos_3x4 -km default`.

O mapa de teclas e as macros ficam na EEPROM e continuam lá depois de atualizar o firmware (o build usa `SKIP_VERSION=yes`, que fixa a data que o VIA usa para validar a EEPROM). Para voltar ao padrão, use *Restaurar teclas padrão* no app.

### App

Precisa do Python 3.12.

```powershell
.\scripts\build.ps1   # o exe embute o firmware, então compile ele antes
.\app\build.ps1       # cria o venv, roda os testes e gera app\dist\Delphos.exe
```

Testes: `app\.venv\Scripts\python -m pytest app\tests`. Os marcados `live` usam o áudio e o teclado
reais e restauram o estado no final.

### Tela

Com `OLED_DISPLAY_128x64` o painel só mostra as 32 linhas de cima, então o `screen.c` desenha em 128x32.
O teste `app/tests/test_screen_parity.py` compila o `screen.c` no PC e confere, pixel a pixel, que o
espelho do app é igual à tela do firmware.

O firmware tenta iniciar a tela de novo se ela não estava pronta no boot e continua desenhando com o
USB suspenso (`NO_SUSPEND_POWER_DOWN`), então a tela não fica apagada esperando uma tecla.

### Protocolo PC ↔ teclado

Raw HID do VIA (usage page `0xFF60`), relatórios de 32 bytes, IDs fora da faixa do VIA, tratados em
`via_command_kb()`. Definido em `keymaps/default/delphos_proto.h` e `app/delphos/protocol.py`.

| ID   | Sentido    | Conteúdo |
|------|------------|----------|
| 0x40 | PC → tecl. | STATE: versão, flags (mic mudo, item mudo), volume, índice, total, nome (20 chars) |
| 0x41 | tecl. → PC | EVENT: 1 mic, 2 próximo, 3 anterior, 4 vol+, 5 vol-, 6 mute item, 7 play, 8 próxima faixa, 9 faixa anterior, 10 ação N |
| 0x42 | PC ↔ tecl. | HELLO: versão do protocolo e do firmware |
| 0x43 | PC → tecl. | BOOTLOADER: entra no modo de gravação |
| 0x44 | PC → tecl. | MEDIA: status (0 nada, 1 tocando, 2 pausado) + "título - artista" (29 chars) |

## Hardware

- Pro Micro (ATmega32U4), bootloader caterina
- 12 teclas em matriz 3x5 (`COL2ROW`), encoder clicável e OLED SSD1306 128x64 (I2C)

Modo de gravação: botão *Atualizar firmware* no app, `scripts\flash.ps1`, segurar a tecla (0,0) ao plugar
o cabo, ou 2 toques rápidos no reset do Pro Micro.

## Créditos

Baseado no [delphos-qmk](https://github.com/thalesgmartins/delphos-qmk) de
[Thales Martins](https://github.com/thalesgmartins), criador do hardware e do firmware original.

O exe embute o [avrdude](https://github.com/avrdudes/avrdude) (GPL-2.0), copiado do QMK MSYS.
A abertura do app usa a fonte [Michroma](https://github.com/googlefonts/Michroma-font) (SIL Open Font License 1.1, em `app/delphos/ui/fonts/OFL.txt`).
