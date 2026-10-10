import os
import unittest
from unittest.mock import patch

from app import create_app, db
from app.instance.models import (
    Conjunto,
    ConjuntoPeca,
    Leitura,
    Pedido,
    PedidoItem,
    Peca,
    StatusLeitura,
)
from app.instance.seed import seed_demo_data


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

    def test_seed_demo_data_creates_deterministic_demo_dataset(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret-key"}):
            app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite://"})
        app.config["TESTING"] = True

        with app.app_context():
            db.drop_all()
            db.create_all()
            seed_demo_data()
            seed_demo_data()

            pedido = Pedido.query.filter_by(codigo="PED-1001").one()
            self.assertEqual(Peca.query.count(), 4)
            self.assertEqual(Pedido.query.count(), 1)
            self.assertEqual(PedidoItem.query.filter_by(pedido_id=pedido.id).count(), 3)
            self.assertEqual(Leitura.query.filter_by(pedido_id=pedido.id).count(), 3)
            self.assertEqual(
                Leitura.query.filter_by(
                    pedido_id=pedido.id,
                    status=StatusLeitura.FORA_DO_PEDIDO,
                ).count(),
                1,
            )
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        with patch.dict(os.environ, {"SECRET_KEY": "test-secret-key"}):
            self.app = create_app(
                {
                    "TESTING": True,
                    "SQLALCHEMY_DATABASE_URI": "sqlite://",
                }
            )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_piece_crud_validates_required_fields_and_unique_values(self):
        response = self.client.post(
            "/pecas/novo",
            data={"codigo": "P-1", "descricao": "", "codigo_barras": "B-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Todos os campos são obrigatórios.", response.get_data(as_text=True))
        self.assertEqual(Peca.query.count(), 0)

        response = self.client.post(
            "/pecas/novo",
            data={"codigo": "P-1", "descricao": "Peça 1", "codigo_barras": "B-1"},
            follow_redirects=True,
        )
        self.assertIn("Peça adicionada com sucesso!", response.get_data(as_text=True))
        peca = Peca.query.filter_by(codigo="P-1").one()

        response = self.client.post(
            "/pecas/novo",
            data={"codigo": "P-1", "descricao": "Duplicada", "codigo_barras": "B-2"},
        )
        self.assertIn("Já existe uma peça", response.get_data(as_text=True))
        self.assertEqual(Peca.query.count(), 1)

        response = self.client.post(
            f"/pecas/editar/{peca.id}",
            data={"codigo": "", "descricao": "Atualizada", "codigo_barras": "B-1"},
        )
        self.assertIn("Todos os campos são obrigatórios.", response.get_data(as_text=True))
        self.assertEqual(db.session.get(Peca, peca.id).codigo, "P-1")

        response = self.client.post(
            f"/pecas/editar/{peca.id}",
            data={"codigo": "P-1A", "descricao": "Atualizada", "codigo_barras": "B-1A"},
            follow_redirects=True,
        )
        self.assertIn("Peça atualizada com sucesso!", response.get_data(as_text=True))
        self.assertEqual(db.session.get(Peca, peca.id).descricao, "Atualizada")

        response = self.client.post(f"/pecas/apagar/{peca.id}", follow_redirects=True)
        self.assertIn("Peça excluída com sucesso!", response.get_data(as_text=True))
        self.assertEqual(Peca.query.count(), 0)

    def test_conjunto_crud_and_piece_association_validate_quantities(self):
        peca = Peca(codigo="P-1", descricao="Peça", codigo_barras="B-1")
        db.session.add(peca)
        db.session.commit()
        response = self.client.post(
            "/conjuntos/novo",
            data={"codigo": "", "descricao": "Sem código"},
        )
        self.assertIn("Código e descrição são obrigatórios.", response.get_data(as_text=True))
        self.assertEqual(Conjunto.query.count(), 0)

        response = self.client.post(
            "/conjuntos/novo",
            data={"codigo": "C-1", "descricao": "Conjunto"},
            follow_redirects=True,
        )
        self.assertIn("Conjunto adicionado com sucesso!", response.get_data(as_text=True))
        conjunto = Conjunto.query.filter_by(codigo="C-1").one()

        response = self.client.post(
            f"/conjuntos/{conjunto.id}/pecas/adicionar",
            data={"peca_id": str(peca.id), "quantidade": "0"},
            follow_redirects=True,
        )
        self.assertIn("quantidade deve ser", response.get_data(as_text=True))
        self.assertEqual(ConjuntoPeca.query.count(), 0)

        self.client.post(
            f"/conjuntos/{conjunto.id}/pecas/adicionar",
            data={"peca_id": str(peca.id), "quantidade": "2"},
        )
        assoc = ConjuntoPeca.query.one()
        self.assertEqual(assoc.quantidade, 2)

        response = self.client.post(
            f"/conjuntos/{conjunto.id}/pecas/editar/{assoc.id}",
            data={"quantidade": "abc"},
            follow_redirects=True,
        )
        self.assertIn("quantidade deve ser", response.get_data(as_text=True))
        self.assertEqual(ConjuntoPeca.query.one().quantidade, 2)

        self.client.post(
            "/conjuntos/novo",
            data={"codigo": "C-2", "descricao": "Outro conjunto"},
        )
        outro_conjunto = Conjunto.query.filter_by(codigo="C-2").one()
        response = self.client.post(
            f"/conjuntos/{outro_conjunto.id}/pecas/remover/{assoc.id}"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ConjuntoPeca.query.count(), 1)

        self.client.post(
            f"/conjuntos/{conjunto.id}/pecas/editar/{assoc.id}",
            data={"quantidade": "3"},
        )
        self.assertEqual(ConjuntoPeca.query.one().quantidade, 3)
        self.client.post(f"/conjuntos/{conjunto.id}/pecas/remover/{assoc.id}")
        self.assertEqual(ConjuntoPeca.query.count(), 0)

        response = self.client.post(
            f"/conjuntos/editar/{conjunto.id}",
            data={"codigo": "", "descricao": "Sem código"},
        )
        self.assertIn("Código e descrição são obrigatórios.", response.get_data(as_text=True))
        response = self.client.post(
            f"/conjuntos/editar/{conjunto.id}",
            data={"codigo": "C-1A", "descricao": "Atualizado"},
            follow_redirects=True,
        )
        self.assertIn("Conjunto atualizado com sucesso!", response.get_data(as_text=True))
        self.assertEqual(db.session.get(Conjunto, conjunto.id).descricao, "Atualizado")

        self.client.post(f"/conjuntos/apagar/{conjunto.id}")
        self.assertIsNone(db.session.get(Conjunto, conjunto.id))

    def test_order_item_crud_validates_quantities_and_preserves_read_history(self):
        peca = Peca(codigo="P-1", descricao="Peça", codigo_barras="B-1")
        db.session.add(peca)
        db.session.commit()
        response = self.client.post(
            "/pedidos/novo",
            data={"codigo": ""},
        )
        self.assertIn("Código do pedido é obrigatório.", response.get_data(as_text=True))
        self.assertEqual(Pedido.query.count(), 0)
        response = self.client.post(
            "/pedidos/novo",
            data={"codigo": "PED-1"},
            follow_redirects=True,
        )
        self.assertIn("Pedido adicionado com sucesso!", response.get_data(as_text=True))
        pedido = Pedido.query.filter_by(codigo="PED-1").one()

        response = self.client.post(
            f"/pedidos/{pedido.id}/itens/adicionar",
            data={"peca_id": str(peca.id), "quantidade_necessaria": "abc"},
            follow_redirects=True,
        )
        self.assertIn("quantidade inteira positiva", response.get_data(as_text=True))
        self.assertEqual(PedidoItem.query.count(), 0)

        self.client.post(
            f"/pedidos/{pedido.id}/itens/adicionar",
            data={"peca_id": str(peca.id), "quantidade_necessaria": "2"},
        )
        item = PedidoItem.query.one()
        self.assertEqual(item.quantidade_necessaria, 2)

        response = self.client.post(
            f"/pedidos/{pedido.id}/itens/editar/{item.id}",
            data={"quantidade_necessaria": "0"},
            follow_redirects=True,
        )
        self.assertIn("quantidade deve ser", response.get_data(as_text=True))
        self.assertEqual(PedidoItem.query.one().quantidade_necessaria, 2)

        self.client.post(
            f"/pedidos/{pedido.id}/itens/editar/{item.id}",
            data={"quantidade_necessaria": "4"},
        )
        self.assertEqual(PedidoItem.query.one().quantidade_necessaria, 4)
        self.client.post(f"/pedidos/{pedido.id}/itens/remover/{item.id}")
        self.assertEqual(PedidoItem.query.count(), 0)

        response = self.client.post(
            f"/pedidos/editar/{pedido.id}",
            data={"codigo": ""},
        )
        self.assertIn("Código do pedido é obrigatório.", response.get_data(as_text=True))
        response = self.client.post(
            f"/pedidos/editar/{pedido.id}",
            data={"codigo": "PED-1A"},
            follow_redirects=True,
        )
        self.assertIn("Pedido atualizado com sucesso!", response.get_data(as_text=True))

        leitura = Leitura(
            pedido_id=pedido.id,
            peca_id=peca.id,
            status=StatusLeitura.SUCESSO,
        )
        db.session.add(leitura)
        db.session.commit()
        response = self.client.post(
            f"/pedidos/apagar/{pedido.id}",
            follow_redirects=True,
        )
        self.assertIn("possui leituras registradas", response.get_data(as_text=True))
        self.assertIsNotNone(db.session.get(Pedido, pedido.id))

        response = self.client.post(
            f"/pecas/apagar/{peca.id}",
            follow_redirects=True,
        )
        self.assertIn("associada a conjuntos, pedidos ou leituras", response.get_data(as_text=True))
        self.assertIsNotNone(db.session.get(Peca, peca.id))

        outro_pedido = Pedido(codigo="PED-2")
        db.session.add(outro_pedido)
        db.session.commit()
        self.client.post(
            f"/pedidos/{outro_pedido.id}/itens/adicionar",
            data={"peca_id": str(peca.id), "quantidade_necessaria": "1"},
        )
        response = self.client.post(
            f"/pedidos/apagar/{outro_pedido.id}",
            follow_redirects=True,
        )
        self.assertIn("Pedido excluído com sucesso!", response.get_data(as_text=True))
        self.assertIsNone(db.session.get(Pedido, outro_pedido.id))
        self.assertEqual(PedidoItem.query.filter_by(pedido_id=outro_pedido.id).count(), 0)

    def test_order_scanner_validates_codes_and_tracks_progress(self):
        pedido = Pedido(codigo="PED-VALIDA")
        peca = Peca(codigo="P-VALIDA", descricao="Peça válida", codigo_barras="B-VALIDA")
        peca_fora = Peca(codigo="P-FORA", descricao="Peça fora", codigo_barras="B-FORA")
        db.session.add_all([pedido, peca, peca_fora])
        db.session.commit()
        self.assertEqual(pedido.progresso()["status"], "sem_itens")
        db.session.add(PedidoItem(pedido_id=pedido.id, peca_id=peca.id, quantidade_necessaria=2))
        db.session.commit()
        self.assertEqual(pedido.progresso()["status"], "em_andamento")

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "erro")

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": "CODIGO-INEXISTENTE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "fora_do_pedido")
        self.assertEqual(response.get_json()["progress"]["percentual"], 0)
        self.assertEqual(Leitura.query.filter_by(pedido_id=pedido.id).count(), 0)

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": peca.codigo_barras},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "sucesso")
        self.assertEqual(Leitura.query.filter_by(pedido_id=pedido.id, peca_id=peca.id, status=StatusLeitura.SUCESSO).count(), 1)
        self.assertEqual(payload["progress"]["percentual"], 50.0)
        self.assertEqual(payload["progress"]["status"], "em_andamento")

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": peca.codigo_barras},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "sucesso")
        self.assertEqual(payload["progress"]["percentual"], 100.0)
        self.assertEqual(payload["progress"]["status"], "finalizado")
        scanner_page = self.client.get(f"/pedidos/{pedido.id}/scanner").get_data(as_text=True)
        self.assertIn("Separação finalizada", scanner_page)
        detail_page = self.client.get(f"/pedidos/{pedido.id}/detalhe").get_data(as_text=True)
        self.assertIn("100.0%", detail_page)

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": peca.codigo_barras},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "duplicada")

        response = self.client.post(
            f"/pedidos/{pedido.id}/scanner/validar",
            json={"codigo": peca_fora.codigo_barras},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "fora_do_pedido")
        self.assertEqual(
            Leitura.query.filter_by(
                pedido_id=pedido.id,
                peca_id=peca_fora.id,
                status=StatusLeitura.FORA_DO_PEDIDO,
            ).count(),
            1,
        )

    def test_order_scanner_page_and_local_scanner_assets_are_available(self):
        pedido = Pedido(codigo="PED-SCANNER")
        db.session.add(pedido)
        db.session.commit()

        response = self.client.get(f"/pedidos/{pedido.id}/scanner")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Iniciar câmera", page)
        self.assertIn("camera-select", page)
        self.assertIn("scanner-status", page)
        self.assertIn("pedido-progress-value", page)
        self.assertIn("Acompanhamento do pedido", page)
        self.assertIn("Pedido sem itens", page)
        self.assertIn("/static/vendor/html5-qrcode.min.js", page)
        self.assertIn("/static/js/scanner.js", page)

        library_response = self.client.get("/static/vendor/html5-qrcode.min.js")
        self.assertEqual(library_response.status_code, 200)
        self.assertGreater(len(library_response.data), 100_000)

        script_response = self.client.get("/static/js/scanner.js")
        self.assertEqual(script_response.status_code, 200)
        self.assertIn(b"PermissionDeniedError", script_response.data)
        self.assertIn(b"Nenhum c", script_response.data)

        css_response = self.client.get("/static/css/scanner.css")
        self.assertEqual(css_response.status_code, 200)

        missing_order_response = self.client.get("/pedidos/999999/scanner")
        self.assertEqual(missing_order_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
