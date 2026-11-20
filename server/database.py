import pyodbc

DB_CONFIG = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=minioms;"
    "UID=miniom1;"
    "PWD=Minioms1*;"
    "TrustServerCertificate=yes;"
)


def obtener_conexion():
    return pyodbc.connect(DB_CONFIG)


def registrar_usuario(username, passwd, id_foto_perfil):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Usuarios (username, passwd, en_linea, id_foto_perfil) VALUES (?, ?, 0, ?)",
                (username, passwd, id_foto_perfil),
            )
            conn.commit()
            return True, "Usuario registrado correctamente"
    except pyodbc.IntegrityError:
        return False, "El nombre de usuario ya existe"
    except Exception as e:
        return False, f"Error BD: {e}"


def validar_login(username, passwd, id_foto_perfil=1):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_usuario, username, passwd, id_foto_perfil FROM Usuarios WHERE username = ?",
                (username,),
            )
            fila = cursor.fetchone()

            if fila:
                if fila.passwd != passwd:
                    return None
                cursor.execute(
                    "UPDATE Usuarios SET en_linea = 1, id_foto_perfil = ? WHERE id_usuario = ?",
                    (id_foto_perfil, fila.id_usuario),
                )
                conn.commit()
                return {
                    "id_usuario": fila.id_usuario,
                    "username": fila.username,
                    "id_foto_perfil": id_foto_perfil,
                }
            else:
                cursor.execute(
                    """
                    INSERT INTO Usuarios (username, passwd, en_linea, id_foto_perfil)
                    OUTPUT INSERTED.id_usuario
                    VALUES (?, ?, 1, ?)
                    """,
                    (username, passwd, id_foto_perfil),
                )
                nuevo_id = cursor.fetchone()[0]
                conn.commit()
                return {
                    "id_usuario": nuevo_id,
                    "username": username,
                    "id_foto_perfil": id_foto_perfil,
                }
    except Exception as e:
        print(f"[Error validar_login]: {e}")
        return None


def marcar_offline(id_usuario):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Usuarios SET en_linea = 0 WHERE id_usuario = ?", (id_usuario,))
            conn.commit()
    except Exception as e:
        print(f"[Error marcar_offline]: {e}")


def obtener_o_crear_privado(id_usuario1, id_usuario2):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.id_sala
                FROM Salas_chat s
                JOIN Miembros_sala m1 ON s.id_sala = m1.id_sala AND m1.id_usuario = ?
                JOIN Miembros_sala m2 ON s.id_sala = m2.id_sala AND m2.id_usuario = ?
                WHERE s.tipo_sala = 'PRIVADO'
                """,
                (id_usuario1, id_usuario2),
            )
            fila = cursor.fetchone()
            if fila:
                return fila.id_sala

            cursor.execute(
                "INSERT INTO Salas_chat (nombre, tipo_sala, id_creador) OUTPUT INSERTED.id_sala VALUES (NULL, 'PRIVADO', ?)",
                (id_usuario1,),
            )
            id_sala = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Miembros_sala (id_sala, id_usuario, rol) VALUES (?, ?, 2)", (id_sala, id_usuario1))
            if id_usuario1 != id_usuario2:
                cursor.execute("INSERT INTO Miembros_sala (id_sala, id_usuario, rol) VALUES (?, ?, 2)", (id_sala, id_usuario2))
            conn.commit()
            return id_sala
    except Exception as e:
        print(f"[Error obtener_o_crear_privado]: {e}")
        return None


def crear_grupo(nombre_grupo, id_creador, miembros_ids):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Salas_chat (nombre, tipo_sala, id_creador) OUTPUT INSERTED.id_sala VALUES (?, 'GRUPO', ?)",
                (nombre_grupo, id_creador),
            )
            id_sala = cursor.fetchone()[0]
            for uid in set(miembros_ids):
                rol = 1 if uid == id_creador else 2
                cursor.execute("INSERT INTO Miembros_sala (id_sala, id_usuario, rol) VALUES (?, ?, ?)", (id_sala, uid, rol))
            conn.commit()
            return id_sala
    except Exception as e:
        print(f"[Error crear_grupo]: {e}")
        return None


def crear_canal(nombre_canal, id_creador):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Salas_chat (nombre, tipo_sala, id_creador) OUTPUT INSERTED.id_sala VALUES (?, 'CANAL', ?)",
                (nombre_canal, id_creador),
            )
            id_sala = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Miembros_sala (id_sala, id_usuario, rol) VALUES (?, ?, 1)", (id_sala, id_creador))
            conn.commit()
            return id_sala
    except Exception as e:
        print(f"[Error crear_canal]: {e}")
        return None


def unirse_canal(id_sala, id_usuario):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM Miembros_sala WHERE id_sala = ? AND id_usuario = ?)
                INSERT INTO Miembros_sala (id_sala, id_usuario, rol) VALUES (?, ?, 2)
                """,
                (id_sala, id_usuario, id_sala, id_usuario),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"[Error unirse_canal]: {e}")
        return False


def puede_escribir_en_sala(id_sala, id_usuario):
    if id_sala == 1:
        return True
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT s.tipo_sala, m.rol
                FROM Salas_chat s
                JOIN Miembros_sala m ON s.id_sala = m.id_sala
                WHERE s.id_sala = ? AND m.id_usuario = ?
                """,
                (id_sala, id_usuario),
            )
            fila = cursor.fetchone()
            if not fila:
                return False
            if fila.tipo_sala == "CANAL" and fila.rol != 1:
                return False
            return True
    except Exception as e:
        print(f"[Error puede_escribir_en_sala]: {e}")
        return False


def obtener_miembros_sala(id_sala):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_usuario FROM Miembros_sala WHERE id_sala = ?", (id_sala,))
            return [fila.id_usuario for fila in cursor.fetchall()]
    except Exception as e:
        print(f"[Error obtener_miembros_sala]: {e}")
        return []


def guardar_mensaje_texto(id_sala, id_remitente, contenido_texto):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Mensajes (contenido_texto, id_remitente, id_sticker, id_sala) VALUES (?, ?, NULL, ?)",
                (contenido_texto, id_remitente, id_sala),
            )
            conn.commit()
    except Exception as e:
        print(f"[Error guardar_mensaje_texto]: {e}")


def guardar_mensaje_sticker(id_sala, id_remitente, id_sticker):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Mensajes (contenido_texto, id_remitente, id_sticker, id_sala) VALUES (NULL, ?, ?, ?)",
                (id_remitente, id_sticker, id_sala),
            )
            conn.commit()
    except Exception as e:
        print(f"[Error guardar_mensaje_sticker]: {e}")


def listar_canales():
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_sala, nombre FROM Salas_chat WHERE tipo_sala = 'CANAL'")
            return [(fila.id_sala, fila.nombre) for fila in cursor.fetchall()]
    except Exception as e:
        print(f"[Error listar_canales]: {e}")
        return []


def obtener_historial_sala(id_sala):
    """Devuelve los mensajes guardados en formato compatible con NUEVO_MSG."""
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.id_sala, m.id_remitente, u.username, u.id_foto_perfil,
                       m.contenido_texto, m.id_sticker
                FROM Mensajes m
                JOIN Usuarios u ON m.id_remitente = u.id_usuario
                WHERE m.id_sala = ?
                ORDER BY m.fecha_envio ASC
                """,
                (id_sala,),
            )
            historial = []
            for f in cursor.fetchall():
                if f.contenido_texto is not None:
                    historial.append(f"NUEVO_MSG|{f.id_sala}|{f.id_remitente}|{f.username}|{f.id_foto_perfil}|TEXTO|{f.contenido_texto}")
                elif f.id_sticker is not None:
                    historial.append(f"NUEVO_MSG|{f.id_sala}|{f.id_remitente}|{f.username}|{f.id_foto_perfil}|STICKER|{f.id_sticker}")
            return historial
    except Exception as e:
        print(f"[Error obtener_historial_sala]: {e}")
        return []


def obtener_nombre_sala(id_sala):
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nombre FROM Salas_chat WHERE id_sala = ?", (id_sala,))
            fila = cursor.fetchone()
            return fila.nombre if fila else None
    except Exception as e:
        print(f"[Error obtener_nombre_sala]: {e}")
        return None