# Biblioteca de guías documentales

Esta biblioteca define cómo elaborar, revisar y mantener documentos útiles para el desarrollo de software. Su organización abarca el ciclo completo; la disponibilidad actual de las guías se indica expresamente y no supone que todas las etapas estén ya documentadas.

## Guías disponibles

| Recurso | Finalidad | Cuándo utilizarlo |
| --- | --- | --- |
| [Guía de elaboración de ERS](01_reqs/guide_ers.md) | Especificar necesidades, comportamiento, restricciones, datos y aceptación con criterios de consistencia. | Al definir un producto o una entrega y al revisar cambios en sus requisitos. |
| [Plantilla de guía documental](plantilla_guia_documental.md) | Crear una guía reutilizable para otro tipo de documento. | Al incorporar nuevos criterios de documentación a esta biblioteca. |

## Etapas y orden de consulta

| Orden | Etapa | Cuándo aplica | Documentos que podrán contar con guías |
| --- | --- | --- | --- |
| 00 | [Gestión y alcance](00_plan/README.md) | Al justificar la iniciativa, delimitar compromisos y organizar el trabajo. | Visión y alcance, plan de desarrollo, registro de riesgos y gestión de cambios. |
| 01 | [Requisitos](01_reqs/README.md) | Al acordar lo que el producto debe cumplir y cómo se aceptará. | ERS; se prevén también guías de necesidades y catálogo de reglas de negocio. |
| 02 | [Arquitectura y diseño](02_design/README.md) | Al decidir cómo satisfacer los requisitos y registrar sus consecuencias. | Arquitectura, decisiones de arquitectura, diseño de datos, interfaces y experiencia de usuario. |
| 03 | [Construcción](03_dev/README.md) | Al preparar y mantener el trabajo de implementación. | Guía de contribución, convenciones de desarrollo e instrucciones de preparación del entorno. |
| 04 | [Pruebas y aceptación](04_qa/README.md) | Al planificar verificaciones, registrar resultados y acordar la aceptación. | Plan de pruebas, casos de prueba, informe de resultados y acta de aceptación. |
| 05 | [Despliegue y entrega](05_deploy/README.md) | Al preparar una versión para su instalación, publicación y transferencia. | Plan de despliegue, procedimiento de reversión, notas de versión y manual de usuario. |
| 06 | [Operación y mantenimiento](06_ops/README.md) | Al operar el producto, atender incidencias y preparar su evolución o retiro. | Manual de operación, plan de mantenimiento, procedimientos de recuperación y plan de retiro. |

La guía ERS es la única guía de un tipo de documento disponible actualmente. Los demás documentos de la última columna son candidatos para guías futuras; sus nombres no representan archivos ya creados.

El orden facilita la navegación y las dependencias entre documentos; no exige un proceso secuencial. Una iteración puede requerir revisar requisitos, diseño, pruebas y operación conjuntamente. El alcance y la complejidad del producto determinarán qué documentos se necesitan y con qué profundidad.

## Cómo utilizar la biblioteca

1. Identificar el documento necesario, la entrega que cubrirá y sus lectores.
2. Consultar la guía disponible y reunir las fuentes que esta exige.
3. Crear el documento del producto en su espacio propio, registrando la guía y versión utilizadas.
4. Adaptar el contenido al producto y justificar los apartados que no correspondan.
5. Revisar el documento con los criterios de su guía; registrar decisiones pendientes y responsables.
6. Mantener las referencias entre documentos y evaluar su impacto cuando cambie un acuerdo.

Las guías no contienen decisiones aprobadas para un producto concreto. Un ejemplo deberá identificarse como tal; no se copiará como requisito, restricción técnica o compromiso de servicio sin una decisión del producto que lo respalde.

La documentación utilizará **producto**, **proyecto** o **sistema** hasta contar con una denominación acordada. Las cabeceras, los ejemplos y las plantillas omitirán identificaciones comerciales, logotipos, firmas y créditos, sin reservar campos vacíos para ellos. Los roles funcionales y los registros de revisión o aceptación se conservarán cuando sean necesarios para explicar y comprobar el comportamiento.

## Reglas comunes de calidad

- Redactar en español correcto y usar términos uniformes; definir siglas y tecnicismos cuando sean necesarios.
- Declarar propósito, alcance, lectores, versión, fecha y estado del documento; identificar los roles funcionales que intervienen en su revisión o aceptación.
- Diferenciar hechos confirmados, propuestas, supuestos, ejemplos y decisiones pendientes.
- Formular criterios de revisión observables y explicar qué evidencia permite comprobarlos.
- Identificar las fuentes y relacionar los elementos que dependen entre sí, sin exigir matrices innecesarias.
- Mantener un único lugar de definición para cada dato o decisión y referenciarlo desde otros apartados.
- Separar los criterios del tipo de documento de los valores y decisiones particulares de un producto.
- Justificar las exclusiones y los apartados que no apliquen; no inventar contenido para completar una plantilla.

Las ocho secciones de la ERS pertenecen a ese tipo de documento. Una guía de arquitectura, pruebas u operación deberá establecer su propia estructura, adecuada a su propósito.

## Cómo agregar una guía

Las carpetas se nombran en inglés, en minúsculas y con palabras cortas o abreviaturas reconocibles. Las etapas conservan el prefijo numérico: `plan`, `reqs`, `design`, `dev`, `qa`, `deploy` y `ops`. Se reutilizará una carpeta existente cuando corresponda al documento.

1. Comprobar que el tipo de documento tiene una finalidad distinta y que no duplica una guía existente.
2. Copiar la [plantilla de guía documental](plantilla_guia_documental.md) a la carpeta de la etapa correspondiente.
3. Nombrar el archivo como `guide_<tipo_o_sigla>.md`, con minúsculas, palabras separadas por guiones bajos y sin acentos en la ruta. El contenido conservará las tildes y la ortografía del español.
4. Completar todos los campos de la plantilla y definir la estructura del documento objetivo. Eliminar las instrucciones dirigidas a quien elabora la guía una vez atendidas.
5. Incluir criterios de elaboración, revisión, consistencia, tratamiento de pendientes y aceptación documental.
6. Comprobar su utilidad mediante un ejemplo de otro producto o un caso representativo, identificado como ilustrativo.
7. Revisar redacción, referencias, enlaces, coherencia de la plantilla y control de cambios.
8. Incorporar el enlace en este índice y en el de su etapa, indicando el estado real de la guía.

Si una guía abarca varias etapas, se ubicará en la que tenga su finalidad principal y se enlazará desde las demás; no se duplicará el archivo.

## Versiones y cambios

Cada guía tendrá una sola fuente editable. La versión, fecha, estado y cambios se registrarán dentro del archivo; el historial del repositorio conservará su evolución. No se usarán sufijos de versión ni copias denominadas «final».

Cambiar una guía no modifica automáticamente documentos de producto ya aprobados. Al revisar uno de ellos, se registrará qué versión de la guía se utiliza y qué adaptaciones requiere. Una guía solo declarará conformidad con una norma externa cuando exista una verificación documentada de esa conformidad.

[Volver al índice de documentación](../README.md).
