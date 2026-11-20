# Minioms (Wasap) — Práctica 1: Sistemas Distribuidos

Aplicación de mensajería cliente-servidor desarrollada en Python utilizando **Sockets TCP**
---

## 📋 Requisitos Previos (Cliente)

Para ejecutar el cliente en cualquier computadora con Windows, Linux o macOS únicamente se necesita:

1. **Python 3.10 o superior** instalado.
2. Las siguientes librerías de Python:
   * `customtkinter` (interfaz gráfica)
   * `pillow` (carga y procesamiento de fotos de perfil)
   * pip install customtkinter pillow
   * Si se tiene problemas en la instalacion en distribucion Linux agregar el comando:
   * -- break-system-packages al final
---
Entra al enlace del repositorio en GitHub ([https://github.com/IsaacPR19/Sist.Distrib](https://github.com/IsaacPR19/Sist.Distrib)).   Haz clic en el botón verde <> Code y selecciona Download ZIP.  
Descomprime el archivo Sist.Distrib-main.zip en cualquier carpeta de su computadora.Verificación: Al abrir la carpeta descomprimida, verá adentro assets, client, server, README.md y requirements.txt.

Instalar las 2 dependencias de Python:
pip install -r requirements.txt

Abrir la aplicación cliente:
cd client
python interface.py

---

## 📁 Estructura de Archivos Necesarios

```text
minioms/
├── assets/
│   └── avatars/
│       ├── perfil1.jpg
│       ├── perfil2.jpg
│       ├── perfil3.jpg
│       ├── perfil4.jpg
│       ├── perfil5.jpg
│       ├── perfil6.jpg
│       ├── perfil7.jpg
│       ├── perfil8.jpg
│       └── perfil9.jpg
├── client/
│   ├── client.py        # Lógica de red, sockets TCP y protocolo de comunicación
│   └── interface.py     # Interfaz gráfica principal (ejecutable)
└── server/              # (Ya desplegado en AWS; no se ejecuta en el cliente)
    ├── server.py
    └── database.py
