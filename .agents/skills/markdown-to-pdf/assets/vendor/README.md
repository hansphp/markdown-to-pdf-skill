# Recursos de renderizado sin conexión

Se incluyen los archivos oficiales, sin modificar, de Mermaid **12.0.0** y KaTeX **0.18.7**. Las licencias MIT del código se conservan en cada directorio, junto con los avisos que contienen sus distribuciones. Las fuentes de KaTeX mantienen su licencia SIL OFL 1.1, incluida en [katex/OFL.txt](katex/OFL.txt). No es necesario instalar Node.js o npm ni conectarse a una CDN para convertir documentos.

`manifest.json` fija las URL de los paquetes originales, su integridad SHA-512 publicada por npm y el SHA-256 de cada archivo extraído de esos paquetes. El campo `license` identifica la licencia del paquete; los avisos específicos de las fuentes se detallan en [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md). `technical_rendering.py` comprueba los archivos del motor que necesita el documento antes de usarlos. La distribución Mermaid incluye su motor de diagramas en un único archivo de navegador. KaTeX incluye JavaScript, CSS y las fuentes originales; las URL de fuentes se convierten en datos embebidos únicamente en el HTML temporal.

Para reproducir estos recursos, descargue las URL fijadas en el manifiesto, verifique su SHA-512 y extraiga únicamente los archivos enumerados. `LICENSE` corresponde a `package/LICENSE`; los demás archivos corresponden a `package/dist/` dentro del archivo npm. Verifique después sus SHA-256. Actualizar versiones requiere actualizar el manifiesto y ejecutar las pruebas de contenido técnico y de navegador.

`katex/OFL.txt` es un aviso complementario, no un archivo extraído del paquete npm ni un recurso cargado por el motor. Su cabecera reúne los titulares y nombres reservados declarados en los metadatos de las fuentes incluidas; el cuerpo reproduce el [texto oficial de SIL OFL 1.1](https://openfontlicense.org/documents/OFL.txt). Consérvelo junto con las fuentes al redistribuir el skill.

Fuentes oficiales: [API de Mermaid](https://mermaid.js.org/config/usage.html), [configuración Mermaid](https://mermaid.js.org/config/schema-docs/config.html), [KaTeX en el navegador](https://katex.org/docs/browser.html) y [opciones KaTeX](https://katex.org/docs/options.html).
