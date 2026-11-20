CREATE TABLE IF NOT EXISTS Videoclub (
    id_videoclub INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_gerente TEXT NOT NULL,
    ciudad TEXT NOT NULL,
    calle TEXT NOT NULL,
    codigo_postal TEXT NOT NULL CHECK (length(codigo_postal) = 5)
);

CREATE TABLE IF NOT EXISTS Pelicula (
    id_pelicula INTEGER PRIMARY KEY AUTOINCREMENT,
    id_videoclub INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    director TEXT,
    fecha_estreno TEXT NOT NULL,
    precio_alquiler REAL NOT NULL,
    FOREIGN KEY (id_videoclub) REFERENCES Videoclub(id_videoclub)
);

CREATE TABLE IF NOT EXISTS Socio (
    id_socio INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    edad INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS Alquiler (
    id_alquiler INTEGER PRIMARY KEY AUTOINCREMENT,
    id_socio INTEGER NOT NULL,
    fecha_recogida TEXT NOT NULL,     
    fecha_devolucion TEXT NOT NULL,   
    total_pagar REAL NOT NULL,        
    FOREIGN KEY (id_socio) REFERENCES Socio(id_socio)
);

CREATE TABLE IF NOT EXISTS Alquiler_Pelicula (
    id_alquiler INTEGER NOT NULL,
    id_pelicula INTEGER NOT NULL,
    PRIMARY KEY (id_alquiler, id_pelicula),
    FOREIGN KEY (id_alquiler) REFERENCES Alquiler(id_alquiler) ON DELETE CASCADE,
    FOREIGN KEY (id_pelicula) REFERENCES Pelicula(id_pelicula)
);

CREATE TABLE IF NOT EXISTS Administrador (
    id_administrador INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Estadistica (
    id_estadistica INTEGER PRIMARY KEY AUTOINCREMENT,
    id_socio INTEGER NOT NULL,
    id_administrador INTEGER NOT NULL,
    mes_anio TEXT NOT NULL,           
    fecha_creacion TEXT NOT NULL,     
    total_gastado REAL NOT NULL,      
    FOREIGN KEY (id_socio) REFERENCES Socio(id_socio),
    FOREIGN KEY (id_administrador) REFERENCES Administrador(id_administrador),
    CONSTRAINT uk_socio_mes UNIQUE (id_socio, mes_anio)
);
