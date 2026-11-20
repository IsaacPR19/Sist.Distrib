import customtkinter as ctk
from PIL import Image
from pathlib import Path
from client import ClienteSocket
import queue

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CARPETA_AVATARS = Path(__file__).resolve().parent.parent / "assets" / "avatars"


def cargar_foto(id_foto, tamano=(65, 65)):
    for extension in (".png", ".jpg", ".jpeg"):
        ruta = CARPETA_AVATARS / f"perfil{id_foto}{extension}"

        if ruta.is_file():
            with Image.open(ruta) as archivo:
                imagen = archivo.convert("RGBA")

            return ctk.CTkImage(
                light_image=imagen,
                dark_image=imagen,
                size=tamano
            )

    return None


class Wasap(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Wasap - Sistemas Distribuidos")
        self.geometry("500x760")
        self.minsize(480, 700)

        self.usuario = ""
        self.foto = 1
        self.seccion_actual = "login"

        self.usuarios_online = []
        self.ids_usuarios = {}
        self.salas_privadas = {}

        self.grupos = []
        self.canales = []
        self.canal_actual_id = None
        self.grupo_actual_id = None
        self.mensajes_general = []
        self.mensajes_privados = {}
        self.usuario_destino = None

        self.imagenes_perfil = []
        self.imagen_usuario = None
        self.caja_general = None

        self.cola_mensajes = queue.Queue()

        self.cliente = ClienteSocket(
            host="3.149.102.2",
            port=3081,
            callback_mensaje=self.recibir_paquete
        )

        self.after(100, self.revisar_mensajes)
        self.protocol("WM_DELETE_WINDOW", self.cerrar_programa)

        self.mostrar_login()

    # ========================================================
    # FUNCIONES GENERALES
    # ========================================================
    def limpiar(self):
        for widget in self.winfo_children():
            widget.destroy()

    def limpiar_contenido(self):
        for widget in self.contenido.winfo_children():
            widget.destroy()

        self.caja_general = None

    def titulo_seccion(self, texto):
        ctk.CTkLabel(
            self.contenido,
            text=texto,
            font=("Arial", 24, "bold")
        ).pack(pady=20)

    def agregar_mensaje(self, caja, texto):
        caja.configure(state="normal")
        caja.insert("end", texto + "\n\n")
        caja.configure(state="disabled")
        caja.see("end")

    # ========================================================
    # COMUNICACIÓN CON EL SERVIDOR
    # ========================================================
    def recibir_paquete(self, paquete):
        self.cola_mensajes.put(paquete)

    def revisar_mensajes(self):
        while not self.cola_mensajes.empty():
            paquete = self.cola_mensajes.get()
            print("[SERVIDOR]", paquete)

            if paquete.startswith("LOGIN_OK|"):
                partes = paquete.split("|")
                if len(partes) >= 4:
                    self.usuario = partes[2]
                    self.foto = int(partes[3])
                    self.mostrar_principal()

            elif paquete.startswith("ERROR|"):
                mensaje = paquete.split("|", 1)[1]
                if self.seccion_actual == "login":
                    self.error_login.configure(text=mensaje, text_color="red")
                    self.boton_conectar.configure(state="normal")

            elif paquete.startswith("ONLINE|"):
                datos = paquete.split("|", 1)[1]
                usuarios = []
                ids_usuarios = {}

                if datos:
                    for elemento in datos.split(","):
                        partes = elemento.split(":")
                        if len(partes) >= 3:
                            id_usuario = int(partes[0])
                            nombre = partes[1]
                            if id_usuario != self.cliente.id_usuario:
                                usuarios.append(nombre)
                                ids_usuarios[nombre] = id_usuario

                self.usuarios_online = usuarios
                self.ids_usuarios = ids_usuarios

            elif paquete.startswith("SALA_PRIVADA|"):
                partes = paquete.split("|")
                if len(partes) >= 3:
                    id_sala = int(partes[1])
                    id_destino = int(partes[2])
                    for nombre, id_usuario in self.ids_usuarios.items():
                        if id_usuario == id_destino:
                            self.salas_privadas[nombre] = id_sala
                            break

            elif paquete.startswith("NUEVO_GRUPO|"):
                partes = paquete.split("|", 3)
                if len(partes) >= 4:
                    id_sala = int(partes[1])
                    nombre_grupo = partes[2]
                    integrantes = partes[3].split(",") if partes[3] else []

                    if not any(g["id_sala"] == id_sala for g in self.grupos):
                        self.grupos.append({
                            "id_sala": id_sala,
                            "nombre": nombre_grupo,
                            "miembros": integrantes,
                            "mensajes": []
                        })

                    if self.seccion_actual == "grupos":
                        self.mostrar_grupos()

            elif paquete.startswith("CANAL_CREADO|"):
                partes = paquete.split("|", 2)
                if len(partes) == 3:
                    id_sala = int(partes[1])
                    nombre = partes[2]
                    canal = next((c for c in self.canales if c["id_sala"] == id_sala), None)

                    if canal is None:
                        self.canales.append({
                            "id_sala": id_sala,
                            "nombre": nombre,
                            "mensajes": [],
                            "dueno": True,
                            "unido": True
                        })
                    else:
                        canal["dueno"] = True
                        canal["unido"] = True

                    if self.seccion_actual == "canales":
                        self.mostrar_canales(actualizar=False)

            elif paquete.startswith("UNIDO_CANAL|"):
                partes = paquete.split("|", 2)
                if len(partes) == 3:
                    id_sala = int(partes[1])
                    nombre = partes[2]
                    canal = next((c for c in self.canales if c["id_sala"] == id_sala), None)

                    if canal is None:
                        canal = {
                            "id_sala": id_sala,
                            "nombre": nombre,
                            "mensajes": [],
                            "dueno": False,
                            "unido": True
                        }
                        self.canales.append(canal)
                    else:
                        canal["unido"] = True

                    self.cliente.solicitar_historial_canal(id_sala)

                    if self.seccion_actual == "canal_abierto" and self.canal_actual_id == id_sala:
                        self.abrir_canal(canal)

            elif paquete.startswith("LISTA_CANALES|"):
                datos = paquete.split("|", 1)[1]
                canales_anteriores = {c["id_sala"]: c for c in self.canales}
                self.canales = []

                if datos:
                    for elemento in datos.split(","):
                        if ":" in elemento:
                            id_texto, nombre = elemento.split(":", 1)
                            id_sala = int(id_texto)
                            canal = canales_anteriores.get(id_sala, {
                                "id_sala": id_sala,
                                "nombre": nombre,
                                "mensajes": [],
                                "dueno": False,
                                "unido": False
                            })
                            canal["nombre"] = nombre
                            self.canales.append(canal)

                if self.seccion_actual == "canales":
                    self.mostrar_canales(actualizar=False)

            elif paquete.startswith("HISTORIAL_CANAL_INICIO|"):
                id_sala = int(paquete.split("|")[1])
                self.historiales_canales_pendientes = getattr(self, "historiales_canales_pendientes", {})
                self.historiales_canales_pendientes[id_sala] = []

            elif paquete.startswith("HISTORIAL_CANAL_MSG|"):
                mensaje_original = paquete.split("|", 1)[1]
                partes = mensaje_original.split("|", 6)
                if len(partes) >= 7 and partes[0] == "NUEVO_MSG":
                    id_sala = int(partes[1])
                    nombre = partes[3]
                    tipo = partes[5]
                    contenido = partes[6]
                    if tipo == "TEXTO" and id_sala in getattr(self, "historiales_canales_pendientes", {}):
                        self.historiales_canales_pendientes[id_sala].append(f"{nombre}: {contenido}")

            elif paquete.startswith("HISTORIAL_CANAL_FIN|"):
                id_sala = int(paquete.split("|")[1])
                canal = next((c for c in self.canales if c.get("id_sala") == id_sala), None)
                historial = getattr(self, "historiales_canales_pendientes", {}).pop(id_sala, None)

                if canal is not None and historial is not None:
                    canal["mensajes"] = historial
                    if self.seccion_actual == "canal_abierto" and self.canal_actual_id == id_sala:
                        self.abrir_canal(canal)

            elif paquete.startswith("HISTORIAL_INICIO|"):
                id_sala = int(paquete.split("|")[1])
                self.historiales_pendientes = getattr(self, "historiales_pendientes", {})
                self.historiales_pendientes[id_sala] = []

            elif paquete.startswith("HISTORIAL_MSG|"):
                mensaje_original = paquete.split("|", 1)[1]
                partes = mensaje_original.split("|", 6)
                if len(partes) >= 7 and partes[0] == "NUEVO_MSG":
                    id_sala = int(partes[1])
                    nombre = partes[3]
                    tipo = partes[5]
                    contenido = partes[6]
                    if tipo == "TEXTO" and id_sala in getattr(self, "historiales_pendientes", {}):
                        self.historiales_pendientes[id_sala].append(f"{nombre}: {contenido}")

            elif paquete.startswith("HISTORIAL_FIN|"):
                id_sala = int(paquete.split("|")[1])
                grupo = next((g for g in self.grupos if g.get("id_sala") == id_sala), None)
                historial = getattr(self, "historiales_pendientes", {}).pop(id_sala, None)

                if grupo is not None and historial is not None:
                    grupo["mensajes"] = historial
                    if self.seccion_actual == "grupo_abierto" and self.grupo_actual_id == id_sala:
                        self.abrir_chat_grupo(grupo, solicitar_historial=False)

            elif paquete.startswith("NUEVO_MSG|"):
                partes = paquete.split("|", 6)
                if len(partes) >= 7:
                    id_sala = int(partes[1])
                    id_remitente = int(partes[2])
                    nombre = partes[3]
                    tipo = partes[5]
                    contenido = partes[6]

                    if tipo == "TEXTO":
                        mensaje = f"{nombre}: {contenido}"

                        # 1. CHAT GENERAL
                        if id_sala == 1:
                            self.mensajes_general.append(mensaje)
                            if self.seccion_actual == "general" and self.caja_general is not None:
                                self.agregar_mensaje(self.caja_general, mensaje)

                        # 2. GRUPOS
                        elif any(g.get("id_sala") == id_sala for g in self.grupos):
                            grupo_recibido = next(g for g in self.grupos if g.get("id_sala") == id_sala)
                            grupo_recibido["mensajes"].append(mensaje)
                            if self.seccion_actual == "grupo_abierto" and self.grupo_actual_id == id_sala:
                                self.abrir_chat_grupo(grupo_recibido, solicitar_historial=False)

                        # 3. CANALES
                        elif any(c.get("id_sala") == id_sala for c in self.canales):
                            canal_recibido = next(c for c in self.canales if c.get("id_sala") == id_sala)
                            canal_recibido["mensajes"].append(mensaje)
                            if self.seccion_actual == "canal_abierto" and self.canal_actual_id == id_sala:
                                self.abrir_canal(canal_recibido)

                        # 4. MENSAJES PRIVADOS
                        else:
                            if id_remitente == self.cliente.id_usuario:
                                destinatario = next((u for u, sala in self.salas_privadas.items() if sala == id_sala), None)
                            else:
                                destinatario = next((u for u, uid in self.ids_usuarios.items() if uid == id_remitente), None)

                            if destinatario is not None:
                                self.salas_privadas[destinatario] = id_sala
                                self.mensajes_privados.setdefault(destinatario, []).append(mensaje)
                                if self.seccion_actual == "privados" and self.usuario_destino == destinatario:
                                    self.actualizar_privados()

        self.after(100, self.revisar_mensajes)

    def cerrar_programa(self):
        self.cliente.desconectar()
        self.destroy()

    # ========================================================
    # INICIO DE SESIÓN
    # ========================================================
    def mostrar_login(self):
        self.seccion_actual = "login"
        self.limpiar()

        self.geometry("500x760")
        self.title("Wasap - Iniciar sesión")

        ctk.CTkLabel(self, text="Wasap", font=("Arial", 32, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="Inicia sesión para continuar").pack(pady=5)

        self.entrada_usuario = ctk.CTkEntry(self, placeholder_text="Nombre de usuario", width=300, height=40)
        self.entrada_usuario.pack(pady=10)

        self.entrada_password = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*", width=300, height=40)
        self.entrada_password.pack(pady=10)

        ctk.CTkLabel(self, text="Selecciona tu foto de perfil", font=("Arial", 16, "bold")).pack(pady=(15, 5))

        self.foto_seleccionada = ctk.IntVar(value=1)
        marco_fotos = ctk.CTkFrame(self)
        marco_fotos.pack(pady=10)

        self.imagenes_perfil = []

        for numero in range(1, 10):
            imagen = cargar_foto(numero, (65, 65))
            self.imagenes_perfil.append(imagen)

            fila = (numero - 1) // 3
            columna = (numero - 1) % 3

            contenedor = ctk.CTkFrame(marco_fotos)
            contenedor.grid(row=fila, column=columna, padx=6, pady=6)

            if imagen is not None:
                ctk.CTkLabel(contenedor, text="", image=imagen).pack(pady=5)
            else:
                ctk.CTkLabel(contenedor, text=f"Sin foto {numero}").pack(pady=10)

            ctk.CTkRadioButton(
                contenedor,
                text=f"Foto {numero}",
                variable=self.foto_seleccionada,
                value=numero,
                width=90
            ).pack(padx=10, pady=5)

        self.error_login = ctk.CTkLabel(self, text="", text_color="red")
        self.error_login.pack(pady=5)

        self.boton_conectar = ctk.CTkButton(self, text="Conectarse", width=300, height=40, command=self.entrar)
        self.boton_conectar.pack(pady=10)

    def entrar(self):
        usuario = self.entrada_usuario.get().strip()
        password = self.entrada_password.get().strip()

        if not usuario or not password:
            self.error_login.configure(text="Ingresa tu usuario y contraseña", text_color="red")
            return

        if any(c in usuario + password for c in ("|", "\n", "\r")):
            self.error_login.configure(text="No uses | ni saltos de línea", text_color="red")
            return

        self.usuario = usuario
        self.foto = self.foto_seleccionada.get()

        self.error_login.configure(text="Conectando con el servidor...", text_color="white")
        self.boton_conectar.configure(state="disabled")

        exito, mensaje = self.cliente.conectar()
        if not exito:
            self.error_login.configure(text=mensaje, text_color="red")
            self.boton_conectar.configure(state="normal")
            return

        self.cliente.login(usuario, password, self.foto)

    # ========================================================
    # VENTANA PRINCIPAL
    # ========================================================
    def mostrar_principal(self):
        self.limpiar()

        self.geometry("1050x650")
        self.minsize(850, 550)
        self.title("Wasap - Chat")

        self.menu = ctk.CTkFrame(self, width=230)
        self.menu.pack(side="left", fill="y", padx=10, pady=10)
        self.menu.pack_propagate(False)

        ctk.CTkLabel(self.menu, text="Wasap", font=("Arial", 26, "bold")).pack(pady=(20, 10))

        self.imagen_usuario = cargar_foto(self.foto, (85, 85))
        if self.imagen_usuario is not None:
            ctk.CTkLabel(self.menu, text="", image=self.imagen_usuario).pack(pady=10)

        ctk.CTkLabel(self.menu, text=f"Usuario: {self.usuario}", font=("Arial", 15, "bold")).pack(pady=10)

        secciones = [
            ("Chat general", self.mostrar_chat_general),
            ("Mensajes privados", self.mostrar_privados),
            ("Grupos", self.mostrar_grupos),
            ("Canales", self.mostrar_canales)
        ]

        for nombre, funcion in secciones:
            ctk.CTkButton(self.menu, text=nombre, width=190, height=40, command=funcion).pack(pady=10)

        self.contenido = ctk.CTkFrame(self)
        self.contenido.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

        self.mostrar_chat_general()

    # ========================================================
    # CHAT GENERAL
    # ========================================================
    def mostrar_chat_general(self):
        self.seccion_actual = "general"
        self.limpiar_contenido()
        self.titulo_seccion("Chat general")

        self.caja_general = ctk.CTkTextbox(self.contenido, font=("Arial", 14))
        self.caja_general.pack(fill="both", expand=True, padx=20, pady=10)

        for mensaje in self.mensajes_general:
            self.caja_general.insert("end", mensaje + "\n\n")

        self.caja_general.configure(state="disabled")
        self.caja_general.see("end")

        barra = ctk.CTkFrame(self.contenido, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=20)

        entrada = ctk.CTkEntry(barra, placeholder_text="Escribe un mensaje...", height=40)
        entrada.pack(side="left", fill="x", expand=True, padx=(0, 10))

        def enviar():
            texto = entrada.get().strip()
            if not texto or not self.cliente.conectado:
                return
            self.cliente.enviar_texto(1, texto)
            entrada.delete(0, "end")

        ctk.CTkButton(barra, text="Enviar", width=100, height=40, command=enviar).pack(side="right")
        entrada.bind("<Return>", lambda evento: enviar())

    # ========================================================
    # MENSAJES PRIVADOS
    # ========================================================
    def mostrar_privados(self):
        self.seccion_actual = "privados"
        self.limpiar_contenido()
        self.titulo_seccion("Mensajes privados")

        ctk.CTkLabel(self.contenido, text="Selecciona un usuario").pack(pady=5)

        opciones = self.usuarios_online
        if not opciones:
            ctk.CTkLabel(self.contenido, text="No hay otros usuarios conectados", text_color="gray").pack(pady=10)
            return

        selector = ctk.CTkOptionMenu(self.contenido, values=opciones, command=self.seleccionar_usuario)
        selector.pack(pady=10)

        if self.usuario_destino not in opciones:
            self.usuario_destino = opciones[0]

        selector.set(self.usuario_destino)

        id_destino = self.ids_usuarios.get(self.usuario_destino)
        if id_destino is not None:
            self.cliente.abrir_privado(id_destino)

        self.caja_privados = ctk.CTkTextbox(self.contenido, font=("Arial", 14))
        self.caja_privados.pack(fill="both", expand=True, padx=20, pady=10)

        barra = ctk.CTkFrame(self.contenido, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=20)

        self.entrada_privado = ctk.CTkEntry(barra, placeholder_text="Escribe un mensaje privado...", height=40)
        self.entrada_privado.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(barra, text="Enviar", width=100, height=40, command=self.enviar_privado).pack(side="right")
        self.entrada_privado.bind("<Return>", lambda evento: self.enviar_privado())

        self.actualizar_privados()

    def seleccionar_usuario(self, nombre):
        self.usuario_destino = nombre
        id_destino = self.ids_usuarios.get(nombre)
        if id_destino is not None:
            self.cliente.abrir_privado(id_destino)
        self.actualizar_privados()

    def actualizar_privados(self):
        self.caja_privados.configure(state="normal")
        self.caja_privados.delete("1.0", "end")

        for mensaje in self.mensajes_privados.get(self.usuario_destino, []):
            self.caja_privados.insert("end", mensaje + "\n\n")

        self.caja_privados.configure(state="disabled")
        self.caja_privados.see("end")

    def enviar_privado(self):
        texto = self.entrada_privado.get().strip()
        if not texto or self.usuario_destino is None:
            return

        id_sala = self.salas_privadas.get(self.usuario_destino)
        if id_sala is None:
            id_destino = self.ids_usuarios.get(self.usuario_destino)
            if id_destino is not None:
                self.cliente.abrir_privado(id_destino)
            return

        if not self.cliente.conectado:
            return

        self.cliente.enviar_texto(id_sala, texto)
        self.entrada_privado.delete(0, "end")

    # ========================================================
    # GRUPOS
    # ========================================================
    def mostrar_grupos(self):
        self.seccion_actual = "grupos"
        self.limpiar_contenido()
        self.titulo_seccion("Grupos")

        ctk.CTkLabel(self.contenido, text="Crear un grupo").pack(pady=5)

        entrada_nombre = ctk.CTkEntry(self.contenido, placeholder_text="Nombre del grupo", width=300)
        entrada_nombre.pack(pady=10)

        ctk.CTkLabel(self.contenido, text="Selecciona los integrantes").pack(pady=5)

        seleccionados = {}
        marco = ctk.CTkFrame(self.contenido)
        marco.pack(pady=10)

        for usuario in self.usuarios_online:
            variable = ctk.BooleanVar(value=False)
            seleccionados[usuario] = variable
            ctk.CTkCheckBox(marco, text=usuario, variable=variable).pack(padx=20, pady=6)

        aviso = ctk.CTkLabel(self.contenido, text="", text_color="orange")
        aviso.pack(pady=3)

        def crear_grupo():
            nombre = entrada_nombre.get().strip()
            miembros = [u for u, var in seleccionados.items() if var.get()]

            if not nombre:
                aviso.configure(text="Escribe el nombre del grupo")
                return
            if not miembros:
                aviso.configure(text="Selecciona al menos un integrante")
                return
            if any(g["nombre"] == nombre for g in self.grupos):
                aviso.configure(text="Ya existe un grupo con ese nombre")
                return

            ids_miembros = [self.ids_usuarios[u] for u in miembros if u in self.ids_usuarios]
            self.cliente.crear_grupo(nombre, ids_miembros)
            aviso.configure(text="Solicitando creación del grupo...")

        ctk.CTkButton(self.contenido, text="Crear grupo", command=crear_grupo).pack(pady=10)
        ctk.CTkLabel(self.contenido, text="Mis grupos", font=("Arial", 18, "bold")).pack(pady=(15, 5))

        lista = ctk.CTkScrollableFrame(self.contenido)
        lista.pack(fill="both", expand=True, padx=20, pady=10)

        if not self.grupos:
            ctk.CTkLabel(lista, text="Todavía no has creado grupos").pack(pady=15)

        for grupo in self.grupos:
            fila = ctk.CTkFrame(lista)
            fila.pack(fill="x", padx=5, pady=5)

            ctk.CTkLabel(fila, text=grupo["nombre"], font=("Arial", 15, "bold")).pack(side="left", padx=15, pady=10)
            ctk.CTkButton(
                fila,
                text="Abrir chat",
                width=100,
                command=lambda g=grupo: self.abrir_chat_grupo(g)
            ).pack(side="right", padx=10, pady=8)

    def abrir_chat_grupo(self, grupo, solicitar_historial=True):
        self.seccion_actual = "grupo_abierto"
        self.grupo_actual_id = grupo.get("id_sala")

        if solicitar_historial and self.grupo_actual_id is not None:
            self.cliente.solicitar_historial_grupo(self.grupo_actual_id)

        self.limpiar_contenido()

        encabezado = ctk.CTkFrame(self.contenido)
        encabezado.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(encabezado, text="← Volver", width=90, command=self.mostrar_grupos).pack(side="left", padx=10, pady=10)
        ctk.CTkLabel(encabezado, text=grupo["nombre"], font=("Arial", 22, "bold")).pack(side="left", padx=15)

        integrantes = ", ".join(grupo.get("miembros", []))
        ctk.CTkLabel(self.contenido, text=f"Integrantes: {integrantes}").pack(pady=5)

        mensajes = ctk.CTkTextbox(self.contenido, font=("Arial", 14))
        mensajes.pack(fill="both", expand=True, padx=20, pady=10)

        for mensaje in grupo.get("mensajes", []):
            mensajes.insert("end", mensaje + "\n\n")

        mensajes.configure(state="disabled")
        mensajes.see("end")

        barra = ctk.CTkFrame(self.contenido, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=20)

        entrada = ctk.CTkEntry(barra, placeholder_text="Escribe un mensaje al grupo...", height=40)
        entrada.pack(side="left", fill="x", expand=True, padx=(0, 10))

        def enviar_mensaje_grupo():
            texto = entrada.get().strip()
            if not texto:
                return
            id_sala = grupo.get("id_sala")
            if id_sala is not None and self.cliente.conectado:
                self.cliente.enviar_texto(id_sala, texto)
                entrada.delete(0, "end")

        ctk.CTkButton(barra, text="Enviar", width=100, height=40, command=enviar_mensaje_grupo).pack(side="right")
        entrada.bind("<Return>", lambda evento: enviar_mensaje_grupo())

    # ========================================================
    # CANALES
    # ========================================================
    def mostrar_canales(self, actualizar=True):
        self.seccion_actual = "canales"
        self.limpiar_contenido()
        self.titulo_seccion("Canales")

        if actualizar:
            self.cliente.listar_canales()

        ctk.CTkLabel(self.contenido, text="Crear un canal").pack(pady=5)

        entrada_nombre = ctk.CTkEntry(self.contenido, placeholder_text="Nombre del canal", width=300)
        entrada_nombre.pack(pady=10)

        aviso = ctk.CTkLabel(self.contenido, text="", text_color="orange")
        aviso.pack(pady=3)

        def crear_canal():
            nombre = entrada_nombre.get().strip()
            if not nombre:
                aviso.configure(text="Escribe el nombre del canal")
                return
            if any(c["nombre"] == nombre for c in self.canales):
                aviso.configure(text="Ya existe un canal con ese nombre")
                return

            self.cliente.crear_canal(nombre)
            aviso.configure(text="Creando canal en el servidor...")

        ctk.CTkButton(self.contenido, text="Crear canal", command=crear_canal).pack(pady=10)
        ctk.CTkLabel(self.contenido, text="Canales disponibles", font=("Arial", 18, "bold")).pack(pady=(15, 5))

        lista = ctk.CTkScrollableFrame(self.contenido)
        lista.pack(fill="both", expand=True, padx=20, pady=10)

        if not self.canales:
            ctk.CTkLabel(lista, text="Todavía no hay canales").pack(pady=15)

        for canal in self.canales:
            fila = ctk.CTkFrame(lista)
            fila.pack(fill="x", padx=5, pady=5)

            informacion = ctk.CTkFrame(fila, fg_color="transparent")
            informacion.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            ctk.CTkLabel(informacion, text=canal["nombre"], font=("Arial", 15, "bold")).pack(anchor="w")
            ctk.CTkLabel(
                informacion,
                text="Dueño del canal" if canal.get("dueno", False) else "Canal disponible"
            ).pack(anchor="w")

            ctk.CTkButton(
                fila,
                text="Abrir canal",
                width=110,
                command=lambda c=canal: self.abrir_canal(c)
            ).pack(side="right", padx=10, pady=8)

    def abrir_canal(self, canal):
        self.seccion_actual = "canal_abierto"
        self.canal_actual_id = canal["id_sala"]
        self.limpiar_contenido()

        encabezado = ctk.CTkFrame(self.contenido)
        encabezado.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(encabezado, text="← Volver", width=90, command=self.mostrar_canales).pack(side="left", padx=10, pady=10)
        ctk.CTkLabel(encabezado, text=canal["nombre"], font=("Arial", 22, "bold")).pack(side="left", padx=15)

        ctk.CTkLabel(
            self.contenido,
            text="Dueño del canal" if canal.get("dueno", False) else "Canal disponible"
        ).pack(pady=5)

        es_creador = canal.get("dueno", False)
        esta_suscrito = canal.get("unido", False) or es_creador

        if not esta_suscrito:
            def suscribirse():
                self.cliente.unirse_canal(canal["id_sala"])

            ctk.CTkButton(self.contenido, text="Suscribirse al canal", command=suscribirse).pack(pady=10)
        else:
            ctk.CTkLabel(self.contenido, text="Suscrito al canal", text_color="lightgreen").pack(pady=5)

        mensajes = ctk.CTkTextbox(self.contenido, font=("Arial", 14))
        mensajes.pack(fill="both", expand=True, padx=20, pady=10)

        for mensaje in canal["mensajes"]:
            mensajes.insert("end", mensaje + "\n\n")

        mensajes.configure(state="disabled")
        mensajes.see("end")

        if es_creador:
            barra = ctk.CTkFrame(self.contenido, fg_color="transparent")
            barra.pack(fill="x", padx=20, pady=20)

            entrada = ctk.CTkEntry(barra, placeholder_text="Escribe una publicación...", height=40)
            entrada.pack(side="left", fill="x", expand=True, padx=(0, 10))

            def publicar():
                texto = entrada.get().strip()
                if not texto:
                    return
                self.cliente.enviar_texto(canal["id_sala"], texto)
                entrada.delete(0, "end")

            ctk.CTkButton(barra, text="Publicar", width=100, height=40, command=publicar).pack(side="right")
            entrada.bind("<Return>", lambda event: publicar())
        else:
            ctk.CTkLabel(self.contenido, text="Solo el creador puede publicar en este canal.").pack(pady=20)


if __name__ == "__main__":
    app = Wasap()
    app.mainloop()