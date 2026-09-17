# Trabajo con Markdown a PDF

La entrada para personas es [README.md](README.md). Las instrucciones del skill
están en [.agents/skills/markdown-to-pdf/SKILL.md](.agents/skills/markdown-to-pdf/SKILL.md).
Úsalas para convertir Markdown a PDF o crear ejemplos de formato.

El motor, las plantillas y las dependencias pertenecen a
`.agents/skills/markdown-to-pdf/`. La entrada en `.claude/skills/markdown-to-pdf/`
delega a ese mismo skill; evita mantener otra copia del conversor.

Los ejemplos públicos están en `ejemplo-markdown-pdf/`. Conserva el Markdown de
origen al convertir. Para probar cambios del conversor, utiliza copias y salidas
temporales. Si cambia el resultado mostrado en la documentación, actualiza su
PDF y las capturas correspondientes.

Pruebas con navegador desde la raíz del repositorio, en macOS/Linux:

```shell
MDPDF_BROWSER_TESTS=1 .agents/skills/markdown-to-pdf/.venv/bin/python -B -m unittest discover -s .agents/skills/markdown-to-pdf/tests -q
```

En Windows, usa `.venv\Scripts\python.exe` y define `MDPDF_BROWSER_TESTS=1`
en el entorno de PowerShell. Requisitos y comandos de conversión: [README](README.md).
