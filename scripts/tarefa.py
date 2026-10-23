#!/usr/bin/env python3
"""Escolhe o modelo pela tabela config/modelos.yaml, lê a cota e roda a tarefa.
Uso: scripts/tarefa.sh TIPO "prompt"   |   scripts/tarefa.sh --cota   |   --dry-run TIPO
Avisos 50%/80% vão pra logs/avisos-cota.log (uma vez por janela). Log: logs/tarefas.log."""
import json, os, re, subprocess, sys, time, glob
from datetime import datetime, timezone
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(RAIZ, "logs"); os.makedirs(LOGS, exist_ok=True)
ESTADO = os.path.join(LOGS, ".avisos-estado.json")

def tabela():
    txt = open(os.path.join(RAIZ, "config", "modelos.yaml"), encoding="utf-8").read()
    lim = dict(re.findall(r"(aviso|para):\s*(\d+)", txt))
    tar = {k: [x.strip() for x in v.split(",")] for k, v in re.findall(r"^\s+([\w-]+):\s*\[(.*)\]", txt, re.M)}
    return int(lim["aviso"]), int(lim["para"]), tar

def grupo(prov, modelo):
    if prov == "codex": return "Codex"
    if "argon" in modelo: return "Gemini 4 Argon"
    if "flash" in modelo or "gemini" in modelo: return "Gemini Models"
    return "Claude and GPT models"

def cotas():
    """{grupo: [(janela, usado%, reset_iso)]}"""
    c = {}
    try:
        j = json.loads(subprocess.run(["agy", "-p", "/usage", "--output-format", "json"],
                       capture_output=True, text=True, timeout=60).stdout)
        for g in j["command"]["data"]["groups"]:
            c[g["name"]] = [(b.get("window", "?"), round(100 * (1 - b["remaining_fraction"])), b.get("reset_time", ""))
                            for b in g["buckets"]]
    except Exception as e:
        print(f"[cota] agy falhou: {e}", file=sys.stderr)
    try:
        f = max(glob.glob(os.path.expanduser("~/.codex/sessions/**/*.jsonl"), recursive=True), key=os.path.getmtime)
        rl = None
        for linha in open(f, encoding="utf-8"):
            if '"rate_limits"' in linha:
                m = re.search(r'"rate_limits":(\{.*?"credits")', linha)
                if m: rl = json.loads(m.group(1)[:-len(',"credits"')] + "}")
        if rl:
            c["Codex"] = [(("5h" if p["window_minutes"] == 300 else "weekly"), round(p["used_percent"]),
                           datetime.fromtimestamp(p["resets_at"], timezone.utc).isoformat())
                          for p in (rl.get("primary"), rl.get("secondary")) if p]
    except Exception as e:
        print(f"[cota] codex falhou: {e}", file=sys.stderr)
    return c

def avisar(c, aviso, para):
    est = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {}
    novos = []
    for g, bs in c.items():
        for jan, usado, reset in bs:
            for nivel in (para, aviso):
                if usado >= nivel:
                    k = f"{g}|{jan}|{reset}|{nivel}"
                    if k not in est:
                        est[k] = 1
                        acao = "PARA de usar, vai pro backup" if nivel == para else "avisar o Lucas"
                        novos.append(f"{datetime.now():%d/%m %H:%M} AVISO {nivel}%: {g} ({jan}) {usado}% usado, renova {reset}: {acao}")
                    break
    json.dump(est, open(ESTADO, "w"))
    if novos:
        open(os.path.join(LOGS, "avisos-cota.log"), "a", encoding="utf-8").write("\n".join(novos) + "\n")
    return novos

def bloqueado(c, g, para):
    return any(u >= para for _, u, _ in c.get(g, []))

def resumo(c):
    return " | ".join(f"{g}: " + ", ".join(f"{j} {100-u}% restante" for j, u, _ in bs) for g, bs in c.items())

def rodar(spec, prompt, log):
    prov, modelo, *esf = spec.split(":")
    if prov == "codex":
        cmd = ["codex", "exec", "-m", modelo, "-c", f"model_reasoning_effort={esf[0] if esf else 'medium'}",
               "-s", "workspace-write", "-C", RAIZ, prompt]
    else:
        cmd = ["agy", "-p", prompt, "--model", modelo, "--dangerously-skip-permissions", "--add-dir", RAIZ, "--print-timeout", "15m"]
    with open(log, "w", encoding="utf-8") as f:  # timeout evita agy preso em tarefa de fundo
        return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=RAIZ).returncode

def main(a):
    aviso, para, tar = tabela()
    if a[:1] == ["--cota"]:
        c = cotas(); n = avisar(c, aviso, para); print(resumo(c)); [print(x) for x in n]; return 0
    dry = a[:1] == ["--dry-run"]; a = a[1:] if dry else a
    if not a or a[0] not in tar:
        print("tipos: " + ", ".join(tar)); return 2
    tipo, prompt = a[0], " ".join(a[1:])
    c = cotas(); [print(x) for x in avisar(c, aviso, para)]
    for spec in tar[tipo]:
        g = grupo(*spec.split(":")[:2])
        if bloqueado(c, g, para) or (g not in c and g != "Codex"):
            print(f"pulando {spec} ({g} >= {para}% ou sem leitura)"); continue
        if dry:
            print(f"{tipo} -> {spec}"); return 0
        log = os.path.join(LOGS, f"tarefa-{datetime.now():%Y%m%d-%H%M%S}-{tipo}.log")
        t = time.time(); rc = rodar(spec, prompt, log); dt = round(time.time() - t)
        open(os.path.join(LOGS, "tarefas.log"), "a", encoding="utf-8").write(
            f"{datetime.now():%Y-%m-%d %H:%M} {tipo} {spec} {'ok' if rc == 0 else 'erro'} {dt}s {os.path.basename(log)}\n")
        print(f"{tipo} {spec} {'ok' if rc == 0 else 'erro rc=%d' % rc} {dt}s log={log}")
        if rc == 0: return 0
    print("sem modelo disponível: avisar o Boss"); return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
