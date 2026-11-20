import socket
import threading

HOST = "127.0.0.1"  # Localhost (tu propia laptop)
PORT = 3081         # Debe ser el MISMO puerto que pusiste en server.py

def escuchar_servidor(sock):
    """Hilo en segundo plano para imprimir todo lo que responda el servidor."""
    buffer = ""
    while True:
        try:
            datos = sock.recv(4096)
            if not datos:
                print("\n[!] El servidor cerró la conexión.")
                break
            buffer += datos.decode("utf-8")
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                print(f"\n[SERVIDOR] -> {linea}")
        except:
            break

if __name__ == "__main__":
    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect((HOST, PORT))
    print(f"[*] Conectado a {HOST}:{PORT}")
    print("Escribe comandos (ej: LOGIN|Isaac|1234) o 'salir' para terminar:\n")

    # Arrancamos el hilo que escucha respuestas del servidor
    threading.Thread(target=escuchar_servidor, args=(cliente,), daemon=True).start()

    while True:
        msg = input()
        if msg.lower() == "salir":
            break
        # Agregamos '\n' al final porque el servidor lee línea por línea
        cliente.sendall((msg + "\n").encode("utf-8"))

    cliente.close()