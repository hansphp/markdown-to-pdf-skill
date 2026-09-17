# Guía de criterios para elaborar una especificación de requisitos de software (ERS)

> Estructura, reglas de redacción y controles de consistencia para especificar productos de software distintos con un mismo nivel de precisión.

| Dato | Valor |
| --- | --- |
| Tipo de documento | Guía reutilizable de elaboración y revisión de ERS |
| Versión | 0.3 |
| Fecha | 2026-09-07 |
| Estado | Borrador revisado |
| Referencia de análisis | Documento de trabajo utilizado para contrastar la estructura, la precisión y la cobertura; no incluido en esta distribución |
| Destinatarios | Responsables de producto, analistas, representantes de los usuarios y equipos de desarrollo y aseguramiento de la calidad |
| Aplicación | Elaboración de una ERS para cualquier producto, ajustando actores, entidades, reglas y restricciones al dominio correspondiente |

Esta guía forma parte de la [biblioteca de guías de documentación](../README.md). Su contenido se mantiene en este único archivo, incluidos el ejemplo, la lista de revisión y la plantilla. Para especificar un producto, se copiará la plantilla del anexo A en un documento propio del producto y se conservará la guía como referencia.

La documentación utilizará las denominaciones **producto**, **proyecto** o **sistema** mientras no exista un nombre acordado. Se omitirán identificaciones comerciales, logotipos, firmas y créditos en cabeceras, ejemplos, plantillas e instrucciones de generación, sin añadir campos vacíos ni marcadores para esos datos. La referencia de análisis aportó criterios documentales; sus identidades y decisiones particulares no se trasladarán al nuevo producto.

**Accesos de consulta:** [estructura de la ERS](#3-estructura-que-deberá-tener-cada-ers), [reglas de consistencia](#5-reglas-de-consistencia-entre-secciones), [aceptación y trazabilidad](#6-criterios-de-aceptación-y-trazabilidad), [lista de revisión](#10-lista-de-revisión-y-criterio-de-terminación), [plantilla](#anexo-a-plantilla-base-para-un-nuevo-producto) e [instrucción de generación](#anexo-b-instrucción-reutilizable-para-generar-una-ers).

## 1. Propósito y forma de uso

Esta guía define cómo producir una ERS que permita diseñar, desarrollar y aceptar un producto sin que el equipo de implementación tenga que inventar decisiones de negocio. Se elaboró a partir de un documento de referencia para organizar y conectar funciones, datos, estados, restricciones y resultados verificables. Esa fuente no se distribuye aquí; los criterios necesarios para aplicar la guía están incluidos en este archivo.

La ERS resultante deberá explicar **qué debe hacer el producto, quién puede hacerlo, bajo qué condiciones, qué cambia, qué sucede cuando no puede realizarse y cómo se comprobará**. El detalle deberá ser suficiente para que dos lectores independientes lleguen a la misma interpretación del comportamiento requerido.

Para utilizar esta guía:

1. Reunir las necesidades y decisiones disponibles del nuevo producto, identificando sus fuentes.
2. Redactar la ERS con las ocho secciones definidas en el apartado 3.
3. Aplicar las reglas de redacción y consistencia de los apartados 4 a 7.
4. Registrar las decisiones faltantes conforme al apartado 8.
5. Revisar el documento con la lista del apartado 10 antes de declararlo listo para su aprobación o implementación.

Los criterios de esta guía son criterios de calidad documental. Los requisitos del nuevo producto solo serán obligatorios cuando hayan sido acordados y aprobados para ese producto. Un ejemplo, una propuesta o una decisión pendiente no deberá presentarse como un requisito aprobado.

### 1.1 Qué se conserva de la ERS de referencia

| Patrón observado | Ubicación en la ERS de referencia | Criterio reutilizable |
| --- | --- | --- |
| Propósito, alcance y exclusiones explícitas | 1, 1.1 y 1.2 | Delimitar el compromiso de desarrollo y el carácter de cada parte del documento. |
| Actores y dependencias de infraestructura | 2 y `RF-ADM-04` | Distinguir capacidades del producto, responsabilidades externas y precondiciones de operación. |
| Requisitos agrupados por dominio e identificados | 3 y 4.1–4.2 | Organizar por capacidades y permitir referencias inequívocas. |
| Consultas con reglas de búsqueda y orden | `RF-PAR-05`, `RF-ADM-07` y `RF-AUD-07` | Definir campos visibles, filtros, coincidencias, orden, desempate y paginación. |
| Identificadores y enlaces con ciclo de vida propio | `RF-EVT-04` a `RF-EVT-08` y `RF-PRI-02` | Especificar generación, unicidad, permanencia, contexto y respuesta ante valores inválidos. |
| Estados y efectos de las operaciones | 3.3, 3.5 y 3.6 | Especificar transiciones, bloqueos, consecuencias y excepciones. |
| Límites temporales exactos | `RF-EVT-09`, `RF-INS-05` y `RF-ASI-02` | Definir reloj, zona, precisión e inclusión o exclusión del límite. |
| Integridad y auditoría ligadas al cambio de negocio | 3.9 y 4 | Explicitar qué cambios deben ocurrir juntos y qué se revierte si hay un error. |
| Contratos de configuración, datos y archivos | 5 | Documentar entradas válidas, normalización y resultados de rechazo. |
| Transformación controlada de contenido | `RF-PRI-03` y `RF-EVT-14` | Definir contenido permitido, variables, edición, versiones y tratamiento de datos ausentes. |
| Interfaz descrita mediante condiciones observables | 3.8 y 4.2 | Convertir la jerarquía visual, la exposición de información y la adaptación a pantallas en condiciones comprobables. |
| Aceptación de resultados satisfactorios, rechazos, fallas y casos límite | 6 | Comprobar el comportamiento completo, incluidos sus límites. |
| Pendientes separados y control de versiones | 7 y 8 | Evitar decisiones implícitas y conservar la evolución del acuerdo. |

Esta guía añade mecanismos de revisión que el original no formaliza por completo: identificadores para todos los requisitos técnicos y criterios de aceptación, glosario, matriz de trazabilidad y registro estructurado de pendientes. Son mejoras metodológicas para facilitar la reutilización; no se atribuyen al documento de referencia como si ya estuvieran presentes.

### 1.2 Qué deberá definirse nuevamente para cada producto

No se deberán trasladar automáticamente nombres de organizaciones, entidades del dominio, actores, rutas, credenciales, tecnologías, algoritmos y parámetros, formatos, límites, volúmenes, colores ni políticas de conservación del sistema de asistencia.

La elección de una base de datos, el mecanismo de configuración, la infraestructura de acceso, la longitud de los códigos públicos, la duración de las sesiones, el tamaño máximo de los archivos y las dimensiones de las tarjetas son decisiones particulares. El criterio reutilizable consiste en **definir y justificar la restricción aplicable**, junto con su verificación.

También deberán distinguirse los ejemplos de dimensionamiento de los compromisos reales de capacidad. En la referencia, un cupo de 70 es ilustrativo y no se impone a las actividades; por separado, la sección técnica sí establece una capacidad mínima de 1500 participantes. Una cifra será obligatoria por su declaración expresa como requisito, nunca por aparecer en un escenario de ejemplo.

### 1.3 Información que se debe reunir

Antes de redactar, se preparará un inventario de la información disponible. Para cada decisión confirmada se conservará una referencia a su fuente y a la persona o al rol que la validó.

| Tema | Información necesaria para elaborar la ERS |
| --- | --- |
| Problema y objetivo | Situación actual, necesidad que debe atenderse y resultado esperado. |
| Alcance de la entrega | Capacidades incluidas, exclusiones y orden de prioridad acordado, si existe. |
| Usuarios y responsabilidades | Roles, permisos, unidad de contexto y responsables de las decisiones. |
| Procesos de negocio | Flujo habitual, excepciones, estados, plazos y operaciones automáticas. |
| Datos y documentos | Entidades, relaciones, formularios, archivos, fuentes y salidas esperadas. |
| Condiciones de operación | Entorno previsto, volúmenes, concurrencia, dependencias y restricciones confirmadas. |
| Aceptación | Quién revisará el producto, qué resultados espera comprobar y qué evidencia necesita. |
| Fuentes | Acuerdos, documentos, ejemplos y propuestas, distinguiendo su estado de validación. |

La información desconocida se registrará conforme al apartado 8; no impedirá documentar las partes que sí estén definidas. Si dos fuentes se contradicen, se registrará la decisión que debe resolverse en lugar de elegir una interpretación sin acuerdo.

### 1.4 Resultado esperado al utilizar la guía

El resultado será un archivo de ERS del producto que contenga sus ocho secciones, los requisitos identificados, los contratos de datos aplicables, los criterios de aceptación, la matriz de trazabilidad, los pendientes y el control de cambios. La revisión y, cuando exista, la aprobación se registrarán mediante los formatos del apartado 10.

La ERS identificará la versión de esta guía utilizada. Su estado seguirá siendo **Borrador** o **En revisión** mientras no exista una aprobación del alcance correspondiente. Los ejemplos didácticos y las instrucciones de la plantilla se sustituirán por contenido del producto antes de entregar la ERS.

## 2. Principios de calidad de la especificación

| Principio | Criterio de cumplimiento |
| --- | --- |
| Necesidad | Cada requisito responde a una necesidad, decisión o restricción identificable del producto. |
| Claridad | La obligación, su objeto y sus condiciones se reconocen sin inferir intenciones; las operaciones identifican también actor y acción. |
| Unidad | Cada identificador expresa un comportamiento principal o una regla coherente; sus condiciones y efectos permanecen unidos. |
| Verificabilidad | Existe una observación, prueba o inspección que permite decidir si se cumple. |
| Completitud del comportamiento | Se describen entradas, resultado correcto, rechazo y efectos secundarios relevantes. |
| Consistencia | Un dato, estado, permiso, plazo o cálculo conserva el mismo significado en todas las secciones. |
| Trazabilidad | Es posible relacionar necesidad, requisito y criterio de aceptación, y localizar los elementos afectados por un cambio. |
| Viabilidad | La capacidad o restricción se puede evaluar con el entorno y los recursos acordados; las dudas quedan registradas. |
| Separación de responsabilidades | El documento identifica lo que construye el equipo y lo que deben aportar terceros o el equipo de operación. |
| Decisiones explícitas | Los vacíos permanecen como pendientes; no se rellenan con supuestos silenciosos. |

La precisión no exige definir toda la arquitectura. La ERS deberá describir comportamiento y restricciones necesarias. El diseño de componentes, el esquema físico de datos y los detalles internos se documentarán por separado, salvo que una elección técnica forme parte expresa del acuerdo del producto. Si se incluye una, se deberá indicar su fuente o motivo.

Esta guía toma como referencia el archivo indicado; no declara conformidad con una norma externa de especificación.

### 2.1 Términos utilizados en la guía

| Término | Significado |
| --- | --- |
| Dominio | Área de actividad a la que pertenece el producto, con sus conceptos y reglas. |
| Entidad | Elemento del negocio sobre el que se conserva información, como un equipo o un préstamo. |
| Precondición | Condición que debe cumplirse antes de ejecutar una operación. |
| Contrato de datos | Definición acordada de los campos, formatos, validaciones y resultados de un intercambio de información. |
| Línea base aprobada | Versión de la ERS aceptada como referencia para un alcance determinado; sus cambios posteriores deben registrarse. |
| Evidencia de verificación | Registro, medición o documento que permite comprobar un resultado. |
| UTC | Tiempo universal coordinado; referencia utilizada para expresar instantes sin depender de la zona horaria local. |

## 3. Estructura que deberá tener cada ERS

Se conservarán las ocho secciones principales del documento de referencia y su orden. Los subapartados funcionales se adaptarán al nuevo dominio. Una sección que no aplique deberá indicarlo con su justificación; no se inventarán funciones para completarla.

### 3.1 Portada y metadatos

La cabecera deberá contener el título **Especificación de requisitos de software (ERS)** y una frase que indique su función como base de requisitos para diseño, desarrollo y aceptación. El producto se identificará mediante su descripción funcional y el alcance de la entrega; no se le asignará un nombre propio a partir del repositorio, del directorio de trabajo ni de los ejemplos de referencia.

| Dato mínimo | Criterio |
| --- | --- |
| Producto y entrega | Descripción funcional del sistema y, cuando corresponda, módulo o entrega cubierta. |
| Tipo de documento | Declara que es una base de requisitos. |
| Versión | Identificador consistente con el control de cambios. |
| Estado | Borrador, en revisión o línea base aprobada; debe reflejar la situación real. |
| Fecha | Fecha de esa versión, en formato `AAAA-MM-DD`. |
| Fuentes | Documentos, acuerdos o sesiones identificables; diferenciar fuentes confirmadas de propuestas. |
| Guía utilizada | Nombre y versión de la guía aplicada a la elaboración de la ERS. |

No se copiarán la versión, fecha, estado de aprobación ni fuentes de la ERS de referencia como si correspondieran al nuevo producto.

Los roles de operación, revisión y aceptación se definirán donde intervengan en los requisitos o en sus registros de verificación. Describen responsabilidades del proceso y no requieren atribuciones comerciales. La ausencia de un nombre propio del producto no impedirá documentar ni revisar sus requisitos.

### 3.2 Sección 1: Propósito y alcance

Deberá declarar el problema que resuelve el producto, sus usuarios y el resultado esperado. Incluirá una lista concreta de capacidades comprendidas en la entrega.

El subapartado **1.1 Fuera de alcance** enumerará funciones y trabajos excluidos. Si una exclusión es necesaria para operar, deberá referenciar una dependencia con responsable y condición de disponibilidad. Excluir el desarrollo de una integración o una instalación no equivale a eliminar su necesidad operativa.

El subapartado **1.2 Componentes del documento** distinguirá requisitos obligatorios tras su aprobación, estructuras de entrada, base de aceptación, exclusiones, pendientes e información de cambios. También identificará documentos complementarios y su relación con la ERS, cuando existan.

Se añadirá un glosario breve dentro de esta sección cuando haya términos que puedan confundirse. Se deberá acordar un nombre por concepto y distinguir sinónimos de conceptos diferentes; por ejemplo, una cancelación puede conservar el historial mientras una eliminación altera la visibilidad operativa.

### 3.3 Sección 2: Actores y dependencias

Se identificarán personas, roles, sistemas externos y procesos automáticos que intervengan. El actor **Sistema** se incluirá cuando existan acciones automáticas con efectos de negocio.

| Elemento | Tipo | Responsabilidad o capacidad | Límite o precondición | Responsable externo, si aplica |
| --- | --- | --- | --- | --- |
| `<actor o dependencia>` | `<rol / sistema / servicio / procedimiento>` | `<qué realiza o aporta>` | `<qué no puede hacer o qué necesita>` | `<responsable>` |

Los permisos se especificarán por rol y contexto: organización, proyecto, cuenta, expediente u otra unidad de aislamiento. No bastará con decir que alguien está autenticado si también debe pertenecer al contexto del registro solicitado.

### 3.4 Sección 3: Requisitos funcionales

Se dividirá por capacidades del negocio. Los nombres de los apartados deberán corresponder al nuevo producto, por ejemplo inventario, préstamos y devoluciones, en lugar de conservar eventos y participantes.

Cada grupo cubrirá las operaciones aplicables y sus reglas: crear, consultar, buscar, modificar, aprobar, cancelar, cerrar, eliminar, exportar u otras propias del dominio. No se exigirá implementar todas esas operaciones; una entidad puede ser inmutable o admitir solo consulta.

Las reglas de negocio podrán integrarse en los requisitos funcionales, como en el original. Si una misma regla gobierna varias funciones, se definirá una sola vez y se referenciará desde ellas. Las tablas de campos, estados y permisos complementarán los requisitos identificados.

Los procesos automáticos, reportes, auditoría, privacidad y exposición de información se incluirán cuando apliquen. Una condición de interfaz será funcional si modifica el acceso a una capacidad o información; las condiciones medibles de presentación y uso se podrán agrupar en requisitos no funcionales.

### 3.5 Sección 4: Requisitos técnicos mínimos

Contendrá las restricciones necesarias de seguridad, integridad, tiempo, capacidad, compatibilidad, operación e interfaz. Cada requisito tendrá identificador y una forma de verificación.

| Aspecto por evaluar | Información que deberá quedar definida cuando aplique |
| --- | --- |
| Plataforma y persistencia | Restricción tecnológica acordada, integridad requerida y condiciones de arranque. |
| Seguridad y sesiones | Autenticación, autorización, protección de secretos, aislamiento, vencimiento y renovación. |
| Tiempo | Reloj de autoridad, zona horaria, precisión, almacenamiento e interpretación. |
| Concurrencia | Reglas que deben preservarse con solicitudes simultáneas, duplicadas o reintentadas. |
| Capacidad y desempeño | Volumen, concurrencia, operación medida, umbral, unidad y entorno de verificación. |
| Compatibilidad | Plataformas, dispositivos o navegadores objetivo y condiciones comprobables. |
| Interfaz y accesibilidad | Tamaños de referencia, jerarquía, visibilidad, teclado, foco y comunicación de estados. |
| Operación | Configuración, dependencias, fallas, recuperación y responsabilidades de despliegue. |
| Continuidad y recuperación | Interrupción y pérdida de datos tolerables, condiciones de respaldo y resultados esperados de la restauración. |
| Aseguramiento de la calidad | Entorno de prueba, aislamiento, reproducibilidad y evidencia exigida. |

Se deberá distinguir capacidad almacenada de usuarios simultáneos y tiempo de respuesta. No se deducirá una de las otras. Expresiones como “rápido”, “seguro”, “intuitivo”, “actual” o “contenido ordinario” deberán acompañarse de una condición evaluable. Si falta el umbral o el conjunto de datos de referencia, se registrará la decisión pendiente.

Cuando se exijan pruebas reproducibles, se definirán los datos y la configuración de referencia, el procedimiento de ejecución y las evidencias que se conservarán. Las pruebas que modifiquen información utilizarán datos y recursos aislados de producción. El plan de pruebas detallará los casos y su ejecución sin modificar los resultados exigidos por la ERS.

### 3.6 Sección 5: Estructuras de entrada

Definirá los contratos de configuración, formularios, archivos, cargas masivas y entradas de integraciones que realmente existan. Los datos compartidos por varios canales tendrán una definición común.

| Campo o clave | Tipo lógico y formato | Obligatorio | Predeterminado | Normalización y validación | Efecto si falta o es inválido |
| --- | --- | --- | --- | --- | --- |
| `<nombre estable>` | `<texto, entero, fecha, enumeración…>` | `<sí / no / condición>` | `<valor acordado / ninguno>` | `<longitud, unidad, rango, comparación…>` | `<rechazo / omisión / sustitución acordada>` |

Se utilizarán tipos lógicos cuando no haya una restricción física aprobada. Los nombres técnicos de campos se escribirán de manera uniforme y se relacionarán con sus etiquetas visibles cuando estas sean distintas.

Para configuración, se definirán ubicación o mecanismo, claves, interpretación de valores, protección de secretos, validación al arranque y momento de aplicación de cambios. Un ejemplo de configuración deberá cumplir su propia tabla de reglas y utilizar marcadores inequívocos para secretos que deban suministrarse en el despliegue.

Se distinguirán una clave ausente, un valor vacío y un valor inválido. Para cada caso se definirá si se utiliza un valor predeterminado acordado, se rechaza el cambio o se impide el arranque. Si la configuración utiliza texto, su contrato indicará codificación, espacios, delimitadores, comentarios, caracteres literales y sustitución de variables, según corresponda al mecanismo elegido. Se describirá qué ocurre al iniciar por primera vez, al reiniciar con cambios y al detectar datos o recursos incompatibles con la configuración. Los errores no deberán revelar secretos.

### 3.7 Sección 6: Criterios mínimos de aceptación

Contendrá escenarios verificables vinculados a requisitos. Deberá cubrir los flujos satisfactorios, los rechazos, los casos límite y las fallas que puedan cambiar el resultado. Los criterios no introducirán funciones, límites ni compromisos ausentes en las secciones de requisitos.

Se incluirá la matriz de trazabilidad como subapartado o anexo. Los criterios relativos a una responsabilidad externa se identificarán como verificación de precondición operativa y no se mezclarán con la aceptación del trabajo de desarrollo.

### 3.8 Sección 7: Requiere definición

Concentrará las decisiones sin acuerdo y sus impactos. Los requisitos afectados referenciarán el identificador del pendiente. Una propuesta deberá quedar expresamente marcada como propuesta, sin convertirse en un valor predeterminado por omisión.

La frase “No quedan definiciones pendientes identificadas para iniciar el desarrollo” solo se utilizará después de revisar el documento y confirmar que no contiene vacíos que afecten esa entrega.

### 3.9 Sección 8: Control de cambios

Contendrá versión, fecha y descripción concreta del cambio. Para modificaciones posteriores a la línea base se identificarán también los requisitos afectados y la fuente de la decisión.

| Versión | Fecha | Cambio | Identificadores afectados | Fuente o responsable del acuerdo |
| --- | --- | --- | --- | --- |
| `<versión>` | `<AAAA-MM-DD>` | `<comportamiento incorporado, corregido o retirado>` | `<identificadores>` | `<referencia>` |

Cuando cambie una regla, se actualizarán los criterios de aceptación, los contratos de datos, las tablas y la documentación complementaria que resulten afectados. No se supondrá que la versión del documento debe coincidir con la del software o sus recursos estáticos: esa relación requiere un acuerdo específico.

## 4. Convenciones de identificación y redacción

### 4.1 Identificadores

| Tipo | Patrón | Uso |
| --- | --- | --- |
| Requisito funcional | `RF-<DOMINIO>-<NN>` | Capacidad o regla de negocio asociada a una función. |
| Requisito no funcional | `RNF-<ASPECTO>-<NN>` | Condición de calidad, seguridad, operación, interfaz o aseguramiento. |
| Restricción técnica | `RT-<ASPECTO>-<NN>` | Decisión técnica obligatoria, si se prefiere distinguirla de los RNF. |
| Criterio de aceptación | `CA-<GRUPO>-<NN>` | Escenario o comprobación vinculada a uno o varios requisitos. |
| Decisión pendiente | `PD-<NN>` | Dato, regla o responsabilidad todavía sin acuerdo. |

El uso de `RT` es opcional: las restricciones podrán agruparse como `RNF-TEC` si se mantiene una convención única. No se duplicará una misma obligación bajo ambos prefijos. El catálogo de abreviaturas deberá definirse para cada ERS.

Los identificadores serán únicos y estables; no dependerán del número de página. La numeración podrá superar dos dígitos si resulta necesario. Reordenar un apartado no cambiará los identificadores, y los identificadores retirados no se reutilizarán para requisitos diferentes. Las referencias deberán apuntar a un elemento existente.

### 4.2 Lenguaje normativo

- **Deberá / realizará / se rechazará:** expresa una obligación o resultado exigido.
- **Podrá:** expresa una capacidad que el sistema deberá ofrecer al actor; no significa que implementarla sea opcional.
- **No permitirá / no deberá:** expresa una prohibición verificable.
- **Opcional:** deberá aclarar si describe un dato que puede omitirse, una acción voluntaria del usuario o una función fuera de la entrega. Son situaciones distintas.
- **Se recomienda:** expresa una preferencia que no será causa de rechazo, salvo que otro requisito la convierta explícitamente en obligación.
- **Por definir:** identifica una decisión abierta y deberá enlazarse a un `PD`.

Se evitarán “etcétera”, “según corresponda”, “adecuado”, “normal” o “cuando sea necesario” si dejan abierta una regla. Los textos literales de interfaz se marcarán en **negritas**; campos, rutas, fórmulas e identificadores se escribirán en `código`. Un texto será literal solo cuando su redacción exacta sea parte del acuerdo.

### 4.3 Forma de un requisito funcional completo

> **RF-DOM-01. Título concreto.** El `<actor>` podrá/deberá `<acción sobre una entidad>` cuando `<precondiciones>`. El sistema validará `<reglas>`. Si la operación concluye correctamente, `<resultado y efectos relacionados>`. Si `<causa de rechazo o falla>`, `<resultado observable y efecto sobre los datos>`. Se aplicarán las reglas comunes definidas en `<referencias>`.

La ficha siguiente sirve para revisar los requisitos funcionales que describen operaciones; no obliga a repetir todas sus filas debajo de cada requisito. Los requisitos no funcionales y las restricciones técnicas se redactarán según la condición exigida: objeto al que se aplican, obligación, condiciones de cumplimiento y forma de verificación. No se les atribuirá un actor o una acción artificial solo para completar esta ficha.

| Pregunta de revisión | Contenido que debe poder localizarse |
| --- | --- |
| ¿Quién? | Actor y permisos, incluido el contexto de acceso. |
| ¿Qué lo inicia? | Acción del usuario, solicitud externa o evento automático. |
| ¿Sobre qué? | Entidad y alcance del registro afectado. |
| ¿Cuándo se permite? | Estado, vigencia, disponibilidad y otras precondiciones. |
| ¿Qué se valida? | Datos, duplicidad, relaciones y límites aplicables. |
| ¿Qué produce? | Estado posterior, datos guardados, respuesta y efectos derivados. |
| ¿Qué sucede si no procede? | Motivo que puede comunicarse al actor, conservación o reversión de datos y posibilidad de corregir. |
| ¿Qué reglas comparte? | Referencias a contratos, restricciones y requisitos relacionados. |

Si un requisito contiene varias capacidades que pueden cambiar de forma independiente, se dividirá. Las validaciones, los efectos y los errores permanecerán vinculados a la operación para conservar el contexto.

## 5. Reglas de consistencia entre secciones

### 5.1 Conceptos, entidades y datos

Cada dato deberá pertenecer a una entidad determinada. Un atributo de una entidad subordinada no se atribuirá a la entidad que la agrupa sin una decisión expresa. Se definirán obligatoriedad, longitud, formato, rango, unidad y comportamiento al omitirlo.

También se precisarán recorte de espacios, tratamiento de mayúsculas y acentos, ceros iniciales, caracteres permitidos, diferencia entre vacío y `NULL`, y ámbito de unicidad cuando sean relevantes. La regla de igualdad usada para validar, buscar, importar e identificar deberá ser compatible con las restricciones de persistencia.

Si un campo llega por formulario, importación e integración, sus reglas comunes se mantendrán iguales. Una excepción por canal deberá estar declarada y justificada. Las condiciones para consultar, modificar o mostrar el dato deberán corresponder a su sensibilidad y a los permisos definidos.

Cuando el sistema genere identificadores, códigos o enlaces, se especificarán el momento de creación, el ámbito de unicidad, el formato acordado, el tratamiento de colisiones y su permanencia o regeneración. También se definirá qué contexto identifican, si permiten alguna forma de acceso y qué ocurre cuando su valor es inválido, vence o queda revocado. Cambiar otros datos de una entidad no deberá alterar esos identificadores salvo que una regla lo establezca. Estas condiciones se refieren a los datos del producto; la convención de identificadores de requisitos se encuentra en el apartado 4.1 de esta guía.

### 5.2 Estados y transiciones

Para las entidades con ciclo de vida se definirán el estado inicial y una tabla de transiciones. Se distinguirán el estado de la entidad, el estado de una relación y la etiqueta mostrada a cada actor.

| Estado de origen | Acción o disparador | Actor | Condiciones | Estado de destino | Efectos relacionados | Reversibilidad |
| --- | --- | --- | --- | --- | --- | --- |
| `<estado>` | `<operación o instante>` | `<rol / Sistema>` | `<reglas>` | `<estado>` | `<registros, cantidades, visibilidad…>` | `<permitida / prohibida y procedimiento>` |

Se deberán describir acciones prohibidas y excepciones. Si una transición es automática, se indicará qué hecho la dispara y desde qué instante produce efectos observables. Una tabla resumida no deberá conceder acciones bloqueadas por una regla de tiempo, permiso o estado; deberá referenciar esas condiciones.

### 5.3 Tiempo y límites

Toda regla temporal deberá definir el reloj de autoridad, la zona horaria, la precisión, el inicio, el fin y si cada extremo es inclusivo o exclusivo. Se distinguirán fechas de calendario de instantes absolutos, y días naturales de periodos de horas cuando exista esa diferencia.

Para una ventana definida como `inicio <= ahora < fin`, la aceptación deberá comprobar el instante anterior al inicio, el inicio exacto, el instante anterior al fin y el fin exacto, usando la precisión acordada. Si aplican varios cierres, se definirá cuál prevalece, por ejemplo `min(cierre_del_contexto, cierre_de_la_operación)`.

Los requisitos de sesión deberán precisar qué actividad renueva el plazo, qué solicitudes no lo renuevan, su ámbito y qué ocurre al vencer o cerrar sesión. Si se especifica comportamiento al cerrar el navegador, deberá ser verificable en los navegadores y condiciones de restauración acordados; no se inferirá únicamente a partir de una propiedad de la cookie.

### 5.4 Permisos y exposición de información

Se definirá qué puede consultar o modificar cada actor en cada estado y contexto, incluidos acceso público, sesión inválida y acceso a un registro de otro contexto. Ocultar un botón o elemento no sustituirá la validación de autorización y negocio en el componente que ejecuta la operación.

La regla deberá cubrir vistas de detalle, búsquedas, enlaces directos, archivos y exportaciones. Cuando el mensaje de error deba ser genérico para no revelar información, se especificará qué puede comunicar sin exponer el dato protegido.

Si la autorización depende de una sesión, un enlace o un contexto seleccionado, se definirá cómo se valida su relación con el registro solicitado y qué sucede al intentar reutilizarlo en otro contexto. Los datos de identidad, permisos y auditoría se obtendrán de fuentes validadas; se indicará qué entradas externas pueden considerarse confiables y bajo qué precondiciones.

### 5.5 Integridad, concurrencia y repetición

Se identificarán los invariantes: condiciones que deben seguir siendo verdaderas después de cualquier operación, como unicidad, disponibilidad no negativa o existencia de un solo vínculo vigente.

Para operaciones que compiten por un recurso, se describirá el resultado esperado de solicitudes simultáneas y de reintentos. Se definirá si, ante una solicitud repetida, el sistema devuelve el resultado anterior, rechaza la solicitud o crea un nuevo intento permitido; no se supondrá que toda operación es idempotente, es decir, que repetirla tenga el mismo efecto que ejecutarla una sola vez.

Los cambios que deban confirmarse juntos se enumerarán. También se indicará qué se revierte ante una falla y qué información recibe el actor. Si existen efectos externos que no puedan revertirse con la transacción local, se definirá su recuperación o se registrará la decisión pendiente; no bastará con afirmar que todos los cambios se confirman o se revierten juntos.

### 5.6 Auditoría e historial

Cuando se requiera auditoría, se distinguirán accesos, cambios de negocio e intentos rechazados. Se especificarán acciones registradas, datos, origen confiable, instante, relación con la operación, permisos de consulta, filtros, orden y política de conservación.

Se deberá definir si una falla de auditoría impide confirmar el cambio. También se indicará si se permite corregir o eliminar registros de auditoría, o incorporar nuevos registros, y mediante qué procedimiento. Cuando los reportes deban conservar nombres o valores tal como eran al ocurrir una operación, se indicará expresamente qué datos históricos deben permanecer disponibles.

### 5.7 Cancelación, eliminación y conservación

Cancelar, desactivar, eliminar lógicamente y destruir físicamente datos tendrán definiciones separadas cuando existan. Para cada operación se especificarán efectos sobre relaciones, disponibilidad, cálculos, archivos, interfaces, reportes y bitácoras.

Si una eliminación conserva antecedentes, se señalará quién puede consultarlos y mediante qué función. La política de conservación deberá ser compatible con esa permanencia. Todo plazo para transferir, archivar o eliminar datos deberá indicar el hecho que inicia su cómputo, la forma de calcularlo, el responsable de cumplirlo y el tratamiento de las excepciones acordadas.

Cuando la entrega, el archivo o la eliminación material sean responsabilidad del equipo de operación, se documentarán como obligación o dependencia externa con evidencia esperada. No se transformará un procedimiento manual en una tarea automática sin acuerdo.

### 5.8 Cargas, archivos, integraciones y salidas

Para cargas masivas se definirán estructura, codificación cuando aplique, orden de columnas, filas vacías, fórmulas, duplicados internos, coincidencias con registros existentes y errores por fila. Se distinguirán el rechazo completo, la omisión prevista de filas y la aceptación parcial; se definirán las condiciones de cada resultado. Cada resultado deberá indicar su efecto sobre los datos y el detalle informado al usuario.

Para archivos se precisarán uso, obligatoriedad, extensión, contenido válido, tamaño con unidad inequívoca, dimensiones si aplican, tratamiento de contenido dañado, almacenamiento y permisos. Se aclarará si un límite se aplica a cargas, a archivos generados o a ambos. Una dimensión recomendada no se convertirá en causa de rechazo.

Las reglas de aceptación del archivo distinguirán su nombre, el tipo de contenido declarado y la validez de su contenido real. Se definirán las comprobaciones necesarias y el resultado ante discrepancias, sin suponer que cambiar una extensión convierte el formato. Cuando corresponda, se precisará el tratamiento de archivos cifrados, vacíos o estructuralmente inválidos.

Si existen integraciones, se documentarán dirección del intercambio, datos, autenticación aplicable, respuestas, fallas, reintentos y responsabilidad del servicio externo. La indisponibilidad de esa dependencia deberá tener un comportamiento definido.

Para reportes y exportaciones se especificarán emisor autorizado, filtros, estados incluidos y excluidos, campos, orden, formato, nombres de archivo y condiciones de disponibilidad. Un cálculo tendrá fórmula, población considerada, unidad y reglas de redondeo o casos sin datos cuando apliquen; deberá coincidir en pantalla y exportaciones, salvo diferencia explícita.

Para las consultas y los listados funcionales se definirán campos visibles, filtros, coincidencias exactas o parciales y reglas de comparación. El orden incluirá un criterio de desempate cuando sea necesario para que los resultados sean estables. Si existe paginación, se especificará su comportamiento al buscar, filtrar o cambiar de página. También se describirán los resultados sin coincidencias y la visibilidad de registros cancelados, cerrados o eliminados según los permisos del actor.

### 5.9 Interfaz y experiencia observable

Se definirán jerarquía de acciones, información visible, estados de espera, ausencia de datos y errores relevantes, textos que deban ser exactos y comportamiento en los tamaños de pantalla acordados. Las exigencias de dimensiones deberán indicar contenido de referencia y respuesta ante nombres largos, ampliación de la vista u otras condiciones que afecten la prueba.

Cuando una acción requiera confirmación, se precisarán momento, consecuencia informada, acciones de aceptar/cancelar y comportamiento al cerrar el diálogo. También se definirá cómo evitar efectos duplicados si ello es necesario para la operación.

Los criterios de legibilidad y accesibilidad se expresarán en comportamientos evaluables, como acceso por teclado, foco y presencia de una etiqueta textual además del color. Las medidas, paletas y distribución del ejemplo no serán obligatorias para otro producto.

### 5.10 Privacidad y contenido informativo

Cuando el producto trate datos personales, el documento deberá ser consistente sobre qué datos recoge, para qué los usa, quién accede y cuánto tiempo permanecen. El contenido informativo visible deberá describir ese tratamiento real.

Las finalidades, los plazos, la jurisdicción y las obligaciones aplicables deberán obtenerse de las fuentes autorizadas del nuevo producto. No se copiarán entidades, autoridades, textos jurídicos ni plazos de la ERS de referencia como reglas universales. Si un contenido necesario para la operación requiere datos institucionales aún no confirmados, se registrará como pendiente la validación de ese contenido y su impacto, sin completar nombres, contactos ni textos jurídicos supuestos. Ese pendiente se evaluará para el alcance que afecte; no se presentará el contenido como listo para publicarse.

Si un texto usa variables, se definirán su origen, campos editables, protección del contenido y comportamiento cuando un valor opcional falte. La salida no deberá dejar marcadores sin sustituir ni frases incompletas.

Cuando se transforme texto para mostrarlo o generar documentos, el contrato indicará el formato admitido, las construcciones permitidas y el tratamiento del contenido no admitido. Se especificará cómo se insertan los valores variables para que no se interpreten como instrucciones o contenido ejecutable. También se definirán la procedencia del texto, quién puede modificarlo, su versión y el efecto de actualizarlo sobre documentos ya generados. Estas reglas se aplicarán a cualquier plantilla de contenido que las necesite, sin presuponer un formato o una tecnología.

### 5.11 Una definición principal por regla

Cada regla compartida tendrá una ubicación principal: por ejemplo, el contrato de un campo en la sección 5 de la ERS o una ventana temporal en un requisito funcional. Las demás secciones la referenciarán. Los ejemplos y criterios de aceptación podrán repetir valores para hacer la prueba concreta, pero deberán coincidir con esa definición.

Si dos secciones se contradicen, se corregirá la contradicción antes de aprobar la línea base. No se resolverá mediante una prioridad implícita de “lo que diga la tabla”, “lo que diga la prueba” o “lo último escrito”.

## 6. Criterios de aceptación y trazabilidad

### 6.1 Formato del criterio

| Dato | Contenido |
| --- | --- |
| Identificador y título | `CA-<GRUPO>-<NN>` y comportamiento comprobado. |
| Requisitos cubiertos | Identificadores de RF, RNF o RT aplicables. |
| Dado | Actor, permisos, contexto, estado, configuración y datos iniciales necesarios. |
| Cuando | Acción o disparador específico. |
| Entonces | Resultado observable, datos afectados y ausencia de efectos prohibidos. |
| Método y evidencia | Prueba funcional, concurrencia, inspección, medición u otro método; resultado o artefacto que demuestra cumplimiento. |

Se podrán redactar como párrafos o listas si conservan esos elementos. La aceptación deberá expresar resultados esperados; un informe de ejecución posterior registrará los resultados obtenidos y la evidencia. Una ERS recién escrita no demuestra que el software ya cumple.

### 6.2 Cobertura mínima según el riesgo de la regla

| Clase de comportamiento | Casos que deberán considerarse cuando apliquen |
| --- | --- |
| Operación normal | Actor autorizado, datos válidos, cambio esperado y respuesta visible. |
| Validación | Ausencia, vacío, formato, límites admitidos y primer valor rechazado. |
| Autorización | Falta de sesión, rol incorrecto y acceso a otro contexto. |
| Ciclo de vida | Transición permitida, transición prohibida y efectos sobre relaciones. |
| Tiempo | Antes, en y después del límite; renovación o reapertura cuando existan. |
| Concurrencia | Solicitudes que compiten por el mismo recurso sin romper invariantes. |
| Repetición | Doble envío, repetición de importación y reintentos según la política acordada. |
| Falla | Error durante cambios relacionados; reversión o recuperación definida. |
| Archivos | Formato válido, contenido incompatible, corrupción y límites. |
| Configuración | Primer arranque, valores ausentes, vacíos o inválidos, cambios, reinicio y falla sin exposición de secretos. |
| Identificadores generados | Creación, colisión, conservación o regeneración, valor inválido y acceso a otro contexto. |
| Consultas | Coincidencias, filtros, orden con desempate, paginación y ausencia de resultados. |
| Transformación de textos | Formatos y construcciones admitidos, valores insertados, contenido rechazado y variables opcionales ausentes. |
| Salidas e interfaz | Información incluida/excluida, fórmulas, etiquetas y condiciones visuales medibles. |
| Auditoría y conservación | Registro exigido, acceso permitido e historial después de cambios o eliminaciones. |
| Dependencia externa | Condición disponible e indisponible, con responsable de verificación. |

No todos los requisitos necesitan todas las clases de prueba. Se deberán elegir las que puedan cambiar su resultado y justificar las exclusiones relevantes. Si se exigen capturas para documentación, se definirá un inventario de flujos y su correspondencia con las evidencias; una captura visual por sí sola no demuestra integridad transaccional ni cumplimiento de tiempos.

Cuando la cobertura visual sea una condición de entrega, se identificarán los flujos que la requieren, los archivos de evidencia y el resultado de la verificación si falta alguno. Los procesos exclusivamente automáticos se comprobarán mediante evidencia técnica adecuada. Si se exige ejecución automática reproducible, sus verificaciones y decisiones de éxito o falla deberán estar definidas de antemano; también se documentarán la preparación del entorno, la conservación de evidencias y la limpieza de los recursos temporales.

### 6.3 Matriz de trazabilidad

| Fuente o necesidad | Requisito | Regla o estructura relacionada | Criterios de aceptación | Método o evidencia prevista |
| --- | --- | --- | --- | --- |
| `<acuerdo identificable>` | `<RF / RNF / RT>` | `<campo, estado, fórmula, dependencia…>` | `<CA>` | `<cómo se comprobará>` |

Cada requisito obligatorio deberá tener al menos un criterio de aceptación. Si reúne varias condiciones comprobables, se cubrirán todas las relevantes mediante uno o varios criterios. Cada criterio deberá apuntar a requisitos existentes; no podrá ampliar el alcance por sí solo.

La revisión de cobertura deberá comprobar también que cada capacidad incluida en el alcance tiene requisitos y que cada requisito corresponde a una capacidad o restricción acordada.

## 7. Ejemplo de aplicación a un producto diferente

**Ejemplo didáctico: préstamo de equipos en un almacén.** Las decisiones siguientes ilustran el método y no son requisitos del producto que se vaya a especificar. Se muestra una parte del flujo, no una ERS completa.

**Alcance de este fragmento:** registrar la entrega de un equipo. La autenticación del operador se toma como precondición del ejemplo. El registro de la devolución se especificaría en otro grupo de requisitos.

**Vocabulario:** un equipo es una unidad física; un préstamo activo vincula un equipo con una persona receptora; un operador está autorizado para un almacén. “Disponible” significa que el equipo no tiene un préstamo activo.

**Contrato de datos del fragmento, correspondiente a la sección 5 de la ERS:**

| Campo | Tipo y obligatoriedad | Regla |
| --- | --- | --- |
| `equipo_id` | Identificador obligatorio | Debe identificar un equipo existente en el almacén autorizado del operador. |
| `persona_id` | Identificador obligatorio | Debe identificar una persona existente y habilitada como receptora en ese almacén. |
| `fecha_entrega` | Instante generado por el sistema | Reloj del servidor, almacenamiento UTC y precisión de segundos. No lo captura el operador. |

**Requisitos del fragmento:**

- **RF-PRE-01. Registrar entrega.** El operador autenticado podrá prestar un equipo de su almacén a una persona habilitada para recibirlo cuando el equipo esté disponible. El sistema validará los identificadores conforme al contrato de datos, creará un préstamo **Activo** y guardará `fecha_entrega`. Mostrará **Préstamo registrado** con su identificador. Si el equipo tiene un préstamo activo, rechazará la operación sin cambios y mostrará **Equipo no disponible**. Si alguno de los identificadores es inválido o no pertenece al contexto autorizado, rechazará sin cambios y mostrará **No se pudo registrar el préstamo**.
- **RF-AUD-01. Auditar entrega.** Cada préstamo registrado generará una entrada de auditoría con identificador del préstamo, equipo, persona receptora, operador obtenido de la sesión y el mismo instante de la entrega. La entrada se obtendrá de los datos validados por el servidor y deberá confirmarse junto con el préstamo.
- **RNF-INT-01. Exclusividad e integridad.** Como máximo podrá existir un préstamo activo por equipo, incluso ante solicitudes simultáneas. La creación del préstamo y su auditoría se confirmarán como una unidad. Si falla cualquiera de las escrituras, no quedará ningún cambio de esa operación y se mostrará **No se pudo registrar el préstamo**. Un nuevo envío para un equipo que ya tiene préstamo activo aplicará el rechazo definido en `RF-PRE-01`.

**Transición cubierta:**

| Condición inicial del equipo | Acción | Actor | Resultado | Efectos |
| --- | --- | --- | --- | --- |
| Sin préstamo activo | Registrar entrega válida | Operador autorizado | Un préstamo activo | El equipo deja de estar disponible y se registra la auditoría. |

**Aceptación y trazabilidad del fragmento:**

| Identificador | Requisitos | Dado / Cuando / Entonces | Evidencia |
| --- | --- | --- | --- |
| `CA-PRE-01` | `RF-PRE-01`, `RF-AUD-01`, `RNF-INT-01` | Dado un equipo disponible, una persona habilitada y un operador autorizado, cuando registra la entrega, entonces existe exactamente un préstamo activo, aparece el mensaje correcto y su auditoría conserva la identidad del operador y el mismo instante. | Resultado funcional e inspección de registros en entorno de prueba. |
| `CA-PRE-02` | `RF-PRE-01`, `RNF-INT-01` | Dado un equipo disponible y dos solicitudes válidas concurrentes, cuando ambas intentan prestarlo, entonces solo una concluye correctamente y la otra informa **Equipo no disponible**; queda un solo préstamo activo. | Ejecución concurrente y verificación de registros. |
| `CA-PRE-03` | `RF-AUD-01`, `RNF-INT-01` | Dado un equipo disponible, cuando falla la escritura de auditoría durante una entrega válida, entonces no se conserva el préstamo ni su auditoría, el equipo sigue disponible y aparece el mensaje de falla. | Falla provocada y comprobación de reversión. |
| `CA-PRE-04` | `RF-PRE-01` | Dado un operador válido, cuando solicita un equipo de otro almacén o una persona no habilitada, entonces la operación se rechaza con el mensaje genérico y no crea registros. | Prueba de acceso y validación por cada variante. |
| `CA-PRE-05` | `RF-PRE-01`, `RNF-INT-01` | Dado un préstamo ya registrado, cuando se vuelve a enviar una solicitud de entrega para el mismo equipo, entonces se informa **Equipo no disponible** y se conserva el préstamo existente sin generar otro. | Repetición y comparación del estado. |

El ejemplo conecta un concepto de negocio con su entrada, autorización, cambio de estado, integridad, auditoría y aceptación. Esa conexión es la que deberá conservarse al cambiar de producto.

## 8. Tratamiento de vacíos, propuestas y decisiones

Antes de redactar, se deberá distinguir entre información confirmada, propuesta pendiente y dato desconocido. La falta de información no autoriza a inventar roles, campos, integraciones, plazos, volúmenes ni tecnologías.

| Identificador | Decisión requerida | Elementos afectados | Impacto o bloqueo | Responsable de resolver | Estado y resolución |
| --- | --- | --- | --- | --- | --- |
| `PD-<NN>` | `<pregunta concreta>` | `<secciones o identificadores>` | `<qué no puede diseñarse, verificarse o aprobarse>` | `<persona o rol>` | `<abierta / propuesta / resuelta y referencia>` |

Una decisión pendiente que afecte permisos, reglas de negocio, integridad, alcance o aceptación impedirá declarar listo el trabajo afectado. Se podrá acordar una entrega parcial solo si sus límites y dependencias quedan explícitos y los pendientes restantes no afectan lo aprobado.

Al resolver un pendiente se actualizarán requisitos, estructuras y criterios relacionados, y se registrará la decisión en el control de cambios. Los marcadores de una plantilla se sustituirán por contenido confirmado o por una referencia a un pendiente antes de entregar el borrador del producto.

## 9. Secuencia de elaboración y revisión

1. **Inventariar las fuentes.** Identificar necesidades confirmadas, decisiones existentes, ejemplos y vacíos.
2. **Delimitar la entrega.** Redactar propósito, capacidades incluidas, exclusiones y dependencias con responsables.
3. **Fijar el vocabulario.** Nombrar actores, entidades, relaciones, estados y unidades de contexto.
4. **Describir los flujos.** Cubrir disparador, permisos, entradas, reglas, resultado, excepciones y efectos relacionados.
5. **Asignar identificadores y centralizar reglas.** Evitar definiciones divergentes de datos, tiempo, permisos y cálculos.
6. **Completar restricciones y contratos.** Precisar solo las decisiones acordadas y registrar las que falten.
7. **Derivar aceptación.** Redactar criterios desde los requisitos, incluidos límites y fallas relevantes, y construir la matriz.
8. **Cruzar las secciones.** Revisar nombres, estados, valores, exclusiones, dependencias y efectos secundarios.
9. **Resolver observaciones.** Corregir contradicciones y clasificar pendientes según el alcance que bloquean.
10. **Versionar la entrega documental.** Registrar cambios y mantener un estado que refleje su revisión o aprobación real.

La ERS servirá como entrada para los documentos de arquitectura, diseño, construcción, pruebas, despliegue y operación que correspondan al producto. Estos documentos referenciarán los requisitos que desarrollan o verifican. Si durante el diseño se detecta que un requisito debe cambiar, se actualizará la ERS mediante una decisión registrada; el documento de diseño no sustituirá ese acuerdo. La [biblioteca de guías](../README.md) organiza esas familias documentales por etapa.

## 10. Lista de revisión y criterio de terminación

La lista siguiente identifica los aspectos que se deben revisar. Las casillas sirven para controlar el avance; el resultado de cada punto se registrará en la tabla del apartado 10.1 como **Cumple**, **Pendiente** o **No aplica**. No se marcará “No aplica” para ocultar una decisión desconocida.

- [ ] La cabecera identifica la descripción funcional del producto, la entrega, la versión, la fecha, el estado y las fuentes reales.
- [ ] Cabeceras, ejemplos y plantillas utilizan denominaciones neutrales, sin identificaciones comerciales, firmas, créditos ni marcadores para esos datos.
- [ ] Se identifica la versión de la guía utilizada y se han sustituido las instrucciones de plantilla por contenido del producto.
- [ ] Están las ocho secciones, con contenido o justificación de no aplicación.
- [ ] El propósito permite reconocer el problema y el resultado esperado.
- [ ] El alcance incluido y las exclusiones son compatibles con los requisitos y la aceptación.
- [ ] Las dependencias externas tienen responsable, precondición y verificación diferenciada.
- [ ] Los conceptos y nombres mantienen un significado único en todo el documento.
- [ ] Todos los requisitos obligatorios tienen identificadores únicos, estables y referencias válidas.
- [ ] Cada requisito define una obligación, sus condiciones y un resultado verificable; los requisitos que describen operaciones identifican también actor, contexto y acción.
- [ ] Se cubren rechazos, fallas y efectos relacionados que cambian el resultado de la operación.
- [ ] Los campos tienen tipo, obligatoriedad, límites, normalización y reglas de comparación suficientes.
- [ ] Las reglas compartidas coinciden entre formulario, importación, integración y persistencia.
- [ ] Los identificadores y enlaces generados tienen reglas de creación, unicidad, permanencia, contexto y tratamiento de valores inválidos.
- [ ] Los ciclos de vida incluyen estado inicial, transiciones, acciones prohibidas y reversibilidad.
- [ ] Las ventanas de tiempo tienen reloj, zona, precisión y límites inequívocos.
- [ ] Los permisos se aplican a vistas, operaciones, archivos y contextos de acceso.
- [ ] Se preservan los invariantes ante concurrencia, doble envío y reintentos aplicables.
- [ ] Están definidos los cambios conjuntos, su reversión y la recuperación de efectos externos cuando exista.
- [ ] Auditoría, eliminación funcional, reportes y conservación de datos son compatibles.
- [ ] Las entradas y salidas tienen formatos, resultados y límites definidos sin confundir recomendaciones con obligaciones.
- [ ] La configuración distingue ausencia, vacío e invalidez y define el comportamiento del arranque y de los cambios.
- [ ] Las consultas especifican campos, filtros, comparación, orden, desempate, paginación y resultados vacíos cuando corresponda.
- [ ] Las plantillas de contenido definen formatos permitidos, inserción de variables, edición, versión y tratamiento de contenido no admitido.
- [ ] Los requisitos técnicos y visuales tienen condiciones de verificación suficientes.
- [ ] Las capacidades y umbrales proceden del nuevo producto; las cifras de ejemplo están identificadas como tales.
- [ ] Cada requisito obligatorio tiene aceptación suficiente y cada criterio remite a requisitos existentes.
- [ ] La aceptación cubre límites, excepciones y fallas pertinentes sin introducir alcance adicional.
- [ ] El entorno, método y evidencia de las verificaciones exigidas están definidos.
- [ ] No quedan contradicciones entre prosa, tablas, ejemplos, configuración y aceptación.
- [ ] Los pendientes tienen identificador, impacto, responsable y estado; las propuestas están marcadas.
- [ ] No se presentan normas, contenidos jurídicos ni parámetros técnicos del ejemplo como obligaciones universales.
- [ ] El control de cambios refleja la versión actual y los elementos afectados.
- [ ] Los documentos complementarios se identifican cuando existen y no contradicen la ERS.

**Criterio de terminación documental:** una ERS estará lista para someterse a aprobación cuando todos los puntos aplicables estén cubiertos, no existan contradicciones y las decisiones necesarias para el alcance propuesto estén resueltas. Solo se declarará **línea base aprobada** cuando exista el acuerdo correspondiente. La revisión de la ERS y la aceptación posterior del software son hitos diferentes.

### 10.1 Registro de revisión

Se copiará este formato en un anexo de revisión de la ERS o en un archivo de revisión vinculado a ella. Se añadirá una fila por cada punto de la lista anterior, indicando su enunciado para que pueda identificarse aunque cambie el orden de la lista.

| Dato | Valor |
| --- | --- |
| Documento y versión revisados | `<nombre y versión de la ERS>` |
| Guía y versión utilizadas | `<nombre y versión de esta guía>` |
| Persona o rol revisor | `<responsable>` |
| Fecha de revisión | `<AAAA-MM-DD>` |

| Criterio revisado | Resultado | Referencia o evidencia | Observación y acción requerida | Responsable de atenderla |
| --- | --- | --- | --- | --- |
| `<enunciado del punto>` | `<Cumple / Pendiente / No aplica>` | `<sección, identificador o evidencia>` | `<hallazgo, corrección o justificación de no aplicación>` | `<responsable / no se requiere acción>` |

Un resultado **Cumple** deberá poder sustentarse en la ERS o en sus referencias. Un resultado **Pendiente** indicará qué falta y quién debe atenderlo. Un resultado **No aplica** incluirá la razón por la que el criterio no corresponde al producto.

### 10.2 Registro de aprobación

Cuando exista una aprobación, se registrará este formato en la ERS o en un documento vinculado a ella. Si el proceso de la organización ya conserva esa información, bastará con referenciar el registro existente.

| Versión de la ERS aprobada | Alcance aprobado | Persona o rol que aprueba | Fecha | Referencia del acuerdo | Exclusiones o pendientes fuera del alcance aprobado |
| --- | --- | --- | --- | --- | --- |
| `<versión>` | `<entrega y capacidades>` | `<responsable con autoridad para aprobar>` | `<AAAA-MM-DD>` | `<acta, registro u otro acuerdo verificable>` | `<identificadores y delimitación / ninguno>` |

Los pendientes que afecten el alcance propuesto deberán resolverse antes de aprobarlo. Registrar la revisión o completar esta plantilla no constituye por sí mismo una aprobación.

## Anexo A. Plantilla base para un nuevo producto

La siguiente estructura es un punto de partida. Los marcadores deberán sustituirse por información del nuevo producto; los vacíos detectados se registrarán en la sección 7 de la ERS.

```markdown
# Especificación de requisitos de software (ERS)

> Requisitos funcionales, reglas de negocio y criterios de aceptación.

| Dato | Valor |
| --- | --- |
| Producto y entrega | <descripción funcional y alcance de la versión> |
| Tipo de documento | Base de requisitos para diseño, desarrollo y aceptación |
| Versión | <versión> |
| Estado | Borrador |
| Fecha | <AAAA-MM-DD> |
| Fuentes | <fuentes identificables> |
| Guía utilizada | Guía de criterios para elaborar una ERS, versión 0.3 |

## 1. Propósito y alcance

<Problema, usuarios, resultado esperado y capacidades incluidas.>

### 1.1 Fuera de alcance

<Exclusiones y referencias a dependencias cuando sean precondiciones.>

### 1.2 Componentes del documento

<Finalidad y carácter de cada componente; documentos complementarios.>

### 1.3 Términos y convenciones

<Conceptos del dominio, abreviaturas y convenciones de identificadores.>

## 2. Actores y dependencias

<Roles, sistemas, procesos automáticos, límites y responsables externos.>

## 3. Requisitos funcionales

### 3.1 <Capacidad del producto>

- **RF-DOM-01. <Título>.** <Actor, acción, condiciones, resultado y errores.>

<Tablas de datos, permisos o transiciones cuando correspondan.>

## 4. Requisitos técnicos mínimos

- **RNF-ASP-01. <Título>.** <Restricción acordada y condición verificable.>

<Agrupar los requisitos por aspectos aplicables al producto.>

## 5. Estructuras de entrada

<Contratos de campos, configuración, formularios, archivos e integraciones.>

| Campo o clave | Tipo y formato | Obligatorio | Predeterminado | Validación | Resultado si falta o es inválido |
| --- | --- | --- | --- | --- | --- |
| <campo> | <tipo y formato> | <condición> | <valor acordado o ninguno> | <reglas> | <resultado> |

<Detallar aquí la interpretación de la configuración y las entradas al arranque.
Describir los identificadores generados, las consultas, las salidas y la
transformación de textos en sus requisitos correspondientes, referenciando
estos contratos para mantener una única definición por regla.>

## 6. Criterios mínimos de aceptación

- **CA-DOM-01. <Título>.** Requisitos: <identificadores>.
  Dado <contexto>, cuando <acción>, entonces <resultado comprobable>.
  Método y evidencia: <verificación>.

### 6.1 Matriz de trazabilidad

| Fuente | Requisito | Regla o contrato | Criterios | Evidencia prevista |
| --- | --- | --- | --- | --- |
| <fuente> | <identificador> | <referencia> | <CA> | <evidencia> |

## 7. Requiere definición

| Identificador | Decisión | Elementos afectados | Impacto | Responsable | Estado |
| --- | --- | --- | --- | --- | --- |
| PD-01 | <pregunta concreta> | <identificadores> | <bloqueo> | <responsable> | Abierta |

<Si no existen pendientes, sustituir la tabla por una declaración revisada.>

## 8. Control de cambios

| Versión | Fecha | Cambio | Identificadores afectados | Fuente del acuerdo |
| --- | --- | --- | --- | --- |
| <versión> | <AAAA-MM-DD> | <cambio> | <identificadores> | <fuente> |

## Anexos de revisión y aprobación

<Incorporar los registros del apartado 10 de la guía o enlazar los documentos
que los contienen. El registro de aprobación se completa solo cuando existe
el acuerdo correspondiente.>
```

## Anexo B. Instrucción reutilizable para generar una ERS

Este texto puede utilizarse con una persona redactora o con una herramienta de generación, adjuntando esta guía y la información del nuevo producto:

```text
Elabora una especificación de requisitos de software para el producto descrito
en las fuentes adjuntas, aplicando la Guía de criterios para elaborar una ERS.

Utiliza las denominaciones producto, proyecto o sistema. No deduzcas un nombre
propio de las rutas, del repositorio ni de los documentos de referencia.
Omite identificaciones comerciales, logotipos, firmas y créditos, incluidos
los campos vacíos o marcadores destinados a esos datos. Describe las
responsabilidades funcionales mediante los roles que estén confirmados.

Conserva las ocho secciones principales y adapta los subapartados al dominio.
Identifica requisitos funcionales, no funcionales y criterios de aceptación.
Describe actores, contexto, datos, estados, permisos, condiciones, resultados,
errores y efectos relacionados. Define contratos de entrada y restricciones
medibles únicamente con información confirmada. Mantén una definición principal
por cada regla compartida y referencias consistentes entre secciones.

No traslades nombres, funciones, tecnologías, cifras ni políticas del sistema
usado como referencia si no están acordados para este producto. Distingue
ejemplos, propuestas y obligaciones. No inventes decisiones: registra cada
vacío con un identificador de pendiente, su impacto y el responsable conocido,
o indica que falta asignarlo. Continúa documentando las partes que sí estén
definidas.

Deriva los criterios de aceptación desde los requisitos; cubre resultados
correctos, rechazos, límites, concurrencia y fallas cuando apliquen. Incluye
una matriz de trazabilidad y verifica que ningún criterio agregue alcance.

Entrega la ERS completa en Markdown e identifica la versión de la guía utilizada.
Incluye el estado real de revisión, los pendientes, el control de cambios y
los registros de revisión o aprobación que correspondan. Corrige las
contradicciones antes de entregar y no declares aprobación ni ausencia de
pendientes sin evidencia suficiente.

Información del nuevo producto:
<Adjuntar descripción, objetivos, actores, alcance, restricciones y acuerdos.>
```

## Control de cambios de esta guía

| Versión | Fecha | Cambio |
| --- | --- | --- |
| 0.1 | 2026-09-07 | Creación de la guía reutilizable a partir de la ERS de referencia, con reglas de consistencia, ejemplo de otro dominio, lista de revisión y plantillas. |
| 0.2 | 2026-09-07 | Revisión del español y de las referencias internas; incorporación de información de entrada, términos, registros de revisión y aprobación, y organización de la guía dentro de la biblioteca documental del desarrollo. |
| 0.3 | 2026-09-07 | Revisión de cobertura frente a la ERS de referencia; precisión de consultas, identificadores generados, configuración, archivos, transformación de textos y evidencias de prueba; adopción de denominaciones neutrales en cabeceras, criterios, plantillas e instrucciones de generación. |
