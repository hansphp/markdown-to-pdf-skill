# Markdown a PDF

Convierte archivos Markdown en PDFs con portada opcional, índices enlazados, tablas, figuras, diagramas Mermaid, fórmulas y notas. Puedes usarlo desde la terminal, con **Codex** o con **Claude Code**. La conversión conserva el Markdown original.

[Ejemplo de una página](ejemplo-markdown-pdf/basico.pdf) · [Ejemplo completo](ejemplo-markdown-pdf/documento.pdf) · [Galería de resultados](ejemplo-markdown-pdf/README.md#capturas-del-resultado) · [Manual de opciones](.agents/skills/markdown-to-pdf/README.md)

Versión estable: [v1.0.0](https://github.com/hansphp/markdown-to-pdf-skill/releases/tag/v1.0.0) · [Última publicación estable](https://github.com/hansphp/markdown-to-pdf-skill/releases/latest)

## Instalar el skill en tu Codex

Para instalar la versión estable sin clonar el repositorio completo:

```text
Usa $skill-installer para instalar el skill de
https://github.com/hansphp/markdown-to-pdf-skill/tree/v1.0.0/.agents/skills/markdown-to-pdf
Prepara sus dependencias Python en la carpeta instalada y verifica un PDF de ejemplo.
```

La carpeta instalable es **`.agents/skills/markdown-to-pdf`**; el nombre interno sigue siendo **`markdown-to-pdf`**. Incluye la URL cuando lo pidas en una conversación nueva: el nombre por sí solo no identifica el repositorio. El instalador copia el paquete; las dependencias Python se preparan después. La [guía de instalación autónoma](.agents/skills/markdown-to-pdf/INSTALL.md) cubre instalación personal, por proyecto y uso desde otra carpeta.

La etiqueta `v1.0.0` fija la versión instalada; `main` contiene el desarrollo posterior. También puedes descargar los [paquetes de la publicación](https://github.com/hansphp/markdown-to-pdf-skill/releases/tag/v1.0.0), con sus sumas SHA-256. Para usar una copia completa del repositorio, sigue los pasos siguientes.

## Empezar

Necesitas **Python 3.10 o posterior** y Chrome, Edge o Chromium instalado. Abre una terminal en la raíz de este repositorio.

### 1. Preparar las dependencias

En macOS o Linux:

```shell
python3 -m venv .agents/skills/markdown-to-pdf/.venv
.agents/skills/markdown-to-pdf/.venv/bin/python -m pip install -r .agents/skills/markdown-to-pdf/requirements.txt
```

En Windows PowerShell:

```powershell
py -3 -m venv .agents/skills/markdown-to-pdf/.venv
.agents/skills/markdown-to-pdf/.venv/Scripts/python.exe -m pip install -r .agents/skills/markdown-to-pdf/requirements.txt
```

Comprueba que el Python elegido sea 3.10 o posterior. No necesitas activar el entorno, instalar Node.js ni descargar otro navegador si ya tienes uno compatible. Mermaid, KaTeX y sus fuentes están incluidos; la instalación inicial de paquetes Python sí necesita acceso a sus paquetes.

### 2. Crear tu primer PDF

En macOS/Linux, este comando crea `mi-primer-pdf.pdf` en la raíz:

```shell
.agents/skills/markdown-to-pdf/.venv/bin/python .agents/skills/markdown-to-pdf/scripts/convert_markdown_to_pdf.py ejemplo-markdown-pdf/basico.md --no-toc --css ejemplo-markdown-pdf/recursos/personalizacion.css --strict --output mi-primer-pdf.pdf
```

En Windows, ejecuta el mismo comando cambiando `.venv/bin/python` por `.venv/Scripts/python.exe`. Si la salida ya existe, elige otro nombre; utiliza `--force` cuando quieras reemplazarla. La carpeta de destino debe existir.

Al finalizar verás la ruta creada, el motor utilizado y el resultado de la validación. `--strict` impide generar una salida con errores o advertencias. Si no se encuentra el navegador, indica su ejecutable con `--browser "ruta/al/navegador"`.

### 3. Pedírselo a tu agente

Abre este repositorio en el agente y usa uno de estos mensajes:

**Codex**:

```text
Usa $markdown-to-pdf para convertir ejemplo-markdown-pdf/basico.md
a mi-primer-pdf.pdf, sin índice de secciones, con
ejemplo-markdown-pdf/recursos/personalizacion.css y validación estricta.
```

**Claude Code**:

```text
/markdown-to-pdf convierte ejemplo-markdown-pdf/basico.md
a mi-primer-pdf.pdf, sin índice de secciones, con
ejemplo-markdown-pdf/recursos/personalizacion.css y validación estricta.
```

Ambas entradas ejecutan el mismo conversor. La [guía de integración](docs/integracion-agentes.md) explica dónde se descubre cada skill, cómo trasladarlo a otro proyecto y qué se ha verificado en cada agente.

## Del Markdown al resultado

El [ejemplo básico completo](ejemplo-markdown-pdf/basico.md) contiene metadatos, un párrafo y esta tabla:

```markdown
Tabla: Tareas {#tbl:tareas}

| Tarea | Estado |
| --- | --- |
| Escribir el contenido | Listo |
| Revisar el PDF | Pendiente |

Consulta [@tbl:tareas] para ver el avance.
```

En el PDF, la tabla recibe el rótulo **«Tabla 2. Tareas»** y la referencia se convierte en **«Consulta Tabla 2 para ver el avance»**, con un enlace a la tabla. La tabla de metadatos ocupa el número 1. El identificador `{#tbl:tareas}` no se imprime.

[![Página real del ejemplo básico: título, metadatos, tabla de tareas y referencia numerada](ejemplo-markdown-pdf/capturas/basico.png)](ejemplo-markdown-pdf/basico.pdf)

GitHub muestra el archivo fuente, pero no interpreta todas las extensiones del conversor: puede mostrar literalmente `[@tbl:tareas]`, `Tabla:` o la configuración YAML. Para ver el resultado final, abre el PDF o las capturas.

## Ejemplos para explorar

| Ejemplo | Qué enseña | Archivos |
| --- | --- | --- |
| Básico, 1 página | Título, tabla, referencia automática, encabezado y pie. | [Markdown](ejemplo-markdown-pdf/basico.md) · [PDF](ejemplo-markdown-pdf/basico.pdf) |
| Completo, 14 páginas | Portada, tres índices, tablas y figuras, Mermaid, fórmulas, notas, CSS y opciones explicadas. | [Markdown](ejemplo-markdown-pdf/documento.md) · [PDF](ejemplo-markdown-pdf/documento.pdf) |

Las siguientes imágenes son capturas de páginas del PDF completo; pulsa cada una para verla a tamaño completo.

| Tablas y figuras — página 6 | Mermaid — página 12 |
| --- | --- |
| [![Tabla de estados y figura del proceso con rótulos y referencias](ejemplo-markdown-pdf/capturas/tablas-figuras.png)](ejemplo-markdown-pdf/capturas/tablas-figuras.png) | [![Diagrama Mermaid renderizado y explicación de sus límites](ejemplo-markdown-pdf/capturas/mermaid.png)](ejemplo-markdown-pdf/capturas/mermaid.png) |

La [galería completa](ejemplo-markdown-pdf/README.md#capturas-del-resultado) incluye portada, índice, fórmulas y notas, además de los comandos para reproducir los PDFs.

## Personalizar y conocer los límites

- **Identidad:** se usa el logotipo genérico «EJEMPLO». Cámbialo con `--logo`, configúralo con `pdf.logo` u omítelo con `--no-logo`.
- **Encabezado:** la clasificación predeterminada es «CONFIDENCIAL»; los ejemplos usan «EJEMPLO». `--classification ""` la omite.
- **Presentación:** hay papel A4, Letter y Legal, orientación horizontal, portada opcional y CSS adicional.
- **Contenido técnico:** se admite un subconjunto de Markdown y de TeX; Mermaid `journey` permanece como limitación documentada. Las notas se reúnen al final del documento.
- **Validación:** errores y, en modo estricto, advertencias impiden reemplazar el PDF previo. La revisión visual complementa las comprobaciones automáticas.

Consulta el [manual completo](.agents/skills/markdown-to-pdf/README.md) para sintaxis, opciones, precedencia de YAML y terminal, recursos relativos y diagnósticos.

## Para agentes y colaboradores

| Archivo | Función |
| --- | --- |
| [SKILL.md canónico](.agents/skills/markdown-to-pdf/SKILL.md) | Instrucciones compartidas y entrada nativa de Codex. |
| [agents/openai.yaml](.agents/skills/markdown-to-pdf/agents/openai.yaml) | Nombre visible, prompt e invocación implícita en Codex. |
| [Entrada Claude Code](.claude/skills/markdown-to-pdf/SKILL.md) | Comando `/markdown-to-pdf` que delega al skill canónico. |
| [AGENTS.md](AGENTS.md) y [CLAUDE.md](CLAUDE.md) | Orientación breve para trabajar en este repositorio. |
| [Guía de integración](docs/integracion-agentes.md) | Instalación por proyecto y alcance de las pruebas de ambos agentes. |
| [Instalación desde GitHub](.agents/skills/markdown-to-pdf/INSTALL.md) | Paquete autónomo, ubicación personal y preparación de dependencias. |
| [Publicación](docs/publicacion.md) | Distribución, contenido publicado y comprobaciones de instalación desde GitHub. |

Las pruebas y el motor están en `.agents/skills/markdown-to-pdf/`. Para ejecutar la suite completa con navegador en macOS/Linux:

```shell
MDPDF_BROWSER_TESTS=1 .agents/skills/markdown-to-pdf/.venv/bin/python -B -m unittest discover -s .agents/skills/markdown-to-pdf/tests -q
```

En PowerShell, define primero `$env:MDPDF_BROWSER_TESTS="1"` y ejecuta el comando con `.venv/Scripts/python.exe`. Las [instrucciones de mantenimiento del ejemplo](ejemplo-markdown-pdf/README.md#actualizar-pdfs-y-capturas) permiten mantener sincronizados Markdown, PDF y capturas.

## Licencia

[MIT](LICENSE), Copyright (c) 2026 Hans Herrera. La licencia también se incluye dentro del paquete instalable. Los componentes incluidos conservan sus [licencias y avisos de terceros](.agents/skills/markdown-to-pdf/THIRD_PARTY_NOTICES.md).
