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
