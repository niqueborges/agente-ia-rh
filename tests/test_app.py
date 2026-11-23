"""
Testes de integração e interface para a aplicação Streamlit (app.py).
"""

from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

CAMINHO_APP = str(Path(__file__).resolve().parent.parent / "app.py")


class TestAppStreamlit:
    """Testes de inicialização e interface do app.py."""

    def test_app_inicializa_sem_excecoes(self):
        at = AppTest.from_file(CAMINHO_APP, default_timeout=20.0)
        at.run()
        assert not at.exception
        assert len(at.title) > 0
        assert "Assistente de RH" in at.title[0].value

    def test_app_trata_ollama_indisponivel(self):
        with patch("rag.ollama_client.verificar_conexao_ollama", return_value=False):
            at = AppTest.from_file(CAMINHO_APP, default_timeout=10.0)
            at.run()
            assert len(at.error) > 0
            assert "Servidor Ollama indisponível" in at.error[0].value
