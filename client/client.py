import socket
import threading

SERVER_IP = "3.149.102.2"
SERVER_PORT = 3081
BUFFER_SIZE = 4096


class ClienteSocket:
    def __init__(self, host=SERVER_IP, port=SERVER_PORT, callback_mensaje=None):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conectado = False
        self.callback_mensaje = callback_mensaje

        self.id_usuario = None
        self.username = ""
        self.id_foto_perfil = 1

    def conectar(self):
        """Establece la conexión TCP con el servidor y arranca el hilo receptor."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.conectado = True
            hilo_escucha = threading.Thread(target=self._escuchar_servidor, daemon=True)
            hilo_escucha.start()
            return True, "Conectado al servidor"
        except Exception as e:
            self.conectado = False
            return False, f"No se pudo conectar: {e}"

    def _enviar(self, paquete):
        """Envía una cadena terminada en salto de línea por el socket."""
        if not self.conectado:
            return
        try:
            self.sock.sendall((paquete + "\n").encode("utf-8"))
        except Exception as e:
            print(f"[Error enviando datos]: {e}")
            self.desconectar()

    def _escuchar_servidor(self):
        """Hilo en segundo plano que lee continuamente las respuestas del servidor."""
        buffer = ""
        while self.conectado:
            try:
                datos = self.sock.recv(BUFFER_SIZE)
                if not datos:
                    break

                buffer += datos.decode("utf-8")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    linea = linea.strip()
                    if linea:
                        self._procesar_respuesta(linea)
            except Exception as e:
                if self.conectado:
                    print(f"[Error de lectura]: {e}")
                break

        self.desconectar()

    def _procesar_respuesta(self, linea):
        """Actualiza estado interno del cliente y pasa el evento a la interfaz."""
        partes = linea.split("|")
        accion = partes[0]

        if accion == "LOGIN_OK" and len(partes) >= 4:
            self.id_usuario = int(partes[1])
            self.username = partes[2]
            self.id_foto_perfil = int(partes[3])

        if self.callback_mensaje:
            self.callback_mensaje(linea)
        else:
            print(f"\n[SERVIDOR] -> {linea}")

    # ==========================================
    # MÉTODOS DE PROTOCOLO (Para interface.py)
    # ==========================================
    def registrar(self, username, passwd, id_foto_perfil):
        self._enviar(f"REGISTRO|{username}|{passwd}|{id_foto_perfil}")

    def login(self, username, passwd, id_foto_perfil=1):
        self._enviar(f"LOGIN|{username}|{passwd}|{id_foto_perfil}")

    def abrir_privado(self, id_destino):
        self._enviar(f"PRIVADO|{id_destino}")

    def crear_grupo(self, nombre_grupo, lista_ids_miembros):
        ids_str = ",".join(str(uid) for uid in lista_ids_miembros)
        self._enviar(f"CREAR_GRUPO|{nombre_grupo}|{ids_str}")

    def solicitar_historial_grupo(self, id_sala):
        self._enviar(f"HISTORIAL_GRUPO|{id_sala}")

    def crear_canal(self, nombre_canal):
        self._enviar(f"CREAR_CANAL|{nombre_canal}")

    def listar_canales(self):
        self._enviar("LISTAR_CANALES")

    def solicitar_historial_canal(self, id_sala):
        self._enviar(f"HISTORIAL_CANAL|{id_sala}")

    def unirse_canal(self, id_sala):
        self._enviar(f"UNIRSE_CANAL|{id_sala}")

    def enviar_texto(self, id_sala, texto):
        self._enviar(f"MSG_TEXTO|{id_sala}|{texto}")

    def enviar_sticker(self, id_sala, id_sticker):
        self._enviar(f"MSG_STICKER|{id_sala}|{id_sticker}")

    def desconectar(self):
        self.conectado = False
        try:
            self.sock.close()
        except:
            pass


if __name__ == "__main__":
    cliente = ClienteSocket(host=SERVER_IP, port=SERVER_PORT)
    exito, msg = cliente.conectar()
    print(f"[*] {msg}")

    if exito:
        print("Comandos de prueba: LOGIN|Isaac|1234|1  o  MSG_TEXTO|1|Hola  (escribe 'salir' para cerrar)\n")
        while cliente.conectado:
            comando = input()
            if comando.lower() == "salir":
                break
            cliente._enviar(comando)
        cliente.desconectar()