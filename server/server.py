import socket
import threading
import database

HOST = "0.0.0.0"
PORT = 3081
BUFFER_SIZE = 4096

clientes_conectados = []
lock_clientes = threading.Lock()


class Cliente:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.id_usuario = None
        self.username = ""
        self.id_foto_perfil = 1


def enviar_paquete(conn, texto):
    try:
        mensaje = texto + "\n"
        conn.sendall(mensaje.encode("utf-8"))
    except Exception as e:
        print(f"[Error al enviar]: {e}")


def reenviar_a_sala(miembros_ids, paquete):
    with lock_clientes:
        for c in clientes_conectados:
            if c.id_usuario in miembros_ids:
                enviar_paquete(c.conn, paquete)


def broadcast_usuarios_online():
    with lock_clientes:
        lista = [
            f"{c.id_usuario}:{c.username}:{c.id_foto_perfil}"
            for c in clientes_conectados if c.id_usuario is not None
        ]
        paquete = "ONLINE|" + ",".join(lista)
        for c in clientes_conectados:
            if c.id_usuario is not None:
                enviar_paquete(c.conn, paquete)


def desconectar_cliente(cliente):
    with lock_clientes:
        if cliente in clientes_conectados:
            clientes_conectados.remove(cliente)

    if cliente.id_usuario is not None:
        database.marcar_offline(cliente.id_usuario)
        broadcast_usuarios_online()

    try:
        cliente.conn.close()
    except:
        pass
    print(f"[-] Cliente desconectado: {cliente.addr} ({cliente.username})")


def procesar_comando(cliente, linea):
    partes = linea.split("|")
    accion = partes[0]

    if accion == "REGISTRO" and len(partes) >= 4:
        username, passwd = partes[1], partes[2]
        if not partes[3].isdigit() or not (1 <= int(partes[3]) <= 9):
            enviar_paquete(cliente.conn, "ERROR|Foto de perfil invalida (1-9)")
            return
        ok, msg = database.registrar_usuario(username, passwd, int(partes[3]))
        if ok:
            enviar_paquete(cliente.conn, f"REGISTRO_OK|{msg}")
        else:
            enviar_paquete(cliente.conn, f"ERROR|{msg}")

    elif accion == "LOGIN" and len(partes) >= 3:
        username, passwd = partes[1], partes[2]
        id_foto = int(partes[3]) if len(partes) >= 4 and partes[3].isdigit() else 1
        datos = database.validar_login(username, passwd, id_foto)
        if datos:
            cliente.id_usuario = datos["id_usuario"]
            cliente.username = datos["username"]
            cliente.id_foto_perfil = datos["id_foto_perfil"]
            enviar_paquete(cliente.conn, f"LOGIN_OK|{cliente.id_usuario}|{cliente.username}|{cliente.id_foto_perfil}")
            broadcast_usuarios_online()
        else:
            enviar_paquete(cliente.conn, "ERROR|Credenciales incorrectas")

    elif accion == "PRIVADO" and len(partes) >= 2 and cliente.id_usuario:
        id_destino = int(partes[1])
        id_sala = database.obtener_o_crear_privado(cliente.id_usuario, id_destino)
        if id_sala:
            enviar_paquete(cliente.conn, f"SALA_PRIVADA|{id_sala}|{id_destino}")
        else:
            enviar_paquete(cliente.conn, "ERROR|No se pudo abrir el chat privado")

    elif accion == "CREAR_GRUPO" and len(partes) >= 3 and cliente.id_usuario:
        nombre_grupo = partes[1]
        miembros = [int(x) for x in partes[2].split(",") if x.isdigit()]
        if cliente.id_usuario not in miembros:
            miembros.append(cliente.id_usuario)
        id_sala = database.crear_grupo(nombre_grupo, cliente.id_usuario, miembros)
        if id_sala:
            with lock_clientes:
                nombres = [c.username for c in clientes_conectados if c.id_usuario in miembros]
            nombres_csv = ",".join(nombres)
            reenviar_a_sala(miembros, f"NUEVO_GRUPO|{id_sala}|{nombre_grupo}|{nombres_csv}")
        else:
            enviar_paquete(cliente.conn, "ERROR|No se pudo crear el grupo")

    elif accion == "CREAR_CANAL" and len(partes) >= 2 and cliente.id_usuario:
        nombre_canal = partes[1]
        id_sala = database.crear_canal(nombre_canal, cliente.id_usuario)
        if id_sala:
            enviar_paquete(cliente.conn, f"CANAL_CREADO|{id_sala}|{nombre_canal}")
        else:
            enviar_paquete(cliente.conn, "ERROR|No se pudo crear el canal")

    elif accion == "UNIRSE_CANAL" and len(partes) >= 2 and cliente.id_usuario:
        id_sala = int(partes[1])
        nombre_canal = database.obtener_nombre_sala(id_sala)
        if nombre_canal and database.unirse_canal(id_sala, cliente.id_usuario):
            enviar_paquete(cliente.conn, f"UNIDO_CANAL|{id_sala}|{nombre_canal}")
        else:
            enviar_paquete(cliente.conn, "ERROR|No se pudo unir al canal")

    elif accion == "MSG_TEXTO" and len(partes) >= 3 and cliente.id_usuario:
        id_sala = int(partes[1])
        texto = "|".join(partes[2:])
        if not database.puede_escribir_en_sala(id_sala, cliente.id_usuario):
            enviar_paquete(cliente.conn, "ERROR|No tienes permiso para escribir en este canal")
            return

        database.guardar_mensaje_texto(id_sala, cliente.id_usuario, texto)
        paquete = f"NUEVO_MSG|{id_sala}|{cliente.id_usuario}|{cliente.username}|{cliente.id_foto_perfil}|TEXTO|{texto}"
        if id_sala == 1:
            with lock_clientes:
                for c in clientes_conectados:
                    if c.id_usuario is not None:
                        enviar_paquete(c.conn, paquete)
        else:
            miembros = database.obtener_miembros_sala(id_sala)
            reenviar_a_sala(miembros, paquete)

    elif accion == "MSG_STICKER" and len(partes) >= 3 and cliente.id_usuario:
        id_sala = int(partes[1])
        id_sticker = int(partes[2])
        if not (1 <= id_sticker <= 9):
            enviar_paquete(cliente.conn, "ERROR|Sticker invalido (1-9)")
            return
        if not database.puede_escribir_en_sala(id_sala, cliente.id_usuario):
            enviar_paquete(cliente.conn, "ERROR|No tienes permiso para enviar stickers en este canal")
            return

        database.guardar_mensaje_sticker(id_sala, cliente.id_usuario, id_sticker)
        paquete = f"NUEVO_MSG|{id_sala}|{cliente.id_usuario}|{cliente.username}|{cliente.id_foto_perfil}|STICKER|{id_sticker}"
        if id_sala == 1:
            with lock_clientes:
                for c in clientes_conectados:
                    if c.id_usuario is not None:
                        enviar_paquete(c.conn, paquete)
        else:
            miembros = database.obtener_miembros_sala(id_sala)
            reenviar_a_sala(miembros, paquete)

    elif accion == "LISTAR_CANALES":
        canales = database.listar_canales()
        texto = ",".join(f"{cid}:{nombre}" for cid, nombre in canales)
        enviar_paquete(cliente.conn, f"LISTA_CANALES|{texto}")

    elif accion == "HISTORIAL_GRUPO" and len(partes) >= 2 and cliente.id_usuario:
        id_sala = int(partes[1])
        enviar_paquete(cliente.conn, f"HISTORIAL_INICIO|{id_sala}")
        for msg in database.obtener_historial_sala(id_sala):
            enviar_paquete(cliente.conn, f"HISTORIAL_MSG|{msg}")
        enviar_paquete(cliente.conn, f"HISTORIAL_FIN|{id_sala}")

    elif accion == "HISTORIAL_CANAL" and len(partes) >= 2 and cliente.id_usuario:
        id_sala = int(partes[1])
        enviar_paquete(cliente.conn, f"HISTORIAL_CANAL_INICIO|{id_sala}")
        for msg in database.obtener_historial_sala(id_sala):
            enviar_paquete(cliente.conn, f"HISTORIAL_CANAL_MSG|{msg}")
        enviar_paquete(cliente.conn, f"HISTORIAL_CANAL_FIN|{id_sala}")

    else:
        enviar_paquete(cliente.conn, "ERROR|Comando no reconocido o sesion no iniciada")


def client_thread(cliente):
    buffer = ""
    try:
        while True:
            datos = cliente.conn.recv(BUFFER_SIZE)
            if not datos:
                break

            buffer += datos.decode("utf-8")
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                if linea.strip():
                    procesar_comando(cliente, linea.strip())
    except (ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        print(f"[Error en hilo de {cliente.addr}]: {e}")
    finally:
        desconectar_cliente(cliente)


if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(100)
    print(f"[*] Servidor escuchando en {HOST}:{PORT}...")

    try:
        while True:
            conn, addr = server.accept()
            nuevo_cliente = Cliente(conn, addr)
            with lock_clientes:
                clientes_conectados.append(nuevo_cliente)
            print(f"[+] Nueva conexion desde {addr}")
            threading.Thread(target=client_thread, args=(nuevo_cliente,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[!] Apagando servidor...")
    finally:
        server.close()