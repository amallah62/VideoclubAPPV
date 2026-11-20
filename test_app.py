
"""Automated tests for the Videoclub application.

Run with: python -m unittest -v
Each test uses its own temporary database.
"""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import app


class BaseTest(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        self._db_original = app.DB_NAME
        app.DB_NAME = self.db_path
        app.inicializar_bd()

        self.id_videoclub = app.Videoclub(
            "Carlos Pérez", "Madrid", "Calle Mayor 12", "28013"
        ).guardar()

        self.id_p1 = app.Pelicula(
            self.id_videoclub,
            "Matrix",
            "Wachowski Sisters",
            "1999-03-31",
            3.50,
        ).guardar()

        self.id_p2 = app.Pelicula(
            self.id_videoclub,
            "Inception",
            "Christopher Nolan",
            "2010-07-16",
            4.00,
        ).guardar()

        self.id_socio = app.Socio("Ana Gómez", 25).guardar()

    def tearDown(self):
        app.DB_NAME = self._db_original
        os.remove(self.db_path)

    def contar(self, tabla):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM {tabla}"
            ).fetchone()[0]

    def nuevo_alquiler(
        self,
        recogida="2026-06-01",
        devolucion="2026-06-10",
        ids=None,
    ):
        return app.Alquiler(
            self.id_socio,
            recogida,
            devolucion,
            ids or [self.id_p1, self.id_p2],
        )


class TestAlquiler(BaseTest):

    def test_total_es_suma_de_precios(self):
        self.assertAlmostEqual(
            self.nuevo_alquiler().total_pagar, 7.50
        )

    def test_guardar_registra_alquiler_y_peliculas(self):
        id_alq = self.nuevo_alquiler().guardar()

        self.assertIsNotNone(id_alq)
        self.assertEqual(self.contar("Alquiler"), 1)
        self.assertEqual(self.contar("Alquiler_Pelicula"), 2)

    def test_pelicula_inexistente_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "does not exist"
        ):
            self.nuevo_alquiler(
                ids=[self.id_p1, 9999]
            )

        self.assertEqual(self.contar("Alquiler"), 0)

    def test_alquiler_sin_peliculas_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "at least one movie"
        ):
            app.Alquiler(
                self.id_socio,
                "2026-06-01",
                "2026-06-10",
                [],
            )

    def test_pelicula_repetida_se_cobra_una_vez(self):
        alquiler = self.nuevo_alquiler(
            ids=[self.id_p1, self.id_p1]
        )

        self.assertAlmostEqual(
            alquiler.total_pagar, 3.50
        )

        alquiler.guardar()

        self.assertEqual(
            self.contar("Alquiler_Pelicula"), 1
        )

    def test_devolucion_anterior_a_recogida_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "later than the pickup date"
        ):
            self.nuevo_alquiler(
                recogida="2026-06-10",
                devolucion="2026-06-01",
            )

    def test_devolucion_igual_a_recogida_lanza_error(self):
        with self.assertRaises(ValueError):
            self.nuevo_alquiler(
                recogida="2026-06-10",
                devolucion="2026-06-10",
            )

    def test_formato_de_fecha_invalido_lanza_error(self):
        fechas = (
            "01/06/2026",
            "2026-13-01",
            "2026-02-30",
            "",
            None,
        )

        for fecha in fechas:
            with self.subTest(fecha=fecha):
                with self.assertRaisesRegex(
                    ValueError, "Invalid date"
                ):
                    self.nuevo_alquiler(recogida=fecha)

    def test_socio_inexistente_no_se_guarda(self):
        alquiler = app.Alquiler(
            9999,
            "2026-06-01",
            "2026-06-10",
            [self.id_p1],
        )

        with self.assertRaises(sqlite3.IntegrityError):
            alquiler.guardar()

        self.assertEqual(self.contar("Alquiler"), 0)


class TestModificarFechaDevolucion(BaseTest):

    def setUp(self):
        super().setUp()
        self.id_alq = self.nuevo_alquiler().guardar()

    def fecha_guardada(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(
                """
                SELECT fecha_devolucion
                FROM Alquiler
                WHERE id_alquiler = ?
                """,
                (self.id_alq,),
            ).fetchone()[0]

    def test_fecha_valida_se_actualiza(self):
        app.Alquiler.modificar_fecha_devolucion(
            self.id_alq,
            "2026-06-20",
            "2026-06-05",
        )

        self.assertEqual(
            self.fecha_guardada(), "2026-06-20"
        )

    def test_fecha_pasada_lanza_error_y_no_cambia(self):
        with self.assertRaisesRegex(
            ValueError, "later than the current date"
        ):
            app.Alquiler.modificar_fecha_devolucion(
                self.id_alq,
                "2026-05-01",
                "2026-06-05",
            )

        self.assertEqual(
            self.fecha_guardada(), "2026-06-10"
        )

    def test_fecha_igual_a_hoy_lanza_error(self):
        with self.assertRaises(ValueError):
            app.Alquiler.modificar_fecha_devolucion(
                self.id_alq,
                "2026-06-05",
                "2026-06-05",
            )

    def test_formato_invalido_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "Invalid date"
        ):
            app.Alquiler.modificar_fecha_devolucion(
                self.id_alq,
                "20/06/2026",
                "2026-06-05",
            )

    def test_alquiler_inexistente_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "does not exist"
        ):
            app.Alquiler.modificar_fecha_devolucion(
                9999,
                "2026-06-20",
                "2026-06-05",
            )


class TestEstadistica(BaseTest):

    def setUp(self):
        super().setUp()

        self.admin = app.Administrador("Lucia Admin")
        self.admin.guardar()

    def test_suma_alquileres_del_mes(self):
        self.nuevo_alquiler().guardar()

        self.nuevo_alquiler(
            "2026-06-15",
            "2026-06-20",
            [self.id_p1],
        ).guardar()

        self.nuevo_alquiler(
            "2026-07-01",
            "2026-07-05",
            [self.id_p2],
        ).guardar()

        est = self.admin.generar_estadistica(
            self.id_socio,
            "2026-06",
            "2026-06-30",
        )

        self.assertAlmostEqual(
            est.total_gastado, 11.00
        )

        self.assertEqual(
            self.contar("Estadistica"), 1
        )

    def test_calcular_total_gastado_directamente(self):
        self.nuevo_alquiler().guardar()

        est = app.Estadistica(
            self.id_socio,
            self.admin.id_administrador,
            "2026-06",
            "2026-06-30",
        )

        self.assertAlmostEqual(
            est.calcular_total_gastado(), 7.50
        )

    def test_guarda_que_administrador_la_genero(self):
        self.admin.generar_estadistica(
            self.id_socio,
            "2026-06",
            "2026-06-30",
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            id_admin = conn.execute(
                "SELECT id_administrador FROM Estadistica"
            ).fetchone()[0]

        self.assertEqual(
            id_admin, self.admin.id_administrador
        )

    def test_administrador_no_guardado_lanza_error(self):
        admin = app.Administrador("Sin guardar")

        with self.assertRaisesRegex(
            ValueError, "must be saved first"
        ):
            admin.generar_estadistica(
                self.id_socio,
                "2026-06",
                "2026-06-30",
            )

    def test_administrador_inexistente_no_se_guarda(self):
        est = app.Estadistica(
            self.id_socio,
            9999,
            "2026-06",
            "2026-06-30",
        )

        with self.assertRaises(sqlite3.IntegrityError):
            est.guardar()

        self.assertEqual(
            self.contar("Estadistica"), 0
        )

    def test_mes_sin_alquileres_da_cero(self):
        est = self.admin.generar_estadistica(
            self.id_socio,
            "2026-01",
            "2026-01-31",
        )

        self.assertEqual(
            est.total_gastado, 0.0
        )

    def test_estadistica_duplicada_lanza_error(self):
        self.nuevo_alquiler().guardar()

        self.admin.generar_estadistica(
            self.id_socio,
            "2026-06",
            "2026-06-30",
        )

        with self.assertRaisesRegex(
            ValueError, "already exists"
        ):
            self.admin.generar_estadistica(
                self.id_socio,
                "2026-06",
                "2026-06-30",
            )

        self.assertEqual(
            self.contar("Estadistica"), 1
        )

    def test_duplicada_aunque_la_genere_otro_administrador(self):
        otro = app.Administrador("Pedro Admin")
        otro.guardar()

        self.admin.generar_estadistica(
            self.id_socio,
            "2026-06",
            "2026-06-30",
        )

        with self.assertRaisesRegex(
            ValueError, "already exists"
        ):
            otro.generar_estadistica(
                self.id_socio,
                "2026-06",
                "2026-06-30",
            )

    def test_mismo_socio_otro_mes_si_se_permite(self):
        self.admin.generar_estadistica(
            self.id_socio,
            "2026-06",
            "2026-06-30",
        )

        self.admin.generar_estadistica(
            self.id_socio,
            "2026-07",
            "2026-07-31",
        )

        self.assertEqual(
            self.contar("Estadistica"), 2
        )

    def test_mes_invalido_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError, "Invalid month"
        ):
            self.admin.generar_estadistica(
                self.id_socio,
                "2026-13",
                "2026-06-30",
            )

    def test_socio_inexistente_lanza_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "Member with ID 9999 does not exist",
        ):
            self.admin.generar_estadistica(
                9999,
                "2026-06",
                "2026-06-30",
            )


class TestEntidades(BaseTest):

    def test_precio_negativo_lanza_error(self):
        with self.assertRaises(ValueError):
            app.Pelicula(
                self.id_videoclub,
                "X",
                "Y",
                "2020-01-01",
                -1,
            )

    def test_fecha_estreno_invalida_lanza_error(self):
        with self.assertRaises(ValueError):
            app.Pelicula(
                self.id_videoclub,
                "X",
                "Y",
                "31-03-1999",
                3.0,
            )

    def test_pelicula_de_videoclub_inexistente_no_se_guarda(self):
        pelicula = app.Pelicula(
            9999,
            "X",
            "Y",
            "2020-01-01",
            3.0,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            pelicula.guardar()

    def test_edad_negativa_lanza_error(self):
        with self.assertRaises(ValueError):
            app.Socio("Luis", -5)

    def test_campo_obligatorio_nulo_no_se_guarda(self):
        socio = app.Socio(None, 30)

        with self.assertRaises(sqlite3.IntegrityError):
            socio.guardar()


class TestRequisitosEnunciado(BaseTest):

    def test_codigo_postal_debe_tener_5_caracteres(self):
        for cp in ("2801", "280130", "", None):
            with self.subTest(cp=cp):
                with self.assertRaisesRegex(
                    ValueError, "postal code"
                ):
                    app.Videoclub(
                        "Carlos",
                        "Madrid",
                        "Calle Mayor 12",
                        cp,
                    )

    def test_campos_obligatorios_del_videoclub(self):
        with self.assertRaisesRegex(
            ValueError, "required"
        ):
            app.Videoclub(
                "  ",
                "Madrid",
                "Calle Mayor 12",
                "28013",
            )

    def test_misma_pelicula_en_distintos_videoclubs(self):
        id_v2 = app.Videoclub(
            "Eva Ruiz",
            "Valencia",
            "Calle Colón 3",
            "46004",
        ).guardar()

        id_copia = app.Pelicula(
            id_v2,
            "Matrix",
            "Wachowski Sisters",
            "1999-03-31",
            3.00,
        ).guardar()

        self.assertNotEqual(id_copia, self.id_p1)
        self.assertEqual(self.contar("Pelicula"), 3)

    def test_socio_alquila_en_varios_videoclubs(self):
        id_v2 = app.Videoclub(
            "Eva Ruiz",
            "Valencia",
            "Calle Colón 3",
            "46004",
        ).guardar()

        id_p3 = app.Pelicula(
            id_v2,
            "Up",
            None,
            "2009-05-29",
            2.50,
        ).guardar()

        alquiler = self.nuevo_alquiler(
            ids=[self.id_p1, id_p3]
        )

        self.assertAlmostEqual(
            alquiler.total_pagar, 6.00
        )

    def test_fecha_de_recogida_no_es_editable(self):
        self.assertFalse(
            hasattr(
                app.Alquiler,
                "modificar_fecha_recogida",
            )
        )

    def test_cargar_administrador(self):
        id_admin = app.Administrador(
            "Lucia Admin"
        ).guardar()

        self.assertEqual(
            app.Administrador.cargar(id_admin).nombre,
            "Lucia Admin",
        )

        with self.assertRaisesRegex(
            ValueError, "does not exist"
        ):
            app.Administrador.cargar(9999)


class TestEntradaManual(BaseTest):
    """Dates must be entered manually."""

    def test_pedir_fecha_repite_hasta_que_es_valida(self):
        with (
            mock.patch(
                "builtins.input",
                side_effect=[
                    "01/06/2026",
                    "2026-02-30",
                    "2026-06-01",
                ],
            ),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(
                app.pedir_fecha("Fecha"),
                "2026-06-01",
            )

    def test_pedir_mes_repite_hasta_que_es_valido(self):
        with (
            mock.patch(
                "builtins.input",
                side_effect=["2026-13", "2026-06"],
            ),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(
                app.pedir_mes("Mes"),
                "2026-06",
            )

    def test_alquiler_desde_el_menu_con_fechas_tecleadas(self):
        entradas = [
            "4",
            str(self.id_socio),
            "2026-06-01",
            "2026-06-10",
            f"{self.id_p1}, {self.id_p2}",
            "0",
        ]

        with (
            mock.patch(
                "builtins.input",
                side_effect=entradas,
            ),
            mock.patch("builtins.print"),
        ):
            app.menu()

        with closing(sqlite3.connect(self.db_path)) as conn:
            fila = conn.execute(
                """
                SELECT fecha_recogida,
                       fecha_devolucion,
                       total_pagar
                FROM Alquiler
                """
            ).fetchone()

        self.assertEqual(
            fila,
            ("2026-06-01", "2026-06-10", 7.5),
        )

    def test_menu_no_se_cierra_ante_un_error(self):
        entradas = [
            "5",
            "9999",
            "2026-06-05",
            "2026-06-20",
            "0",
        ]

        with (
            mock.patch(
                "builtins.input",
                side_effect=entradas,
            ),
            mock.patch("builtins.print") as salida,
        ):
            app.menu()

        mensajes = " ".join(
            str(c.args[0])
            for c in salida.call_args_list
            if c.args
        )

        self.assertIn("does not exist", mensajes)

    def test_no_se_usa_la_fecha_del_sistema(self):
        with open(app.__file__, encoding="utf-8") as f:
            codigo = f.read()

        llamadas = (
            "datetime.now(",
            "date.today(",
            "datetime.today(",
            "time.time(",
        )

        for llamada in llamadas:
            self.assertNotIn(llamada, codigo)


if __name__ == "__main__":
    unittest.main()
