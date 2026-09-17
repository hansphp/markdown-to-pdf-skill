---
name: markdown-to-pdf
description: Convierte archivos Markdown locales a PDF y crea documentos de ejemplo que enseñan su formato y opciones. Úsalo para exportar una especificación, guía, informe o README, o para generar una plantilla de ejemplo con las características del conversor. No edita PDF existentes.
---

# Markdown a PDF

Convierte Markdown local a PDF y crea ejemplos explicados. Conserva el contenido del Markdown y utiliza un encabezado y un pie de página configurables, sin añadir créditos de elaboración. La plantilla incluye un logotipo genérico con la palabra **EJEMPLO**, que puede sustituirse u omitirse.

## Integración y rutas

Esta carpeta contiene el skill completo. Codex permite invocarlo como `$markdown-to-pdf`, tanto desde `.agents/skills/markdown-to-pdf/` en un proyecto como desde una instalación personal hecha con `skill-installer`. Localiza la carpeta a partir de la ruta de este `SKILL.md` cargado; no presupongas que el proyecto del documento contiene `.agents/` ni que la instalación pertenece al repositorio de origen. Los scripts, assets, manual, plantilla y entorno `.venv` son relativos a esa carpeta.

Resuelve `scripts/convert_markdown_to_pdf.py` respecto de este archivo y utiliza su ruta absoluta. El conversor resuelve imágenes y `pdf.logo` respecto del Markdown, y las rutas de terminal respecto del directorio de ejecución. Consulta [INSTALL.md](INSTALL.md) para instalación desde GitHub y preparación de dependencias en cualquier ubicación, el [manual](README.md) para las funciones que necesites y el [ejemplo integrado](assets/ejemplo/documento.md) para su sintaxis.

En la distribución completa del repositorio, Claude Code usa `/markdown-to-pdf` desde `.claude/skills/markdown-to-pdf/`, que lee este archivo. Ese adaptador no se necesita para una instalación personal en Codex.

## Crear un documento de ejemplo

Ante solicitudes como «crea un documento básico de ejemplo» o «muéstrame las características del skill», genera un Markdown editable y explicado; este modo no requiere un archivo de origen del usuario.

- Lee [assets/ejemplo/documento.md](assets/ejemplo/documento.md) y úsalo como base. Copia también su carpeta `recursos/`, que contiene una figura local, la hoja CSS opcional y su paleta importada. Respeta el destino solicitado; sin uno, crea `ejemplo-markdown-pdf/` en la raíz del proyecto, con un sufijo disponible si ya existe. Conserva las rutas relativas o ajústalas al destino, sin sobrescribir archivos ajenos a la tarea.
- Conserva los ejemplos y las explicaciones de las funciones menos evidentes: metadatos YAML como fuente del título, subtítulo y tabla inicial, portada opcional y su paginación, logotipo relativo al Markdown, precedencia de las opciones de terminal, índices de secciones, tablas y figuras, marcadores, rótulos e identificadores estables, referencias automáticas, anclas con acentos, saltos de página, escapes en tablas, validación normal o estricta, Mermaid, fórmulas y notas. Distingue la sintaxis escrita en el Markdown de las opciones de exportación; consulta el [README](README.md#opciones) para sus valores y compatibilidad.
- Los bloques `documento` y `pdf` al inicio del ejemplo son configuración activa; el ejemplo genera una portada con el logotipo incluido y ambos índices de elementos. Los datos documentales se escriben una sola vez, entre comillas; `pdf.portada`, `pdf.indice_tablas` y `pdf.indice_figuras` usan `true` o `false` sin comillas. Conserva las referencias, el diagrama, las fórmulas y las notas ejecutables; muestra errores ilustrativos solo dentro de código. Explica los campos ausentes, vacíos y las opciones que desactivan cada función. Al incorporar una función, añádela al ejemplo y actualiza su explicación.
- Entrega enlaces al Markdown y a los recursos necesarios. Genera también un PDF cuando se solicite, siguiendo el flujo de conversión. Crear solo el ejemplo no requiere instalar dependencias ni iniciar un navegador.

## Conversión

1. Resuelve la ruta del Markdown y comprueba que exista. Conserva su contenido sin cambios.
2. Usa un PDF con el mismo nombre junto al Markdown, salvo que el usuario indique otro destino. La carpeta de destino debe existir.
3. Ejecuta el script de la instalación localizada. Sustituye `/ruta/al/skill` por la carpeta que contiene este archivo y usa rutas de entrada y salida del proyecto del usuario:

   ```shell
   python3 "/ruta/al/skill/scripts/convert_markdown_to_pdf.py" "documento.md" --output "documento.pdf"
   ```

4. Comprueba que el comando termine correctamente y atiende sus diagnósticos de recursos, enlaces y maquetación. Los errores impiden publicar el PDF; el modo estricto también detiene las advertencias. No omitas una validación solicitada para conseguir una salida. Consulta [validación](README.md#validación-de-recursos-enlaces-y-maquetación) para su alcance y las opciones.
5. Revisa visualmente una muestra representativa de páginas: portada si está activa, títulos, tablas, texto en español, encabezados, pies, índices, rótulos y contenido técnico presente. Comprueba enlaces, referencias cruzadas, marcadores y la ida y vuelta de las notas en un lector de PDF. La portada ocupa una página sin encabezado ni pie repetidos y se cuenta en la numeración física de las siguientes páginas. Las comprobaciones automáticas complementan esta revisión. Si no puedes abrir o renderizar el PDF, comunica esa limitación.
6. Entrega un enlace al PDF y el motor indicado por el conversor; informa las advertencias pendientes y cualquier validación parcial. Para varios archivos, convierte cada uno por separado e informa su resultado.

Los comandos con `python3` corresponden a macOS/Linux. En Windows utiliza `.venv/Scripts/python.exe` dentro del skill instalado tras preparar las dependencias, o `py -3` si aún necesitas diagnosticar la instalación. En PowerShell, antepone `&` a una ruta de ejecutable entre comillas.

## Motores y alcance local

- El formato predeterminado requiere Python 3.10 o posterior, las dependencias fijadas en `requirements.txt` y un navegador compatible instalado, como Chrome, Edge o Chromium. El conversor puede reutilizar ese navegador sin descargar otro; `--browser` permite indicar su ejecutable.
- Las dependencias se mantienen en `.venv/` dentro del skill instalado. Si falta una dependencia necesaria en el Python utilizado y está disponible en ese entorno local, el comando se vuelve a ejecutar allí automáticamente. Nunca instala dependencias por su cuenta.
- La salida básica con `--no-branding --no-cover --no-toc --no-table-index --no-figure-index --no-bookmarks --no-strict --engine browser` utiliza Python 3.9 o posterior y el navegador instalado sin requerir paquetes adicionales cuando no se usa configuración YAML, Mermaid ni matemáticas. Interpretar los bloques `documento` o `pdf` requiere PyYAML, fijado en `requirements.txt`, incluso con esa salida básica. La portada y los índices paginados requieren Playwright y pypdf; Mermaid y las fórmulas requieren Playwright; la validación estricta requiere las comprobaciones completas. `auto` solo puede recurrir al motor básico cuando esas funciones están desactivadas o ausentes. En ese motor, la validación es parcial y se informa como advertencia; se conservan rótulos, referencias automáticas y notas.
- Usa `--diagnose` cuando necesites identificar un motor o resolver un fallo, no antes de cada conversión.
- Si falta una dependencia, informa cuál es. Una instalación autorizada se limitará al entorno local y a las versiones de `requirements.txt`; consulta la receta del README. No instales paquetes globalmente ni descargues otro navegador cuando ya haya uno compatible.
- Utiliza la implementación que cargó el agente; no la copies al proyecto de cada documento. En la distribución completa, el adaptador de Claude Code reutiliza el núcleo de `.agents/skills/markdown-to-pdf/`. La instalación personal de Codex solo necesita esta carpeta completa, según [INSTALL.md](INSTALL.md).
- Para probar cambios en el skill, usa documentos y salidas temporales en un entorno aislado; no modifiques documentos de trabajo como parte de las pruebas.

## Salida y opciones

La salida predeterminada muestra **CONFIDENCIAL** en el encabezado y un pie con título, subtítulo y `Página N de T`. Los documentos sin configuración de metadatos ni portada conservan el comportamiento anterior: el primer H1 y el primer H2 alimentan el pie. Con metadatos o portada, se utiliza la fuente común descrita abajo. Incluye el logotipo local `assets/logo.png`. `pdf.logo` permite sustituirlo desde el Markdown; `--logo` y `--no-logo` prevalecen sobre esa configuración para una conversión.

El pie reserva espacio para la numeración y abrevia con `…` el título o subtítulo que no cabe en su línea. Los textos completos se conservan en el documento.

El índice de secciones con páginas reales, los marcadores del PDF y los rótulos numerados de tablas e imágenes están activos de forma predeterminada. La portada y los índices independientes de tablas y figuras son opcionales y están desactivados si no se solicitan. Estos elementos se generan durante la exportación sin modificar el Markdown. Consulta el README para ajustar su alcance y escribir títulos e identificadores estables.

Los índices conservan el formato y las fórmulas de los encabezados y rótulos. Las referencias se resuelven también en sus textos derivados. En pies, marcadores y título interno del PDF, las fórmulas se expresan como texto legible, por ejemplo `(a)/(b)` o `x^(2)`, y las llamadas a notas como `[n]`. Las etiquetas copiadas no crean nuevas llamadas a notas ni enlaces anidados. Los marcadores con fórmulas o notas requieren pypdf para conservar sus textos y destinos. Consulta [textos de índices, pies y marcadores](README.md#textos-de-índices-pies-y-marcadores) para la notación completa.

El logotipo **EJEMPLO** es una muestra de presentación. Para cambiar el predeterminado, sustituye `assets/logo.png` por otro PNG. Para una conversión concreta, usa `--logo FILE`, `pdf.logo` o `--no-logo` según corresponda. Conserva la elección de logotipo del usuario.

```text
--output FILE                 Ruta del PDF de salida.
--paper A4|Letter|Legal        Tamaño del papel; predeterminado: A4.
--landscape                   Orientación horizontal.
--css FILE                    Hoja CSS adicional.
--engine auto|playwright|browser
--browser FILE                Ejecutable del navegador para browser o Playwright.
--cover / --no-cover           Activa u omite la portada; prevalece sobre pdf.portada.
--logo FILE                   Sustituye el logotipo para esta conversión: PNG, JPEG o SVG.
--no-logo                     Omite el logotipo y conserva los demás elementos.
--title TEXT                  Título documental; tiene prioridad sobre el YAML.
--subtitle TEXT               Subtítulo documental; tiene prioridad sobre el YAML.
--document-code TEXT          Código del documento; tiene prioridad sobre el YAML.
--document-version TEXT       Versión del documento; tiene prioridad sobre el YAML.
--document-date TEXT          Fecha del documento; tiene prioridad sobre el YAML.
--document-status TEXT        Estado del documento; tiene prioridad sobre el YAML.
--classification TEXT         Clasificación; prioridad sobre YAML; por defecto CONFIDENCIAL.
--footer                      Activa el pie; ya está activo de forma predeterminada.
--no-footer                   Desactiva solo el pie.
--no-branding                 Omite encabezado, pie y logos; conserva portada y metadatos.
--toc / --no-toc               Activa u omite el índice paginado; activo por defecto.
--toc-depth N                 Profundidad relativa del índice: 1 a 6; predeterminada: 2.
--table-index / --no-table-index    Índice de tablas; prevalece sobre pdf.indice_tablas.
--figure-index / --no-figure-index  Índice de figuras; prevalece sobre pdf.indice_figuras.
--bookmarks / --no-bookmarks   Activa u omite los marcadores PDF; activos por defecto.
--captions / --no-captions     Activa u omite los rótulos numerados generados; activos por defecto.
--strict / --no-strict         Detiene o permite advertencias; prioridad sobre pdf.validacion.
--force                       Reemplazar un PDF existente.
--diagnose                    Mostrar los motores y recursos disponibles.
```

Para omitir solo la leyenda, usa `--classification ""`. `--no-footer` conserva el encabezado; cualquier portada, encabezado, pie o marcador activo requiere Playwright. La portada y los índices paginados requieren además pypdf, incluido en las dependencias locales. Si la paginación de los índices no converge, la conversión informa un error; no entregues ese resultado como terminado.

No reemplaces un PDF existente salvo que el usuario haya solicitado sustituirlo o que sea un resultado generado durante la tarea actual; solo entonces utiliza `--force`.

## Metadatos dentro del Markdown

Para declarar los datos documentales una sola vez, coloca un bloque YAML al principio del archivo, delimitado por `---`:

```yaml
---
documento:
  titulo: "Documento de ejemplo"
  subtitulo: "Guía de características de Markdown a PDF"
  codigo: "DOC-EJEMPLO"
  version: "0.1"
  fecha: "2026-09-13"
  estado: "Borrador"
  clasificacion: "EJEMPLO"
pdf:
  portada: true
  indice_tablas: true
  indice_figuras: true
  validacion: normal
---
```

Escribe los valores como texto entre comillas, también la versión y la fecha. No inventes datos ausentes. Un campo ausente puede heredar el dato ya escrito en el H1, el subtítulo inicial reconocido o la tabla inicial `Dato | Valor`; un campo con `null` o `""` lo omite explícitamente. Las opciones de terminal prevalecen sobre el YAML y admiten `""` para omitir el dato en esa exportación. Si no hay clasificación configurada ni reconocida, se conserva **CONFIDENCIAL** en el encabezado sin añadir una fila al cuerpo.

Con `documento`, una nueva opción de metadatos o la portada activa, la exportación genera o actualiza el H1, el subtítulo y la tabla de datos iniciales sin repetirlos; reutiliza título y subtítulo en el pie y clasificación en el encabezado. Conserva la introducción, el cuerpo y el control de cambios. Sin esta configuración, usar solo `--classification` conserva el comportamiento anterior. `--no-branding` omite encabezado, pie y logotipos, pero mantiene la portada solicitada y los datos del cuerpo. El Markdown de origen permanece intacto; no hace falta escribir de nuevo los campos en el cuerpo del ejemplo.

## Portada y logotipo dentro del Markdown

`pdf.portada: true` coloca el título, subtítulo y tabla inicial en una primera página propia, seguida de los índices activos y luego de la introducción y el cuerpo. Conserva las anclas y la numeración de tablas: los metadatos siguen siendo «Tabla 1. Datos del documento» y los logotipos no se numeran como figuras. La portada se cuenta como página 1, sin imprimir allí el encabezado ni el pie repetidos; la numeración posterior continúa con las páginas físicas del PDF.

`pdf.portada: false`, o la ausencia de esta opción, conserva la presentación inicial sin una página exclusiva. `--cover` y `--no-cover` prevalecen sobre el YAML. Usa booleanos sin comillas; `"true"`, `null` o valores de texto no son válidos para `portada`.

`pdf.logo: "./imagenes/logo.png"` admite un PNG, JPEG o SVG local relativo a la carpeta del Markdown y lo utiliza en la portada y el encabezado, incluso cuando no hay portada. Omitir `logo` conserva el recurso incluido; `logo: null` lo oculta. `--logo FILE` y `--no-logo` prevalecen sobre el YAML. El archivo elegido debe existir; las rutas de terminal se resuelven desde la carpeta de ejecución.

La plantilla ajusta el título y el espaciado al papel elegido; si la portada no cabe en una página, la exportación informa un error. Revisa los textos extensos y el CSS personalizado. El bloque `pdf` no configura papel ni estilos. Consulta el [README](README.md#portada-configurable) para ejemplos y compatibilidad.

## Índices, referencias y validación

`pdf.indice_tablas: true` y `pdf.indice_figuras: true` activan listados independientes con número, título, enlace y página real. El orden es portada, índice de secciones, índice de tablas, índice de figuras e introducción y cuerpo; sin portada, se conserva el bloque inicial previo a los índices. Los listados vacíos se omiten. `--no-toc` afecta solo al índice de secciones. La tabla de metadatos se incluye y los logotipos se excluyen. Consulta [índices de tablas y figuras](README.md#índices-de-tablas-y-figuras).

Para referencias que resistan cambios de orden, escribe `Tabla: Estados {#tbl:estados}` antes de la tabla y `[@tbl:estados]` en el texto; para figuras, `Figura: Flujo {#fig:flujo}` y `[@fig:flujo]`. El conversor calcula el número y crea el enlace, incluso cuando el destino aparece después. Los identificadores duplicados, en conflicto o inexistentes producen errores. El código conserva la sintaxis literal. Los enlaces manuales `#table-N` y `#figure-N` siguen disponibles y dependen de la posición. Consulta [referencias cruzadas](README.md#referencias-cruzadas-automáticas).

`--no-captions` omite los rótulos numerados generados y conserva los párrafos explícitos `Tabla: …` y `Figura: …`, también ante Mermaid. Por ejemplo, `Tabla: Estados {#tbl:estados}` se muestra como `Tabla: Estados`; el identificador se procesa como destino sin imprimirse. Los índices activos y las referencias conservan sus números y enlaces. Los títulos inferidos siguen disponibles en los índices, pero no se añaden junto a las tablas o figuras.

`pdf.validacion` admite `normal` —predeterminado— y `estricta`; `--strict` y `--no-strict` prevalecen sobre el YAML. Las imágenes ausentes o que no cargan, las anclas rotas y las referencias sin destino son errores. Playwright añade comprobaciones de maquetación; los posibles desbordamientos, recortes verticales por altura limitada y `overflow`, y páginas vacías inesperadas generan advertencias en modo normal y detienen la salida en modo estricto. Un fallo no reemplaza el PDF previo. Consulta [validación](README.md#validación-de-recursos-enlaces-y-maquetación) para el alcance y la interpretación de diagnósticos.

## Formato y límites

Admite archivos `.md`, `.markdown` y `.mdown` en UTF-8. Procesa encabezados, párrafos, negritas, cursivas, tachado, código, listas anidadas y sus continuaciones, casillas de tareas, citas, tablas, enlaces e imágenes. Resuelve los recursos relativos desde la carpeta del Markdown. `<!-- pagebreak -->` en una línea independiente añade un salto de página.

Renderiza cercas `mermaid` como figuras y fórmulas con KaTeX. Mermaid utiliza los mismos rótulos `Figura:`, identificadores `fig:`, referencias e índice que las imágenes. Las matemáticas en línea usan `$...$` o `\(...\)`; los bloques usan `$$` o `\[` y su cierre correspondiente en líneas independientes. El código y las secuencias escapadas se conservan literalmente. Los importes como `$5` permanecen como texto. Los errores de diagrama o de fórmula detienen la exportación. Ambos motores y las fuentes matemáticas están incluidos localmente: no descargues recursos ni instales Node.js para convertir. Consulta [contenido técnico](README.md#contenido-técnico) para ejemplos y límites de TeX.

Cada bloque Mermaid admite hasta 50 000 caracteres de fuente, medidos como unidades UTF-16. El límite de 500 aristas se aplica a `flowchart`/`graph` y `agentflow`; los bloques se cuentan por separado. Ambos valores son fijos y no se amplían con opciones de terminal, YAML ni directivas internas. Si se supera un límite, informa el diagnóstico y sugiere simplificar o dividir el diagrama, o utilizar una imagen PNG local. La exportación fallida conserva el PDF previo. Consulta [diagramas Mermaid](README.md#diagramas-mermaid) para el conteo y los mensajes.

Mermaid `journey` no está admitido: sus etiquetas HTML dentro del SVG son incompatibles con esta exportación. El diagnóstico `mermaid-journey-unsupported` señala la ruta y línea del bloque y conserva el PDF previo. Explica esta limitación ante un `journey` válido y sugiere una imagen PNG local o un tipo compatible, como `flowchart`.

Las notas usan `[^id]` y una definición `[^id]: Texto`; las continuaciones llevan cuatro espacios. Se numeran por primera aparición, conservan el número al repetirse y ofrecen enlaces de ida y de regreso a cada llamada. Las definiciones se reúnen al final del documento bajo «Notas»: no se colocan al pie de cada página. Las notas ausentes, duplicadas, sin uso o anidadas producen errores. Explica esta ubicación cuando la solicitud dependa de notas en una página concreta.

El soporte de Markdown es parcial; no garantiza compatibilidad completa con CommonMark ni con todo LaTeX. El HTML escrito en el Markdown se muestra como texto, sin ejecutarse.

La hoja principal indicada con `--css` admite `@import` al principio. Sus importaciones y `url(...)` parten de la carpeta del Markdown; las rutas dentro de una hoja importada parten de esa hoja. Las imágenes remotas y los recursos remotos del CSS personalizado pueden requerir conexión. No añadas recursos externos al documento durante la conversión.

Consulta [README.md](README.md) para ejemplos de terminal, instalación local y pruebas del conversor.
