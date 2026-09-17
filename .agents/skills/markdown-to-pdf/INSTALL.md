# Instalación en Codex desde GitHub

El paquete instalable es la carpeta **`.agents/skills/markdown-to-pdf`** del repositorio. Contiene `SKILL.md`, instrucciones, scripts, recursos, plantilla, requisitos y licencias. El nombre interno del skill es **`markdown-to-pdf`**, independientemente del nombre del repositorio.

## Pedir la instalación a Codex

Para instalar desde el repositorio oficial, utiliza esta solicitud. Puedes sustituir `main` por una etiqueta publicada si necesitas una versión concreta:

```text
Usa $skill-installer para instalar el skill de
https://github.com/hansphp/markdown-to-pdf-skill/tree/main/.agents/skills/markdown-to-pdf
Prepara sus dependencias Python en el entorno .venv de la carpeta instalada
y comprueba que pueda generar un PDF de ejemplo.
```

Incluye la URL en una conversación nueva: el nombre del skill por sí solo no identifica este repositorio ni garantiza que el agente recuerde su procedencia. No es necesario pertenecer al catálogo de skills seleccionados de OpenAI para instalar desde una URL de GitHub. El repositorio debe estar publicado y ser accesible; uno privado requiere acceso con las credenciales del usuario.

## Qué debe hacer el agente instalador

1. Utiliza el `skill-installer` disponible en la sesión. Selecciona `.agents/skills/markdown-to-pdf`, no la raíz del repositorio ni el adaptador de Claude Code. Conserva el nombre de destino `markdown-to-pdf`.
2. El instalador copia el paquete a su destino de skills y muestra la ruta final. Si ese destino existe, informa la coincidencia y resuelve la actualización según lo solicitado; no borres una instalación existente como parte de una instalación nueva.
3. Localiza `SKILL.md` en la ruta que devolvió el instalador. Prepara las dependencias según la receta siguiente y verifica el navegador existente. El instalador de skills no ejecuta `pip` ni crea `.venv` automáticamente.
4. Haz la conversión de comprobación en una carpeta temporal, copiando `assets/ejemplo/` completo. Usa el script instalado por ruta absoluta, su CSS de ejemplo y `--strict`. Mantén los documentos del usuario fuera de esta prueba.
5. Confirma la ubicación, el resultado y cualquier dependencia que falte. El skill debe estar disponible en el siguiente turno; si no aparece, reinicia Codex. Puedes invocarlo con `$markdown-to-pdf`.

El helper actual acepta estas opciones; sustituye también la ruta al helper por la del `skill-installer` que tengas instalado:

```shell
python3 "/ruta/al/skill-installer/scripts/install-skill-from-github.py" --repo hansphp/markdown-to-pdf-skill --ref main --path .agents/skills/markdown-to-pdf
```

El destino predeterminado del helper disponible durante esta revisión es `$CODEX_HOME/skills`, o `~/.codex/skills` si no se configura esa variable. La documentación actual también define `~/.agents/skills` como ubicación personal; el helper permite elegirla con `--dest`. Usa la ubicación que corresponda a tu instalación de Codex y confirma su detección, evitando copias duplicadas. Las ubicaciones de descubrimiento y el uso de `skill-installer` se describen en la [documentación oficial](https://learn.chatgpt.com/docs/build-skills).

## Preparar las dependencias en cualquier ubicación

Necesitas Python 3.10 o posterior y Chrome, Edge o Chromium. Sustituye la ruta de ejemplo por la carpeta real que contiene el `SKILL.md` instalado. Las recetas crean un entorno independiente junto al skill; no dependen del repositorio del documento.

En macOS/Linux:

```shell
mdpdf_skill_dir="/ruta/real/markdown-to-pdf"
python3 -m venv "$mdpdf_skill_dir/.venv"
"$mdpdf_skill_dir/.venv/bin/python" -m pip install -r "$mdpdf_skill_dir/requirements.txt"
"$mdpdf_skill_dir/.venv/bin/python" "$mdpdf_skill_dir/scripts/convert_markdown_to_pdf.py" --diagnose
```

En Windows PowerShell:

```powershell
$mdpdfSkillDir = "C:\ruta\real\markdown-to-pdf"
py -3 -m venv "$mdpdfSkillDir/.venv"
& "$mdpdfSkillDir/.venv/Scripts/python.exe" -m pip install -r "$mdpdfSkillDir/requirements.txt"
& "$mdpdfSkillDir/.venv/Scripts/python.exe" "$mdpdfSkillDir/scripts/convert_markdown_to_pdf.py" --diagnose
```

El diagnóstico debe mostrar Playwright, pypdf, PyYAML, CSS, logotipo y un navegador disponibles para la salida completa. Si falta el navegador, puedes indicar su ejecutable con `--browser`. El diagnóstico ayuda a identificar recursos; la conversión con `--strict` comprueba su funcionamiento conjunto. No necesitas Node.js ni descargar otro navegador si ya tienes uno compatible. La instalación inicial de paquetes requiere acceso a sus fuentes; Mermaid y KaTeX ya vienen incluidos.

Para convertir desde la carpeta de tus documentos, en macOS/Linux, usando la variable anterior:

```shell
"$mdpdf_skill_dir/.venv/bin/python" "$mdpdf_skill_dir/scripts/convert_markdown_to_pdf.py" "documento.md" --output "documento.pdf" --strict
```

En Windows cambia el intérprete por `.venv/Scripts/python.exe` y utiliza `&` ante la ruta entre comillas. El Markdown de origen se conserva. La carpeta de salida debe existir; `--force` permite reemplazar deliberadamente un PDF previo.

## Instalación por proyecto y Claude Code

También puedes copiar esta carpeta a `.agents/skills/markdown-to-pdf/` dentro de un proyecto. Conserva todos sus archivos y crea un entorno nuevo; no copies `.venv` ni cachés de otra máquina. El código resuelve sus recursos desde su propia ubicación.

El adaptador de Claude Code se distribuye en `.claude/skills/markdown-to-pdf/` del repositorio completo. Para ese agente copia ambas carpetas al proyecto y usa `/markdown-to-pdf`. Una instalación personal de este paquete en Codex no instala automáticamente el adaptador de Claude Code.

El [manual](README.md) contiene todas las opciones y la [plantilla incluida](assets/ejemplo/documento.md) permite crear ejemplos sin archivos de la raíz del repositorio.
