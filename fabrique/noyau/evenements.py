"""Flux d'événements du noyau (SSE) : chaque abonné (la fenêtre) a sa file ; un battement toutes les 15 s garde la connexion vivante et
fait voir au noyau un abonné parti."""
import json
import queue
import threading

BATTEMENT = 15
_abonnes: set[queue.Queue] = set()
_verrou = threading.Lock()


def publier(type_: str, **donnees):
    with _verrou:
        for q in _abonnes:
            q.put_nowait({"type": type_, **donnees})


def flux(battement: float = BATTEMENT):
    q: queue.Queue = queue.Queue()
    with _verrou:
        _abonnes.add(q)
    try:
        yield ": ouvert\n\n"
        while True:
            try:
                e = q.get(timeout=battement)
            except queue.Empty:
                yield ": battement\n\n"
                continue
            yield f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False, default=str)}\n\n"
    finally:  # abonné parti (écriture refusée par waitress) : sa file est retirée
        with _verrou:
            _abonnes.discard(q)
