# Setup blockers — qué arreglar para empezar

Estado al **2026-08-23**. Objetivo: dejar un entorno rápido y estable para desarrollar el agente y
correr experimentos. Lo demás del repo (kit `re-takehome-main/`) queda intacto.

Resumen: el entorno elegido es **Ryzen 7 7730U vía WSL2 Ubuntu-22.04** (rápido, con AVX2). `sshrun`
(Linux 2011) funciona pero es ~10-15× más lento (14 min por operación) → solo fallback. El único
bloqueo real hoy es **RAM del host de Windows**.

---

## 🔴 Blocker 1 — RAM del host (el único que impide arrancar)

**Síntoma:** el `docker pull` (y `import Mathlib`) mata la VM de WSL a mitad.

**Causa (medida):** 15.3 GB totales; Windows usa ~9.6 GB → solo ~5.7 GB libres. Cuando el workload
infla `vmmem` a ~5-6.5 GB, el host cae a <1 GB libre y Windows **termina la VM**. El guest nunca
llega a su cap de 8 GB — se queda sin RAM **el host**, no el guest.

**Fix (acción tuya, 1 min):** cerrar apps pesadas antes de correr el kit.

| App | Libera |
|---|---|
| **Chrome** (25 procesos) | **~3.7 GB** |
| **ChatGPT** | **~1.2 GB** |

- Cerrando esos dos → host libre pasa de ~5.7 a **~10-11 GB** → la VM puede usar sus ~6.5 GB de
  Mathlib sin matar al host.
- **No** cerrar Claude Desktop (es esta sesión). No hace falta subir el cap de WSL (dejarlo en 8 GB).

**Verificación:** con Chrome/ChatGPT cerrados, `docker pull` completa y el health check pasa.

---

## 🟡 Blocker 2 — Mantener viva la VM durante trabajos largos

**Síntoma:** trabajos lanzados con `nohup`/desacoplados mueren cuando el cliente `wsl.exe` retorna.

**Causa:** la VM se apaga si no hay un cliente `wsl.exe` attached (aunque haya procesos corriendo).

**Fix:** correr pulls/experimentos largos como comando **en primer plano** (attached) con timeout
amplio, no desacoplados. Para runs de horas, mantener una sesión `wsl.exe` abierta.

---

## 🟢 Ya resueltos (no requieren acción)

- ✅ **Docker en WSL**: ya instalado (v29.1.3), datos en **D:** (`D:\WSL\Ubuntu2204`), no toca C:.
- ✅ **Python 3.11**: instalado con `uv` (3.11.16) + shim `~/.pyshim/python3`; el python del sistema
  (3.10) quedó intacto. Resuelve el requisito `>=3.11` del kit sin editar el kit.
- ✅ **Repo clonado** en WSL nativo (`~/verified-mechanism`, no `/mnt/d`) y en `sshrun`. Remotes
  limpios (sin token).
- ✅ **`avid-server`** detenido en WSL + auto-restart desactivado (usaba solo 98 MB; reversible con
  `docker start avid-server`). Imagen `avid-journal` intacta.
- ✅ **`sshrun`** 100% funcional como fallback: imagen, health y smoke OK.

---

## ⚪ Decisión pendiente (no bloquea el arranque)

- **VM en la nube (16-32 GB) para los runs largos de la parte 2.** La laptop de 15 GB alcanza para
  desarrollo/testing con apps cerradas, pero es frágil para corridas desatendidas de horas. Coincide
  con el esquema original: **dev/testing en la Ryzen, runs largos en un entorno dedicado.**

---

## Secuencia para arrancar (una vez liberada la RAM)

```bash
# 1) (en Windows) cerrar Chrome y ChatGPT

# 2) (en WSL) completar el setup del kit — attached, con host RAM libre
cd ~/verified-mechanism/re-takehome-main
PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH" bash scripts/setup.sh   # pull imagen + health

# 3) verificar sin key (debería tardar ~1-2 min)
bash scripts/smoke_test.sh

# 4) recién ahí: agregar la key en .env y empezar baselines solo
cp .env.example .env    # y pegar OPENROUTER_API_KEY
```
