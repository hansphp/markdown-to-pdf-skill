---
name: markdown-to-pdf
description: Convierte archivos Markdown locales a PDF y crea documentos de ejemplo que enseñan su formato y opciones. Úsalo para exportar una especificación, guía, informe o README, o para generar una plantilla de ejemplo con las características del conversor. No edita PDF existentes.
license: MIT
---

# Markdown a PDF en Claude Code

Esta entrada conecta Claude Code con el mismo motor y las mismas instrucciones que utiliza Codex en este repositorio.

1. Antes de actuar, lee el [SKILL canónico](../../../.agents/skills/markdown-to-pdf/SKILL.md). Su ruta absoluta se obtiene desde `${CLAUDE_SKILL_DIR}/../../../.agents/skills/markdown-to-pdf/SKILL.md`.
2. Sigue su flujo para crear ejemplos o convertir documentos. Resuelve sus enlaces, scripts, recursos y entorno `.venv` desde la carpeta **canónica** `.agents/skills/markdown-to-pdf/`, no desde esta entrada.
3. Usa el comando siguiente para la conversión. Sustituye los nombres de ejemplo por las rutas del documento y destino solicitados, entre comillas. Las rutas de entrada y salida relativas parten de la carpeta donde ejecutes el comando; puedes usar rutas absolutas si trabajas desde una subcarpeta.

   ```shell
   python3 "${CLAUDE_SKILL_DIR}/../../../.agents/skills/markdown-to-pdf/scripts/convert_markdown_to_pdf.py" "documento.md" --output "documento.pdf"
   ```

Claude Code sustituye `${CLAUDE_SKILL_DIR}` al cargar este skill. No es una variable que debas definir para usar el conversor manualmente: en ese caso sigue los comandos del [README del motor](../../../.agents/skills/markdown-to-pdf/README.md).

El comando mostrado usa `python3` en macOS/Linux. En Windows, usa el intérprete `.venv/Scripts/python.exe` del núcleo canónico tras instalar las dependencias, o `py -3` para diagnosticar la instalación. En PowerShell, antepone `&` si la ruta del ejecutable está entre comillas. Conserva la ruta del script resuelta desde `${CLAUDE_SKILL_DIR}`.

Puedes invocarlo con `/markdown-to-pdf convierte "mi documento.md" a PDF` o pedir un ejemplo. Para usarlo en otro proyecto, conserva juntas las carpetas `.claude/skills/markdown-to-pdf/` y `.agents/skills/markdown-to-pdf/` dentro de ese proyecto. Esta entrada depende del núcleo y no se instala por separado.

Solicitud del usuario:

$ARGUMENTS
