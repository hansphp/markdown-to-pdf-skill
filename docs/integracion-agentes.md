# Integración con Codex y Claude Code

Los dos agentes utilizan el mismo conversor y los mismos recursos. Instala primero las dependencias del [inicio rápido](../README.md#empezar).

Esta guía describe principalmente la copia completa del repositorio. Para instalar solo el skill en tu Codex desde GitHub, consulta [INSTALL.md](../.agents/skills/markdown-to-pdf/INSTALL.md): incluye la URL de origen, la ruta del paquete y los comandos para prepararlo en su ubicación personal.

| Agente | Entrada del proyecto | Invocación explícita | Implementación |
| --- | --- | --- | --- |
| Codex | [.agents/skills/markdown-to-pdf/SKILL.md](../.agents/skills/markdown-to-pdf/SKILL.md) | `$markdown-to-pdf` | Scripts y recursos junto al skill. |
| Claude Code | [.claude/skills/markdown-to-pdf/SKILL.md](../.claude/skills/markdown-to-pdf/SKILL.md) | `/markdown-to-pdf` | El adaptador lee el skill canónico y ejecuta sus scripts. |

Las descripciones permiten que el agente reconozca solicitudes de conversión y creación de ejemplos. La selección automática depende de la solicitud y del agente; la invocación explícita identifica el skill que quieres usar.

## Codex

Abre este repositorio en Codex. Los skills de proyecto se descubren en `.agents/skills/` desde la carpeta de trabajo y sus ancestros dentro del repositorio. Si acabas de añadir el skill y no aparece, reinicia Codex y vuelve a abrir el proyecto. Consulta la [documentación oficial de skills](https://learn.chatgpt.com/docs/build-skills).

```text
Usa $markdown-to-pdf para convertir ejemplo-markdown-pdf/basico.md
a resultado.pdf, sin índice de secciones y con validación estricta.
```

[agents/openai.yaml](../.agents/skills/markdown-to-pdf/agents/openai.yaml) define el nombre visible, la descripción breve y el prompt sugerido. `policy.allow_implicit_invocation: true` permite su selección implícita; no obliga al agente a utilizarlo en cualquier solicitud.

[AGENTS.md](../AGENTS.md) orienta al agente hacia las instrucciones, los ejemplos y las pruebas. La integración no requiere editar la configuración personal de Codex.

## Claude Code

Abre Claude Code desde la raíz de este repositorio y solicita:

```text
/markdown-to-pdf convierte ejemplo-markdown-pdf/basico.md
a resultado.pdf, sin índice de secciones y con validación estricta.
```

Claude Code descubre la entrada en `.claude/skills/markdown-to-pdf/SKILL.md`. El adaptador utiliza `${CLAUDE_SKILL_DIR}` para localizar el núcleo compartido aunque la carpeta de trabajo cambie. Claude Code sustituye esa expresión al cargar el skill; no es una variable que debas configurar para ejecutar comandos manuales. Estas convenciones se describen en su [documentación oficial de skills](https://code.claude.com/docs/en/skills).

El adaptador indica que se lea el `SKILL.md` canónico antes de convertir y que sus recursos se resuelvan desde `.agents/skills/markdown-to-pdf/`. Así se mantiene una sola implementación. [CLAUDE.md](../CLAUDE.md) aporta orientación al abrir el proyecto, siguiendo el mecanismo de [instrucciones de proyecto de Claude Code](https://code.claude.com/docs/en/memory).

Si el comando no aparece, comprueba que abriste la raíz correcta, que existe el archivo de entrada y que utilizas una versión de Claude Code compatible con skills. Reinicia la sesión tras añadir la entrada.

## Instalar en otro proyecto

Conserva esta estructura relativa:

```text
tu-proyecto/
├── .agents/skills/markdown-to-pdf/   # Núcleo compartido y entrada de Codex
└── .claude/skills/markdown-to-pdf/   # Adaptador de Claude Code
```

Para Codex basta con la primera carpeta. Para Claude Code copia ambas. Excluye `.venv/`, `__pycache__/` y `*.pyc`, y crea un entorno nuevo con las dependencias fijadas en `requirements.txt`. Un entorno virtual existente no debe trasladarse entre instalaciones o sistemas operativos.

Incorpora las indicaciones pertinentes de `AGENTS.md` o `CLAUDE.md` a las instrucciones existentes del proyecto, ajustando los enlaces. Los ejemplos públicos, las capturas y los documentos de la raíz son material de consulta opcional; el núcleo ya incluye su propio manual y su plantilla en `assets/ejemplo/`.

Los archivos de entrada, salida y opciones de terminal se resuelven desde la carpeta de ejecución. Las imágenes y `pdf.logo` declarados dentro del documento se resuelven desde la carpeta del Markdown. Utiliza comillas para las rutas con espacios. Consulta el [manual](../.agents/skills/markdown-to-pdf/README.md) para opciones y validación.

## Verificación realizada

Comprobaciones locales realizadas el **16 de septiembre de 2026**, en macOS con Google Chrome:

| Comprobación | Resultado |
| --- | --- |
| Descubrimiento real de Codex mediante `app-server` y `skills/list` | Con `codex-cli 0.154.0-alpha.6.2`, se detectó una entrada de repositorio habilitada y sin errores, tanto desde la raíz como desde una subcarpeta. |
| Descubrimiento de una copia autónoma | En un repositorio temporal con solo los 117 archivos del skill, sin entorno ni cachés, Codex detectó una única entrada habilitada, con metadatos correctos y cero errores desde la raíz y una subcarpeta. |
| Metadatos de Codex | Se cargaron el nombre visible, la descripción breve y el prompt de `openai.yaml`. Se comprobó `allow_implicit_invocation: true` en el YAML; `skills/list` no devuelve ese campo. No se hizo una petición a un modelo para medir su selección automática. |
| Dependencias y ejecución desde otra carpeta | Diagnóstico correcto desde fuera del repositorio; `pip check` sin conflictos y versiones acordes con `requirements.txt`. |
| Instalación autónoma desde paquete | Helper de `skill-installer` probado con un ZIP local equivalente a GitHub, entorno nuevo y dependencias recién instaladas; conversión estricta de 14 páginas desde otra carpeta. La descarga del repositorio público se verificará después de publicarlo. |
| Adaptador de Claude Code | Metadatos válidos, enlaces al núcleo correctos y comando probado en una copia temporal con espacios en las rutas y ejecución desde una subcarpeta. |
| Conversión a través del comando del adaptador | PDF real con Mermaid y fórmula en modo estricto. El Markdown se conserva; un error de Mermaid con `--force` conserva también el PDF anterior. |
| Suite completa con navegador | 351 pruebas aprobadas, incluidas las dos pruebas del adaptador. |
| Inicio rápido y ejemplos públicos | Comando del README ejecutado con una salida temporal: PDF de una página, referencia numerada correcta y Markdown sin cambios. Se revisaron las seis capturas de los PDFs incluidos. |
| Sesión real de Claude Code | **Pendiente de verificar:** el CLI no está instalado en este entorno. Las pruebas del adaptador no sustituyen una invocación dentro de Claude Code. |

La comprobación de Codex usa la interfaz documentada de [App Server](https://learn.chatgpt.com/docs/app-server). Las pruebas reproducibles del adaptador están en [test_agent_integration.py](../.agents/skills/markdown-to-pdf/tests/test_agent_integration.py).

Para ejecutar todas las pruebas con navegador desde la raíz, en macOS/Linux:

```shell
MDPDF_BROWSER_TESTS=1 .agents/skills/markdown-to-pdf/.venv/bin/python -B -m unittest discover -s .agents/skills/markdown-to-pdf/tests -q
```

En PowerShell, define `$env:MDPDF_BROWSER_TESTS="1"` y usa `.venv/Scripts/python.exe`. Las instrucciones de Windows y Linux están documentadas; estas comprobaciones se ejecutaron en macOS.
