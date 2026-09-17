# Licencias y avisos de terceros

El código propio, la documentación y los recursos de ejemplo de este skill se distribuyen bajo la [licencia MIT](LICENSE), con Copyright (c) 2026 Hans Herrera. El logotipo genérico de ejemplo de `assets/logo.png` se generó con una herramienta de imágenes; su prompt se conserva en `assets/logo.prompt.txt`.

Los componentes de terceros conservan sus licencias y titulares originales. La licencia del skill no sustituye estos avisos ni cambia la licencia de las fuentes.

## Recursos incluidos

| Componente | Versión incluida | Licencia y aviso local | Titular del aviso |
| --- | --- | --- | --- |
| Mermaid | 12.0.0 | [MIT](assets/vendor/mermaid/LICENSE) | Copyright (c) 2014 - 2022 Knut Sveidqvist |
| KaTeX, JavaScript y CSS | 0.18.7 | [MIT](assets/vendor/katex/LICENSE) | Copyright (c) 2013-2020 Khan Academy and other contributors |
| Fuentes KaTeX, TTF, WOFF y WOFF2 | Distribuidas con KaTeX 0.18.7 | [SIL Open Font License 1.1](assets/vendor/katex/OFL.txt) | Copyright (c) 2009-2010 Design Science, Inc.; Copyright (c) 2014-2018 Khan Academy |

Las URL de los paquetes npm originales y las sumas de integridad de los recursos de renderizado están en [assets/vendor/manifest.json](assets/vendor/manifest.json). Se conservan las licencias originales de los paquetes y los avisos incorporados en los archivos distribuidos. Esta tabla identifica los componentes principales incluidos; no constituye un inventario exhaustivo de dependencias transitivas incorporadas en sus paquetes.

## Fuentes KaTeX

Los avisos de licencia presentes en los metadatos de las fuentes declaran SIL OFL 1.1 y estos nombres reservados:

- `KaTeX_AMS`
- `KaTeX_Caligraphic`
- `KaTeX_Fraktur`
- `KaTeX_Main`
- `KaTeX_Math`
- `KaTeX_SansSerif`
- `KaTeX_Script`
- `KaTeX_Size1`
- `KaTeX_Size2`
- `KaTeX_Size3`
- `KaTeX_Size4`
- `KaTeX_Typewriter`

La copia local [OFL.txt](assets/vendor/katex/OFL.txt) reúne esos avisos de copyright y nombres reservados con el [texto oficial de SIL OFL 1.1](https://openfontlicense.org/documents/OFL.txt). Los metadatos pueden consultarse también en las fuentes del [repositorio oficial KaTeX/katex-fonts](https://github.com/KaTeX/katex-fonts/tree/56e79c93c88c9054b017cc92e496b383e0bf82d7/fonts). No se han modificado los archivos de fuentes incluidos.

## Dependencias instaladas por separado

Las dependencias Python declaradas en `requirements.txt` y el navegador utilizado para exportar PDF se instalan por separado y mantienen sus propias licencias. No forman parte de los archivos de renderizado incluidos en `assets/vendor/`.

## Referencias

- [Texto de la licencia MIT, Open Source Initiative](https://opensource.org/license/mit).
- [Proyecto Mermaid](https://github.com/mermaid-js/mermaid).
- [Proyecto KaTeX](https://github.com/KaTeX/KaTeX).
- [SIL Open Font License, texto oficial y preguntas frecuentes](https://openfontlicense.org/).
