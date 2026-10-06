import os
import unittest
from unittest.mock import patch

from app import create_app
from app.instance.models import Conjunto, Pedido, Peca


class TestTagcontrolApp(unittest.TestCase):
    def test_create_app_registers_all_blueprints(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret-key"}):
            app = create_app()

        self.assertEqual(app.config["SECRET_KEY"], "test-secret-key")
        self.assertIn("pecas", app.blueprints)
        self.assertIn("conjuntos", app.blueprints)
        self.assertIn("pedidos", app.blueprints)

    def test_create_app_requires_secret_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                create_app()

    def test_required_models_expose_core_fields(self):
        self.assertTrue(hasattr(Peca, "codigo"))
        self.assertTrue(hasattr(Peca, "descricao"))
        self.assertTrue(hasattr(Peca, "codigo_barras"))

        self.assertTrue(hasattr(Conjunto, "codigo"))
        self.assertTrue(hasattr(Conjunto, "descricao"))

        self.assertTrue(hasattr(Pedido, "codigo"))
        self.assertTrue(hasattr(Pedido, "itens"))
        self.assertTrue(hasattr(Pedido, "leituras"))


if __name__ == "__main__":
    unittest.main()
