"""
Módulo de acceso y persistencia de datos para el sistema distribuido Minioms.

Gestiona las conexiones hacia Microsoft SQL Server mediante pyodbc y ejecuta
consultas parametrizadas para la autenticación y auto-registro de usuarios,
creación de salas (privadas, grupos y canales), control de permisos y
almacenamiento/recuperación del historial de mensajes.
"""

import pyodbc

# Cadena de conexión ODBC hacia la instancia local de SQL Server en AWS
DB_CONFIG = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=minioms;"
    "UID=miniom1;"
    "PWD=Minioms1*;"
    "TrustServerCertificate=yes;"
)


def obtener_conexion():
    """Establece y devuelve una conexión activa hacia la base de datos SQL Server."""
    return pyodbc.connect(DB_CONFIG)


def registrar_usuario(username, passwd, id_foto_perfil):
    """
    Registra un nuevo usuario en la tabla Usuarios.

    Args:
        username (str): Nombre de usuario único.
        passwd (str): Contraseña de acceso.
        id_foto_perfil (int): Identificador del avatar seleccionado (1-9).

    Returns:
        tuple[bool, str]: Tupla (éxito, mensaje descriptivo).
    """
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
    """
    Valida las credenciales de inicio de sesión o auto-registra usuarios nuevos.

    Si el usuario existe en la base de datos, verifica su contraseña, actualiza
    su estado en línea y su avatar. Si no existe, lo inserta automáticamente
    para permitir el acceso inmediato al sistema.

    Args:
        username (str): Nombre de usuario.
        passwd (str): Contraseña ingresada.
        id_foto_perfil (int, optional): Avatar elegido (1-9). Por defecto 1.

    Returns:
        dict | None: Diccionario con 'id_usuario', 'username' e 'id_foto_perfil'
                     si la autenticación es exitosa, o None si la contraseña falla.
    """
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id_usuario, username, passwd, id_foto_perfil FROM Usuarios WHERE username = ?",
                (username,),
            )
            fila = cursor.fetchone()

            if fila:
                # Usuario existente: verificar coincidencia de contraseña
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
                # Usuario nuevo: registro automático con estado activo
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
    """Actualiza el estado de conexión del usuario a desconectado (en_linea = 0)."""
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Usuarios SET en_linea = 0 WHERE id_usuario = ?", (id_usuario,))
            conn.commit()
    except Exception as e:
        print(f"[Error marcar_offline]: {e}")


def obtener_o_crear_privado(id_usuario1, id_usuario2):
    """
    Busca una sala privada existente entre dos usuarios o crea una nueva.

    Args:
        id_usuario1 (int): ID del usuario solicitante.
        id_usuario2 (int): ID del usuario destinatario.

    Returns:
        int | None: ID de la sala privada en Salas_chat, o None ante error.
    """
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

            # Crear nueva sala privada y registrar ambos participantes con rol estándar (2)
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
    """
    Crea una sala grupal y asocia a sus integrantes en Miembros_sala.

    El creador recibe rol de administrador (1) y los demás integrantes rol (2).

    Returns:
        int | None: ID de la nueva sala grupal, o None ante error.
    """
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
    """
    Crea un canal de difusión unidireccional asignando rol de creador (1) al dueño.

    Returns:
        int | None: ID del canal creado, o None ante error.
    """
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
    """Suscribe a un usuario como lector (rol = 2) dentro de un canal existente."""
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
    """
    Verifica si un usuario tiene permisos de escritura en una sala determinada.

    En el Chat General (id_sala = 1) todos pueden escribir. En salas de tipo
    'CANAL', únicamente el creador (rol = 1) tiene permiso de publicación.

    Returns:
        bool: True si está autorizado para enviar mensajes, False en caso contrario.
    """
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
    """Devuelve una lista con los IDs de todos los usuarios pertenecientes a una sala."""
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_usuario FROM Miembros_sala WHERE id_sala = ?", (id_sala,))
            return [fila.id_usuario for fila in cursor.fetchall()]
    except Exception as e:
        print(f"[Error obtener_miembros_sala]: {e}")
        return []


def guardar_mensaje_texto(id_sala, id_remitente, contenido_texto):
    """Inserta un mensaje de texto plano en la tabla Mensajes."""
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
    """Inserta un mensaje de tipo sticker (1-9) en la tabla Mensajes."""
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
    """Retorna una lista de tuplas (id_sala, nombre) de todos los canales disponibles."""
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_sala, nombre FROM Salas_chat WHERE tipo_sala = 'CANAL'")
            return [(fila.id_sala, fila.nombre) for fila in cursor.fetchall()]
    except Exception as e:
        print(f"[Error listar_canales]: {e}")
        return []


def obtener_historial_sala(id_sala):
    """
    Recupera todos los mensajes almacenados de una sala ordenados cronológicamente.

    Returns:
        list[str]: Lista de paquetes formateados según el protocolo NUEVO_MSG.
    """
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
    """Consulta y devuelve el nombre de una sala a partir de su identificador."""
    try:
        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nombre FROM Salas_chat WHERE id_sala = ?", (id_sala,))
            fila = cursor.fetchone()
            return fila.nombre if fila else None
    except Exception as e:
        print(f"[Error obtener_nombre_sala]: {e}")
        return None