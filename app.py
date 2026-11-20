from contextlib import closing, contextmanager
from datetime import datetime
import os
import sqlite3

# SQLite Database Configuration
DB_NAME = "videoclub_appv.db"
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
DATE_FORMAT = "%Y-%m-%d"


def conectar():
  """Opens a connection with foreign keys enabled (SQLite disables them by default)."""
  conn = sqlite3.connect(DB_NAME)
  conn.execute("PRAGMA foreign_keys = ON")
  return conn


@contextmanager
def transaccion():
  """Opens a connection, commits on success / rolls back on error, and always closes it."""
  with closing(conectar()) as conn:
    with conn:
      yield conn


def inicializar_bd():
  with transaccion() as conn:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
      conn.executescript(f.read())


def _validar_fecha(fecha_str):
  """Returns a datetime or raises ValueError if the format is not YYYY-MM-DD."""
  try:
    return datetime.strptime(fecha_str, DATE_FORMAT)
  except (TypeError, ValueError) as exc:
    raise ValueError(f"Error: Invalid date '{fecha_str}', expected YYYY-MM-DD.") from exc


class Videoclub:

  def __init__(self, nombre_gerente, ciudad, calle, codigo_postal):
    for campo, valor in (
        ("nombre_gerente", nombre_gerente), ("ciudad", ciudad), ("calle", calle)
    ):
      if not valor or not str(valor).strip():
        raise ValueError(f"Error: The field '{campo}' is required.")
    if codigo_postal is None or len(str(codigo_postal)) != 5:
      raise ValueError("Error: The postal code must have exactly 5 characters.")
    self.nombre_gerente = nombre_gerente
    self.ciudad = ciudad
    self.calle = calle
    self.codigo_postal = codigo_postal

  def guardar(self):
    with transaccion() as conn:
      cursor = conn.execute(
          """INSERT INTO Videoclub (nombre_gerente, ciudad, calle, codigo_postal)
             VALUES (?, ?, ?, ?)""",
          (self.nombre_gerente, self.ciudad, self.calle, self.codigo_postal),
      )
      return cursor.lastrowid


class Pelicula:

  def __init__(
      self, id_videoclub, nombre, director, fecha_estreno, precio_alquiler
  ):
    if precio_alquiler is None or precio_alquiler < 0:
      raise ValueError("Error: The rental price cannot be negative.")
    _validar_fecha(fecha_estreno)
    self.id_videoclub = id_videoclub
    self.nombre = nombre
    self.director = director
    self.fecha_estreno = fecha_estreno
    self.precio_alquiler = precio_alquiler

  def guardar(self):
    with transaccion() as conn:
      cursor = conn.execute(
          """INSERT INTO Pelicula (id_videoclub, nombre, director, fecha_estreno, precio_alquiler)
             VALUES (?, ?, ?, ?, ?)""",
          (
              self.id_videoclub,
              self.nombre,
              self.director,
              self.fecha_estreno,
              self.precio_alquiler,
          ),
      )
      return cursor.lastrowid


class Socio:

  def __init__(self, nombre, edad):
    if edad is None or edad < 0:
      raise ValueError("Error: Age cannot be negative.")
    self.nombre = nombre
    self.edad = edad

  def guardar(self):
    with transaccion() as conn:
      cursor = conn.execute(
          "INSERT INTO Socio (nombre, edad) VALUES (?, ?)",
          (self.nombre, self.edad),
      )
      return cursor.lastrowid


class Alquiler:

  def __init__(self, id_socio, fecha_recogida, fecha_devolucion, ids_peliculas):
    f_recogida = _validar_fecha(fecha_recogida)
    f_devolucion = _validar_fecha(fecha_devolucion)
    if f_devolucion <= f_recogida:
      raise ValueError(
          "Error: The return date must be later than the pickup date."
      )
    if not ids_peliculas:
      raise ValueError("Error: A rental must include at least one movie.")

    self.id_socio = id_socio
    self.fecha_recogida = fecha_recogida
    self.fecha_devolucion = fecha_devolucion
    self.ids_peliculas = list(dict.fromkeys(ids_peliculas))  # drop duplicates
    self.total_pagar = self.calcular_total()

  def calcular_total(self):
    total = 0.0
    with closing(conectar()) as conn:
      for id_p in self.ids_peliculas:
        res = conn.execute(
            "SELECT precio_alquiler FROM Pelicula WHERE id_pelicula = ?", (id_p,)
        ).fetchone()
        if res is None:
          raise ValueError(f"Error: Movie with ID {id_p} does not exist.")
        total += res[0]
    return round(total, 2)

  def guardar(self):
    # Single transaction: if any insert fails, nothing is saved.
    with transaccion() as conn:
      cursor = conn.execute(
          """INSERT INTO Alquiler (id_socio, fecha_recogida, fecha_devolucion, total_pagar)
             VALUES (?, ?, ?, ?)""",
          (
              self.id_socio,
              self.fecha_recogida,
              self.fecha_devolucion,
              self.total_pagar,
          ),
      )
      id_alquiler = cursor.lastrowid
      conn.executemany(
          "INSERT INTO Alquiler_Pelicula (id_alquiler, id_pelicula) VALUES (?, ?)",
          [(id_alquiler, id_p) for id_p in self.ids_peliculas],
      )
      return id_alquiler

  @staticmethod
  def modificar_fecha_devolucion(id_alquiler, nueva_fecha_str, fecha_actual_str):
    f_nueva = _validar_fecha(nueva_fecha_str)
    f_actual = _validar_fecha(fecha_actual_str)

    if f_nueva <= f_actual:
      raise ValueError(
          "Error: The return date must be later than the current date."
      )

    with transaccion() as conn:
      cursor = conn.execute(
          "UPDATE Alquiler SET fecha_devolucion = ? WHERE id_alquiler = ?",
          (nueva_fecha_str, id_alquiler),
      )
      if cursor.rowcount == 0:
        raise ValueError(f"Error: Rental with ID {id_alquiler} does not exist.")


class Estadistica:
  """Amount spent by a member in one month (max. one per member and month)."""

  def __init__(self, id_socio, id_administrador, mes_anio, fecha_creacion):
    try:
      datetime.strptime(mes_anio, "%Y-%m")
    except (TypeError, ValueError) as exc:
      raise ValueError(
          f"Error: Invalid month '{mes_anio}', expected YYYY-MM."
      ) from exc
    _validar_fecha(fecha_creacion)
    self.id_socio = id_socio
    self.id_administrador = id_administrador
    self.mes_anio = mes_anio
    self.fecha_creacion = fecha_creacion
    self.total_gastado = self.calcular_total_gastado()

  def calcular_total_gastado(self):
    with closing(conectar()) as conn:
      if conn.execute(
          "SELECT 1 FROM Socio WHERE id_socio = ?", (self.id_socio,)
      ).fetchone() is None:
        raise ValueError(f"Error: Member with ID {self.id_socio} does not exist.")
      res = conn.execute(
          """SELECT SUM(total_pagar) FROM Alquiler
             WHERE id_socio = ? AND strftime('%Y-%m', fecha_recogida) = ?""",
          (self.id_socio, self.mes_anio),
      ).fetchone()
    return round(res[0], 2) if res[0] is not None else 0.0

  def guardar(self):
    try:
      with transaccion() as conn:
        cursor = conn.execute(
            """INSERT INTO Estadistica
                 (id_socio, id_administrador, mes_anio, fecha_creacion, total_gastado)
               VALUES (?, ?, ?, ?, ?)""",
            (
                self.id_socio,
                self.id_administrador,
                self.mes_anio,
                self.fecha_creacion,
                self.total_gastado,
            ),
        )
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
      if "UNIQUE" in str(exc):
        raise ValueError(
            "Error: A statistic record already exists for this member in this"
            " month."
        ) from exc
      raise


class Administrador:

  def __init__(self, nombre):
    self.nombre = nombre
    self.id_administrador = None

  def guardar(self):
    with transaccion() as conn:
      cursor = conn.execute(
          "INSERT INTO Administrador (nombre) VALUES (?)", (self.nombre,)
      )
      self.id_administrador = cursor.lastrowid
      return self.id_administrador

  @staticmethod
  def cargar(id_administrador):
    """Returns the saved administrator with that ID, or raises ValueError."""
    with closing(conectar()) as conn:
      res = conn.execute(
          "SELECT nombre FROM Administrador WHERE id_administrador = ?",
          (id_administrador,),
      ).fetchone()
    if res is None:
      raise ValueError(
          f"Error: Administrator with ID {id_administrador} does not exist."
      )
    admin = Administrador(res[0])
    admin.id_administrador = id_administrador
    return admin

  def generar_estadistica(self, id_socio, mes_anio, fecha_creacion):
    """Creates, saves and returns the statistic of a member for a month (YYYY-MM).

    Raises ValueError if the data is invalid or the statistic already exists.
    """
    if self.id_administrador is None:
      raise ValueError("Error: The administrator must be saved first.")
    estadistica = Estadistica(
        id_socio, self.id_administrador, mes_anio, fecha_creacion
    )
    estadistica.guardar()
    print(
        f"[{self.nombre}] Statistic generated for member {id_socio} in month"
        f" {mes_anio}. Total spent: {estadistica.total_gastado} €"
    )
    return estadistica


# ---------------------------------------------------------------------------
# Interactive console. All dates are typed by the user: the system date is
# never used, as required by the case study.
# ---------------------------------------------------------------------------


def pedir_texto(mensaje, obligatorio=True):
  while True:
    valor = input(mensaje).strip()
    if valor or not obligatorio:
      return valor or None
    print("  Este campo es obligatorio.")


def pedir_numero(mensaje, tipo=int):
  while True:
    try:
      return tipo(input(mensaje).strip().replace(",", "."))
    except ValueError:
      print("  Introduce un número válido.")


def pedir_fecha(mensaje):
  while True:
    valor = input(f"{mensaje} (YYYY-MM-DD): ").strip()
    try:
      _validar_fecha(valor)
      return valor
    except ValueError as e:
      print(f"  {e}")


def pedir_mes(mensaje):
  while True:
    valor = input(f"{mensaje} (YYYY-MM): ").strip()
    try:
      datetime.strptime(valor, "%Y-%m")
      return valor
    except ValueError:
      print("  Formato de mes no válido.")


CONSULTAS_LISTADO = {
    "Videoclub": "SELECT * FROM Videoclub",
    "Pelicula": "SELECT * FROM Pelicula",
    "Socio": "SELECT * FROM Socio",
    "Alquiler": "SELECT * FROM Alquiler",
    "Alquiler_Pelicula": "SELECT * FROM Alquiler_Pelicula",
    "Administrador": "SELECT * FROM Administrador",
    "Estadistica": "SELECT * FROM Estadistica",
}


def listar(tabla):
  with closing(conectar()) as conn:
    cursor = conn.execute(CONSULTAS_LISTADO[tabla])
    columnas = [d[0] for d in cursor.description]
    filas = cursor.fetchall()
  print(f"\n{tabla}: {len(filas)} registro(s)")
  print("  " + " | ".join(columnas))
  for fila in filas:
    print("  " + " | ".join("" if v is None else str(v) for v in fila))


def opcion_videoclub():
  v = Videoclub(
      pedir_texto("Nombre del gerente: "),
      pedir_texto("Ciudad: "),
      pedir_texto("Calle: "),
      pedir_texto("Código postal (5 caracteres): "),
  )
  print(f"Videoclub registrado con código {v.guardar()}.")


def opcion_pelicula():
  p = Pelicula(
      pedir_numero("Código del videoclub: "),
      pedir_texto("Nombre: "),
      pedir_texto("Director (opcional): ", obligatorio=False),
      pedir_fecha("Fecha de estreno"),
      pedir_numero("Precio de alquiler (€): ", float),
  )
  print(f"Película registrada con código {p.guardar()}.")


def opcion_socio():
  s = Socio(pedir_texto("Nombre: "), pedir_numero("Edad: "))
  print(f"Socio registrado con código {s.guardar()}.")


def opcion_alquiler():
  id_socio = pedir_numero("Código del socio: ")
  recogida = pedir_fecha("Fecha de recogida")
  devolucion = pedir_fecha("Fecha de devolución")
  texto = pedir_texto("Códigos de las películas, separados por comas: ")
  ids = [int(x) for x in texto.replace(" ", "").split(",") if x]
  a = Alquiler(id_socio, recogida, devolucion, ids)
  print(f"Alquiler registrado con código {a.guardar()}. Total a pagar: {a.total_pagar} €")


def opcion_modificar_devolucion():
  id_alquiler = pedir_numero("Código del alquiler: ")
  actual = pedir_fecha("Fecha actual")
  nueva = pedir_fecha("Nueva fecha de devolución")
  Alquiler.modificar_fecha_devolucion(id_alquiler, nueva, actual)
  print(f"Fecha de devolución actualizada a {nueva}.")


def opcion_administrador():
  a = Administrador(pedir_texto("Nombre: "))
  print(f"Administrador registrado con código {a.guardar()}.")


def opcion_estadistica():
  admin = Administrador.cargar(pedir_numero("Código del administrador: "))
  admin.generar_estadistica(
      pedir_numero("Código del socio: "),
      pedir_mes("Mes"),
      pedir_fecha("Fecha de creación"),
  )


def opcion_listar():
  for tabla in CONSULTAS_LISTADO:
    listar(tabla)


def opcion_ejemplo():
  """Loads the case-study example data; the dates are still typed by the user."""
  id_v = Videoclub("Carlos Pérez", "Madrid", "Calle Mayor 12", "28013").guardar()
  id_p1 = Pelicula(id_v, "Matrix", "Wachowski Sisters", "1999-03-31", 3.50).guardar()
  id_p2 = Pelicula(id_v, "Inception", "Christopher Nolan", "2010-07-16", 4.00).guardar()
  id_s = Socio("Ana Gómez", 25).guardar()
  print(f"Creados: videoclub {id_v}, películas {id_p1} y {id_p2}, socio {id_s}.")
  a = Alquiler(
      id_s,
      pedir_fecha("Fecha de recogida"),
      pedir_fecha("Fecha de devolución"),
      [id_p1, id_p2],
  )
  print(f"Alquiler {a.guardar()} registrado. Total a pagar: {a.total_pagar} €")


OPCIONES = {
    "1": ("Registrar videoclub", opcion_videoclub),
    "2": ("Registrar película", opcion_pelicula),
    "3": ("Registrar socio", opcion_socio),
    "4": ("Registrar alquiler", opcion_alquiler),
    "5": ("Modificar fecha de devolución", opcion_modificar_devolucion),
    "6": ("Registrar administrador", opcion_administrador),
    "7": ("Generar estadística mensual", opcion_estadistica),
    "8": ("Listar datos", opcion_listar),
    "9": ("Cargar datos de ejemplo", opcion_ejemplo),
}


def menu():
  inicializar_bd()
  while True:
    print("\n=== VIDEOCLUB APPV ===")
    for clave, (texto, _) in OPCIONES.items():
      print(f"{clave}. {texto}")
    print("0. Salir")
    eleccion = input("Opción: ").strip()
    if eleccion == "0":
      break
    if eleccion not in OPCIONES:
      print("Opción no válida.")
      continue
    try:
      OPCIONES[eleccion][1]()
    except (ValueError, sqlite3.IntegrityError) as e:
      print(f"No se ha podido completar la operación: {e}")


if __name__ == "__main__":
  menu()
