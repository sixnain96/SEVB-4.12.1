"""OBSOLETO desde la Fase B (acceso solo con Google).

Este script probaba registro, entrada y cambio de contraseña, el vínculo de una cuenta con contraseña al entrar con Google con el mismo correo y el borrado escribiendo el correo. Esas vías ya no existen en el servidor (responden 410) y el vínculo por correo se eliminó (docs/CUENTAS.md).
Cobertura vigente: CuentaControllerTest, GoogleTokenVerifierTest, CuentaIdentidadPostgresTest (PostgreSQL real) y e2e/cuenta_google_e2e.py (navegador, Google simulado).
Se conserva el archivo solo como referencia histórica; ejecutarlo no hace nada.
"""
import sys

print('Obsoleto: ver el docstring de este archivo y docs/CUENTAS.md.')
sys.exit(0)
