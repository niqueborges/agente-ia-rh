"""Configurações globais e fixtures para o pytest."""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH para resolução dos módulos
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))
