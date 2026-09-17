"""Exercise the documented Claude entry after relocating the shared repository.

These tests validate its paths and conversion command, not Claude Code discovery
or a model session. The canonical skill can also be distributed on its own.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
REPOSITORY = SKILL.parents[2]
ADAPTER = REPOSITORY / '.claude/skills/markdown-to-pdf'


@unittest.skipUnless((ADAPTER / 'SKILL.md').is_file(),
                     'Requiere el repositorio con la entrada de Claude Code')
class AgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mdpdf agent integration ')
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name).resolve() / 'repositorio con espacios'
        self.skill = self.repository / '.agents/skills/markdown-to-pdf'
        self.adapter = self.repository / '.claude/skills/markdown-to-pdf'
        shutil.copytree(SKILL, self.skill,
                        ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.pyc'))
        shutil.copytree(ADAPTER, self.adapter)
        self.workspace = self.repository / 'documentos de prueba'
        self.workspace.mkdir()
        self.source = self.workspace / 'informe con espacios.md'
        self.output = self.workspace / 'resultado con espacios.pdf'
        text = (self.adapter / 'SKILL.md').read_text(encoding='utf-8')
        match = re.search(r'```shell\n\s*(python3 [^\n]+)\n', text)
        self.assertIsNotNone(match, 'La entrada debe documentar su comando de conversión')
        # Reproduce the documented path substitution before parsing the quoted
        # command. This does not claim to emulate Claude Code's skill loader.
        command = match.group(1).replace('${CLAUDE_SKILL_DIR}', str(self.adapter))
        self.command = shlex.split(command)
        self.command[0] = sys.executable  # Use the test environment's dependencies.
        self.command = [self.source.name if part == 'documento.md' else
                        self.output.name if part == 'documento.pdf' else part
                        for part in self.command]
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def run_converter(self, *options):
        return subprocess.run([*self.command, *options], cwd=self.workspace,
                              env=self.environment, text=True, capture_output=True,
                              timeout=120)

    def test_documented_entry_resolves_shared_skill_and_cli_after_relocation(self):
        text = (self.adapter / 'SKILL.md').read_text(encoding='utf-8')
        canonical_link = re.search(r'\[SKILL canónico\]\(([^)]+)\)', text)
        self.assertIsNotNone(canonical_link)
        self.assertEqual((self.adapter / canonical_link.group(1)).resolve(),
                         self.skill / 'SKILL.md')
        self.assertEqual(Path(self.command[1]).resolve(),
                         self.skill / 'scripts/convert_markdown_to_pdf.py')
        self.assertFalse((self.skill / '.venv').exists())
        result = self.run_converter('--help')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('--strict', result.stdout)
        self.assertIn('--no-logo', result.stdout)

    @unittest.skipUnless(os.environ.get('MDPDF_BROWSER_TESTS') == '1',
                         'Requiere MDPDF_BROWSER_TESTS=1')
    def test_adapter_command_renders_pdf_and_preserves_it_after_invalid_input(self):
        from pypdf import PdfReader

        markdown = r'''# Informe de integración

## Proceso

Figura: Revisión {#fig:revision}

```mermaid
flowchart LR
 A[Entrada] --> B[Resultado]
```

Consulta [@fig:revision]. La fórmula es \(x^2\).
'''
        self.source.write_text(markdown, encoding='utf-8')
        result = self.run_converter('--strict')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Engine: playwright', result.stdout)
        self.assertIn('Validación: sin incidencias detectadas', result.stdout)
        self.assertEqual(self.source.read_text(encoding='utf-8'), markdown)
        with PdfReader(self.output) as reader:
            text = ' '.join(page.extract_text() or '' for page in reader.pages)
            self.assertIn('Informe de integración', text)
            self.assertIn('Entrada', text)
            self.assertIn('Resultado', text)
            self.assertNotIn('flowchart LR', text)
        previous_pdf = self.output.read_bytes()
        invalid = '# Error de prueba\n\n```mermaid\nflowchart LR\nA --> [\n```\n'
        self.source.write_text(invalid, encoding='utf-8')
        result = self.run_converter('--strict', '--force')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Mermaid', result.stderr)
        self.assertEqual(self.output.read_bytes(), previous_pdf)
        self.assertEqual(self.source.read_text(encoding='utf-8'), invalid)


if __name__ == '__main__':
    unittest.main()
