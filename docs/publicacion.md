# Publicación en GitHub

Repositorio: [hansphp/markdown-to-pdf-skill](https://github.com/hansphp/markdown-to-pdf-skill). Compatible con Codex y Claude Code. El identificador interno permanece **`markdown-to-pdf`**.

Primera versión estable: **v1.0.0**, disponible en [Releases](https://github.com/hansphp/markdown-to-pdf-skill/releases/tag/v1.0.0). El enlace [Latest](https://github.com/hansphp/markdown-to-pdf-skill/releases/latest) permite encontrar la publicación estable más reciente.

## Contrato de instalación

| Dato | Valor |
| --- | --- |
| Carpeta instalable | `.agents/skills/markdown-to-pdf` |
| Entrada requerida | `.agents/skills/markdown-to-pdf/SKILL.md` |
| Instrucciones de instalación incluidas | [INSTALL.md](../.agents/skills/markdown-to-pdf/INSTALL.md) |
| Invocación en Codex | `$markdown-to-pdf` |
| Dependencias | Python 3.10+, paquetes de `requirements.txt` y Chrome, Edge o Chromium |
| Preparación del entorno | `.venv/` junto al skill instalado; no se distribuye un entorno preconstruido |
| Licencia propia | [MIT](../LICENSE), también incluida dentro del skill |
| Componentes incluidos | Mermaid, KaTeX y fuentes con sus [licencias y avisos](../.agents/skills/markdown-to-pdf/THIRD_PARTY_NOTICES.md) |

Mantén estable la ruta de la carpeta instalable: forma parte de la URL que usarán los lectores. Para una versión reproducible puedes publicar una etiqueta de Git y usarla en lugar de `main`.

No hace falta incluir el repositorio en un catálogo para que Codex lo instale mediante una URL accesible. La publicación tampoco lo añade automáticamente a un catálogo ni permite identificarlo inequívocamente usando solo su nombre.

## Contenido de la distribución

Publica la carpeta completa del skill, incluyendo scripts, assets, fuentes, licencias y requisitos. El adaptador `.claude/skills/markdown-to-pdf/`, los archivos `AGENTS.md` y `CLAUDE.md`, el README, los ejemplos, PDFs y capturas permiten utilizar y explorar el repositorio completo.

`docs/guides/` es una biblioteca documental complementaria; no interviene en la instalación del conversor. El instalador de Codex copia solo la carpeta del skill seleccionada.

El `.gitignore` excluye `.venv`, cachés, archivos temporales del sistema y configuración personal de Claude. Puedes revisar el conjunto publicable antes del primer commit con:

```shell
git ls-files --cached --others --exclude-standard
```

## Publicación y verificación

Publicado en `main` y verificado el **16 de septiembre de 2026**, con autor **Hans Herrera** (`hans.php@gmail.com`), conservando el historial existente:

- Metadatos válidos del skill y detección nativa de Codex comprobada tanto en este proyecto como en un repositorio temporal que contiene solo el paquete: una entrada habilitada y cero errores, desde la raíz y una subcarpeta.
- Paquete autónomo: las instrucciones y recursos se resuelven desde el skill instalado, sin depender del proyecto original.
- Instalador de Codex ejecutado contra la URL pública real del skill: descarga, extracción y copia de 117 archivos idénticos al paquete publicado. Codex detectó el paquete descargado como una entrada habilitada, sin errores. El rechazo de una instalación duplicada se verificó también con un ZIP local.
- Entorno `.venv` creado desde cero en la instalación temporal, seis dependencias instaladas desde `requirements.txt` y `pip check` sin conflictos. Conversión desde otra carpeta con espacios: PDF de 14 páginas con portada, índices, Mermaid, fórmulas y notas, en modo estricto y sin modificar el Markdown. También se comprobó la reutilización automática de ese entorno al iniciar con otro Python.
- Recursos de terceros verificados: coinciden las 65 huellas SHA-256 del manifiesto; se incluyen MIT y OFL.
- Archivos publicables revisados sin credenciales evidentes, referencias a la marca retirada ni rutas personales; PDFs y capturas incluidos. Ningún archivo supera 7 MB.
- Consistencia final de rutas: 27 archivos Markdown y 168 enlaces locales comprobados; rutas del adaptador, CSS, SVG y anclas generadas correctas. No hay rutas personales fijadas ni referencias necesarias fuera del paquete autónomo. Las rutas absolutas ilustrativas están señaladas y las ubicaciones estándar del navegador son candidatos de detección.
- Suite completa ejecutada desde una copia limpia, con un directorio de trabajo externo: 351 pruebas con navegador aprobadas, sin omisiones. Después se aisló únicamente el skill y se generó un PDF de 14 páginas desde rutas con espacios y acentos, en modo estricto y conservando el Markdown. La prueba utilizó el intérprete de pruebas existente; la instalación de dependencias desde cero se verificó por separado, como se indica arriba.

La descarga pública, la instalación de dependencias y la conversión se comprobaron desde una carpeta temporal ajena al proyecto original, en macOS con Google Chrome. La sesión real de Claude Code sigue sin comprobarse porque su CLI no está instalado; el adaptador y sus comandos sí se probaron.

## Publicar futuras actualizaciones

1. Usa el repositorio `hansphp/markdown-to-pdf-skill` y la rama `main`. Conserva las URL de instalación alineadas con ese destino; si se mueve el repositorio, actualízalas.
2. Revisa `git remote -v` y asigna el destino elegido antes de subir. Comprueba que el propietario, el nombre del repositorio y la rama coincidan con las URL de instalación; no reutilices sin verificar un remoto anterior del proyecto.
3. Crea un commit con los archivos revisados y publícalo conservando el historial existente. Conserva también el `LICENSE` de la raíz y su copia dentro del paquete instalable.
4. Desde una carpeta temporal, repite la instalación mediante la URL pública real, prepara sus dependencias y genera el PDF de ejemplo con `--strict`. Confirma que Codex detecta `$markdown-to-pdf` desde otro proyecto.

El [inicio del README](../README.md#instalar-el-skill-en-tu-codex) y [INSTALL.md](../.agents/skills/markdown-to-pdf/INSTALL.md#pedir-la-instalación-a-codex) incluyen la solicitud para una instalación futura.

## Preparar una versión estable

Cada publicación estable utiliza una etiqueta de versión y archivos generados desde el mismo commit. Para v1.0.0 se distribuyen el núcleo autónomo, el repositorio completo y `SHA256SUMS.txt`. La estructura y el uso de cada descarga están en [INSTALL.md](../.agents/skills/markdown-to-pdf/INSTALL.md#paquetes-de-la-publicación-estable).

Genera los ZIP con `git archive` para incluir únicamente archivos versionados, sin `.git`, entornos ni cachés. Verifica el contenido extraído, las licencias, los recursos del manifiesto y una conversión estricta. Publica las sumas de ambos archivos. Conserva la etiqueta y los archivos de una versión publicada; los cambios posteriores deben recibir una versión nueva.

Marca la publicación como estable y `Latest`, sin la opción de prerelease. Conserva en las notas los requisitos y el alcance de la validación: las pruebas actuales se ejecutan en macOS con Google Chrome; Windows/Linux tienen instrucciones, y la sesión real de Claude Code todavía no se ha verificado.
