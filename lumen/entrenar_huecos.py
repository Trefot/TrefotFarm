"""Entrena el detector de huecos vacios de la mano (lumen/huecos.py). Solo para quien mantiene Lumen.

    python -m lumen.entrenar_huecos casillas.npz

``casillas.npz`` lleva ``imagenes`` (lista de casillas de la mano, BGR) y ``etiquetas`` (1 = hueco, 0 = carta).
Necesita scikit-learn solo aqui, para entrenar; Lumen usa el resultado con numpy (assets/modelos/huecos_lumen.npz).
"""

from __future__ import annotations

import sys

import numpy as np

from lumen import huecos

C_SVM = 5.0


def entrenar(imagenes, etiquetas) -> dict:
    from sklearn.svm import SVC

    X = np.array([huecos.rasgos(img) for img in imagenes])
    y = np.asarray(etiquetas, dtype=int)
    svm = SVC(C=C_SVM, gamma="scale").fit(X, y)
    gamma = 1.0 / (X.shape[1] * X.var())  # lo que usa gamma="scale"
    datos = {"vectores": svm.support_vectors_.astype(np.float32), "pesos": svm.dual_coef_[0].astype(np.float32),
             "sesgo": np.float32(svm.intercept_[0]), "gamma": np.float32(gamma)}
    # La clase 1 (hueco) es la "positiva" de la SVM: decision > 0 -> hueco
    assert list(svm.classes_) == [0, 1]
    return datos


def main(ruta: str) -> None:
    with np.load(ruta, allow_pickle=True) as f:
        imagenes, etiquetas = list(f["imagenes"]), f["etiquetas"]
    datos = entrenar(imagenes, etiquetas)
    huecos.ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(huecos.ARCHIVO, **datos)
    print(f"{len(datos['vectores'])} vectores de soporte -> {huecos.ARCHIVO}")


if __name__ == "__main__":
    main(sys.argv[1])
