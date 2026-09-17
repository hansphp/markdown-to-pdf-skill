# Documentación del desarrollo

Este directorio reúne las guías y los documentos del producto a lo largo de su desarrollo, entrega y operación. El repositorio corresponde a un solo proyecto. La documentación utiliza las denominaciones **producto**, **proyecto** o **sistema** y mantiene una presentación neutral.

La [biblioteca de guías](guides/README.md) contiene los métodos reutilizables. La primera guía disponible es la [guía de elaboración de una especificación de requisitos de software (ERS)](guides/01_reqs/guide_ers.md). Las demás etapas tienen un espacio reservado y un alcance definido para incorporar guías cuando se necesiten.

Para conocer el conversor de Markdown a PDF, empieza por la [guía rápida con ejemplos y capturas](../README.md). La [integración con Codex y Claude Code](integracion-agentes.md) describe su instalación y comprobaciones.

## Organización

Las carpetas usan nombres breves en inglés. Los documentos del proyecto se agrupan por etapa directamente en `docs/`, y las guías reutilizables se mantienen en `docs/guides/`. Los prefijos numéricos conservan el orden de las etapas; los documentos se redactan en español.

```text
docs/
├── guides/
│   ├── 00_plan/      # Gestión y alcance
│   ├── 01_reqs/      # Requisitos
│   ├── 02_design/    # Arquitectura y diseño
│   ├── 03_dev/       # Construcción
│   ├── 04_qa/        # Pruebas y aceptación
│   ├── 05_deploy/    # Despliegue y entrega
│   └── 06_ops/       # Operación y mantenimiento
└── 01_reqs/
    └── ers.md
```

| Contenido | Ubicación | Uso |
| --- | --- | --- |
| Guías reutilizables | `guides/` | Definen cómo elaborar y revisar un tipo de documento para distintos productos. |
| Plantilla para nuevas guías | [Plantilla de guía documental](guides/plantilla_guia_documental.md) | Permite incorporar nuevos tipos de documentos con criterios comunes de calidad. |
| Documentos del proyecto | Carpetas por etapa en `docs/`; disponible: [ERS del proyecto](01_reqs/ers.md) | Contienen los acuerdos, requisitos, diseños y evidencias del proyecto. La ERS tiene por ahora un archivo inicial vacío. |
| Fuentes del proyecto | Ubicación prevista: `sources/` | Permitirán identificar el origen y la vigencia de las decisiones del proyecto. |

La ruta de fuentes está prevista y todavía no se ha creado. Las demás carpetas de documentos se crearán directamente en `docs/` cuando se necesiten, con los mismos nombres de etapa de la biblioteca, como `02_design/` o `04_qa/`. Al redactarse, cada documento identificará la guía y versión utilizadas.

Una guía explica **cómo escribir y revisar**; un documento del proyecto establece **lo que se acuerda para el proyecto**; una fuente aporta **el origen o la evidencia de una decisión**. Esta separación permite distinguir los criterios de elaboración de las decisiones concretas del proyecto.

## ERS del proyecto

La ERS del proyecto se redactará en [`01_reqs/ers.md`](01_reqs/ers.md), cuya ruta desde la raíz del repositorio es `docs/01_reqs/ers.md`. El archivo está creado y vacío; aún no contiene requisitos.

La guía se llama `guide_ers.md`, que cumple la convención `guide_<tipo_o_sigla>.md` y describe su función. Al comenzar la ERS del proyecto, se utilizará la plantilla del anexo A de la [guía](guides/01_reqs/guide_ers.md).

## Mantenimiento

Cada guía tendrá un único archivo editable. Su versión y evolución se registrarán dentro del documento y en el historial del repositorio; no se crearán copias con sufijos como `_v2`, `_final` o `_definitivo`.

Los índices deberán distinguir entre guías disponibles y guías previstas. Solo se añadirán enlaces a archivos existentes, y cualquier cambio de ubicación deberá actualizar sus referencias.

## Exportación local a PDF

El skill [Markdown a PDF](../.agents/skills/markdown-to-pdf/README.md) está instalado en `.agents/skills/markdown-to-pdf/`. Codex lo descubre allí y Claude Code usa un adaptador en `.claude/skills/markdown-to-pdf/`. El formato predeterminado utiliza Playwright en el entorno local del skill y un navegador compatible instalado. Genera un índice con enlaces y páginas reales, marcadores de navegación y rótulos numerados de tablas e imágenes, sin modificar el Markdown ni duplicar los metadatos. Incluye el logotipo genérico **EJEMPLO**, la leyenda **CONFIDENCIAL**, título, subtítulo y `Página N de T`. Esta presentación no añade créditos de elaboración ni define la identidad del producto.

Se puede solicitar su uso con una instrucción como esta:

```text
Usa $markdown-to-pdf para convertir docs/guides/01_reqs/guide_ers.md a PDF.
```

En Claude Code, usa `/markdown-to-pdf convierte docs/guides/01_reqs/guide_ers.md a PDF`.

La opción `--no-branding` omite el encabezado y el pie; `--classification ""` omite solo la leyenda y `--no-footer` omite solo el pie. `--no-logo` omite solo el logotipo. Para cambiarlo, usa `--logo` en la terminal o `pdf.logo` en el YAML del documento. El contenido y los criterios de neutralidad de las guías ERS permanecen independientes de este formato de exportación.

El índice, los marcadores y los rótulos están activos por defecto; se pueden omitir con `--no-toc`, `--no-bookmarks` y `--no-captions`. El [manual](../.agents/skills/markdown-to-pdf/README.md#requisitos) explica la salida básica con validación parcial y los requisitos de cada función.

Las instrucciones, la instalación local y las opciones del conversor se mantienen en el README del skill. Su instalación no modifica la configuración compartida de Codex.
