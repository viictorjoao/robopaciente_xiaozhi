"""Ponto de entrada: python -m app.main  (ou iniciar.bat / iniciar.sh)."""
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import api, config, db, xiaozhi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%H:%M:%S")

app = FastAPI(title="Robô Paciente — UNINORTE")
db.iniciar()

app.include_router(xiaozhi.router)
app.include_router(api.router)
app.include_router(api.A)

ESTATICO = config.BASE / "static"
app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


@app.get("/")
def raiz():
    return RedirectResponse("/aluno")


@app.get("/professor")
def professor():
    return FileResponse(ESTATICO / "professor.html")


@app.get("/aluno")
def aluno():
    return FileResponse(ESTATICO / "aluno.html")


def rodar():
    ips = api.ips_locais()
    print("\n" + "=" * 64)
    print("  ROBÔ PACIENTE — servidor iniciado")
    for ip in ips:
        print(f"  Professor:  http://{ip}:{config.PORTA}/professor")
        print(f"  Alunos:     http://{ip}:{config.PORTA}/aluno")
        print(f"  URL OTA (configure no ESP32):  http://{ip}:{config.PORTA}/xiaozhi/ota/")
    print("=" * 64 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=config.PORTA, log_level="warning", ws_ping_interval=20, ws_ping_timeout=20)


if __name__ == "__main__":
    rodar()
