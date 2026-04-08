"""Testes para o texto explícito de gasto duplo no monitor."""

import unittest

from app.voting.app_desktop import montar_texto_monitor


class MonitorAlertasTests(unittest.TestCase):
    def test_monitor_mostra_bloco_explicito_quando_ha_gasto_duplo(self):
        texto = montar_texto_monitor(
            {"message": "API funcionando"},
            {
                "length": 1,
                "chain": [
                    {
                        "index": 0,
                        "hash": "0000abc123",
                        "previous_hash": "0" * 64,
                        "nonce": 0,
                        "difficulty": 1,
                        "transactions": [{"type": "genesis", "data": "Início da Votação"}],
                    }
                ],
            },
            {"count": 0, "transactions": []},
            {"count": 0, "forks": []},
            {
                "count": 1,
                "events": [
                    {
                        "event_id": 1,
                        "type": "gasto_duplo_detectado",
                        "reason": "nullifier duplicado",
                        "tx_id": "tx-ataque",
                        "nullifier": "serial-ataque",
                        "candidate_id": "Candidato A",
                        "detected_at": 0,
                    }
                ],
            },
        )

        self.assertIn("STATUS DE SEGURANCA", texto)
        self.assertIn("ATAQUE DE GASTO DUPLO DETECTADO", texto)
        self.assertIn("Serial reutilizado:", texto)

    def test_monitor_mostra_ausencia_de_ataque_quando_nao_ha_alertas(self):
        texto = montar_texto_monitor(
            {"message": "API funcionando"},
            {"length": 0, "chain": []},
            {"count": 0, "transactions": []},
            {"count": 0, "forks": []},
            {"count": 0, "events": []},
        )

        self.assertIn("Nenhum ataque de gasto duplo detectado.", texto)
