"""Resumen al terminar una sesion de farmeo: una tarjeta en pantalla y el mismo resumen al movil (ntfy)."""

import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from lumen import avisos, botin
from lumen.gui import iconos, tema
from lumen.gui.comun import formatear_tiempo

MINIMO_S = 30  # sesiones mas cortas (arranques en falso) no se resumen


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def datos(stats: dict, segundos: float, registros: list[dict]) -> dict:
    """Lo que entra en el resumen: cifras de la sesion y el botin de sus fotos de victoria."""
    totales: dict[str, int] = {}
    for r in registros:
        for oid, cantidad in (r.get("objetos") or {}).items():
            totales[oid] = totales.get(oid, 0) + int(cantidad)
    victorias = int(stats.get("victorias") or 0)
    peleas = victorias + int(stats.get("derrotas") or 0) + int(stats.get("reinicios") or 0)
    return {
        "victorias": victorias,
        "derrotas": int(stats.get("derrotas") or 0),
        "peleas": peleas,
        "segundos": segundos,
        "por_hora": victorias / (segundos / 3600) if segundos > 0 else 0.0,
        "oro": sum(int(r.get("oro") or 0) for r in registros),
        "objetos": dict(sorted(totales.items(), key=lambda kv: -kv[1])),
        "ultima_foto": max(registros, key=lambda r: r.get("fecha", 0)).get("ruta_completa") if registros else None,
    }


def texto(nombre_modo: str, d: dict, catalogo: dict | None = None) -> str:
    """El resumen en pocas lineas (para el movil)."""
    catalogo = catalogo if catalogo is not None else botin.cargar_catalogo()
    lineas = [f"Lumen Farm: sesión terminada · {nombre_modo}",
              f"{d['victorias']} victorias de {d['peleas']} peleas · {formatear_tiempo(d['segundos'])} · "
              f"{d['por_hora']:.1f} por hora".replace(".", ",")]
    if d["oro"]:
        lineas.append(f"Oro: {_miles(d['oro'])}")
    if d["objetos"]:
        lineas.append("Botín: " + ", ".join(f"{botin.nombre(oid, catalogo)} ×{_miles(n)}"
                                            for oid, n in list(d["objetos"].items())[:8]))
    return "\n".join(lineas)


def enviar_al_movil(nombre_modo: str, d: dict) -> None:
    """Manda el resumen por ntfy con la foto de la ultima victoria (si hay canal configurado)."""
    foto = cv2.imread(str(d["ultima_foto"])) if d["ultima_foto"] else None
    avisos.enviar(texto(nombre_modo, d), foto)


class TarjetaResumen(QDialog):
    """La tarjeta que sale al terminar: foto del modo, cifras y el botin conseguido."""

    def __init__(self, padre, nombre_modo: str, foto, d: dict):
        super().__init__(padre)
        self.setWindowTitle("Sesión terminada")
        self.setMinimumWidth(520)
        capa = QVBoxLayout(self)
        capa.setSpacing(12)

        cab = QHBoxLayout()
        emblema = QLabel()
        pix = iconos.redondo(foto, 84, tema.ACENTO) if foto else None
        if pix:
            emblema.setPixmap(pix)
        cab.addWidget(emblema)
        textos = QVBoxLayout()
        textos.addWidget(QLabel("Sesión terminada", objectName="titulo_pagina"))
        textos.addWidget(QLabel(nombre_modo, objectName="tenue"))
        cab.addLayout(textos, 1)
        capa.addLayout(cab)

        cifras = QGridLayout()
        cifras.setSpacing(8)
        for i, (valor, titulo, icono) in enumerate((
            (str(d["victorias"]), "Victorias", "trofeo"),
            (formatear_tiempo(d["segundos"]), "Tiempo", "reloj"),
            (f"{d['por_hora']:.1f}".replace(".", ","), "Por hora", "rayo"),
            (_miles(d["oro"]), "Oro", "oro"),
        )):
            marco = QFrame(objectName="cifra_mini")
            c = QVBoxLayout(marco)
            c.setContentsMargins(8, 8, 8, 6)
            arriba = QHBoxLayout()
            arriba.addStretch()
            dibujo = QLabel()
            dibujo.setPixmap(iconos.pixmap(icono, 20, tema.ACENTO))
            arriba.addWidget(dibujo)
            arriba.addWidget(QLabel(valor, objectName="cifra"))
            arriba.addStretch()
            c.addLayout(arriba)
            c.addWidget(QLabel(titulo, objectName="tenue", alignment=Qt.AlignCenter))
            cifras.addWidget(marco, 0, i)
        capa.addLayout(cifras)

        if d["objetos"]:
            capa.addWidget(QLabel("Botín conseguido", objectName="titulo_seccion"))
            rejilla = QGridLayout()
            rejilla.setSpacing(6)
            catalogo = botin.cargar_catalogo()
            for i, (oid, cantidad) in enumerate(list(d["objetos"].items())[:24]):
                casilla = QFrame(objectName="objeto_mini")
                c = QVBoxLayout(casilla)
                c.setContentsMargins(4, 4, 4, 2)
                c.setSpacing(0)
                dibujo = QLabel(alignment=Qt.AlignCenter)
                p = QPixmap(str(botin.ruta_icono(oid)))
                if not p.isNull():
                    dibujo.setPixmap(p.scaled(44, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                c.addWidget(dibujo)
                c.addWidget(QLabel(f"×{_miles(cantidad)}", objectName="cantidad_mini", alignment=Qt.AlignCenter))
                casilla.setToolTip(botin.nombre(oid, catalogo))
                rejilla.addWidget(casilla, i // 8, i % 8)
            capa.addLayout(rejilla)
        elif d["victorias"]:
            capa.addWidget(QLabel("No se leyó botín de estas victorias.", objectName="tenue"))

        boton = QPushButton("Aceptar", objectName="primario")
        boton.clicked.connect(self.accept)
        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(boton)
        capa.addLayout(fila)
