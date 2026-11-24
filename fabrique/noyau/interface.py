"""L'interface de la fenêtre (0.12) : une application web (interface\\, React, construite dans fenetre\\web) servie par le noyau et affichée dans
la fenêtre WebView2. Elle entre une fois par /fenetre/entree?j=<jeton de la fenêtre> (lu par la fenêtre dans donnees) : le jeton est posé
en cookie HttpOnly SameSite=Strict, puis chaque appel de l'API le porte sans que la page le voie ; une requête qui change quelque chose
porte aussi l'en-tête X-Fabrique (comme l'iPhone). Images réduites gardées dans donnees\\cache ; vidéos servies par morceaux (Range : le
lecteur peut sauter)."""
import hashlib
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.views.decorators.http import require_GET

from fabrique import dossiers
from fabrique.noyau import jetons

COOKIE = "fabrique_fenetre"
LOCAL = ("127.0.0.1", "localhost")
LARGEURS = (320, 640, 960, 1280)  # vignettes demandées par l'interface ; toute autre largeur est ramenée à la plus proche au-dessus
SURETE = {"X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}


def web() -> Path:
    """Installée : fenetre\\web (copié par construire.py) ; en développement : interface\\dist (npm run build)."""
    livre = dossiers.CODE / "fenetre" / "web"
    return livre if livre.is_dir() else dossiers.CODE.parent / "interface" / "dist"


def appelant(request) -> str | None:
    """« fenetre » si le cookie porte le jeton de la fenêtre (et l'en-tête pour une écriture), sinon None."""
    j = request.COOKIES.get(COOKIE, "")
    if jetons.APPELANTS.get(j) != "fenetre":
        return None
    return "fenetre" if request.method in ("GET", "HEAD") or request.headers.get("X-Fabrique") == "fenetre" else None


@require_GET
def entree(request):
    """Seulement en local (jamais par Tailscale) ; « vers » : un chemin de l'interface (/#/…), jamais une autre adresse."""
    if request.get_host().split(":")[0] not in LOCAL or jetons.APPELANTS.get(request.GET.get("j", "")) != "fenetre":
        return HttpResponse("Entrée refusée.", status=403, content_type="text/plain; charset=utf-8")
    vers = request.GET.get("vers", "/")
    p = urlsplit(vers)
    r = HttpResponseRedirect(vers if vers.startswith("/") and not vers.startswith("//") and not p.netloc else "/")
    r.set_cookie(COOKIE, request.GET["j"], httponly=True, samesite="Strict")
    r["Cache-Control"] = "no-store"
    return r


@require_GET
def page(request, chemin: str = ""):
    """Un fichier construit (assets\\… : gardé en cache, son nom change à chaque construction) ou index.html pour toute autre adresse."""
    racine = web().resolve()
    f = (racine / chemin).resolve() if chemin else racine / "index.html"
    if not f.is_relative_to(racine) or not f.is_file():
        f = racine / "index.html"
    if not f.is_file():
        return HttpResponse("Interface absente : construire interface\\ (npm run build).", status=503, content_type="text/plain; charset=utf-8")
    r = FileResponse(f.open("rb"), content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")
    r["Cache-Control"] = "public, max-age=31536000, immutable" if f.parent.name == "assets" else "no-cache"
    for k, v in SURETE.items():
        r[k] = v
    return r


def image(chemin: Path, largeur: int | None = None):
    """L'image entière, ou réduite à `largeur` (JPEG gardé dans donnees\\cache\\images, refait si l'original change)."""
    if not chemin.is_file():
        raise Http404("image absente")
    if not largeur:
        return _cache(FileResponse(chemin.open("rb"), content_type=mimetypes.guess_type(chemin.name)[0] or "image/png"))
    largeur = next((l for l in LARGEURS if l >= largeur), LARGEURS[-1])
    st = chemin.stat()
    cle = hashlib.sha1(f"{chemin}|{st.st_mtime_ns}|{st.st_size}|{largeur}".encode()).hexdigest()
    cache = settings.DONNEES / "cache" / "images" / f"{cle}.jpg"
    if not cache.is_file():
        from PIL import Image

        cache.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(chemin) as im:
            im.thumbnail((largeur, largeur * 4))
            tmp = cache.with_suffix(".tmp")
            im.convert("RGB").save(tmp, "JPEG", quality=86, optimize=True)
            tmp.replace(cache)
    return _cache(FileResponse(cache.open("rb"), content_type="image/jpeg"))


def _cache(r):
    r["Cache-Control"] = "private, max-age=3600"
    return r


PLAGE = re.compile(r"bytes=(\d*)-(\d*)$")
MORCEAU = 1 << 20


def media(request, chemin: Path):
    """Un son ou une vidéo, par morceaux si le lecteur le demande (Range) : sans cela, impossible de sauter dans la vidéo."""
    if not chemin.is_file():
        raise Http404("fichier absent")
    taille = chemin.stat().st_size
    genre = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    m = PLAGE.match(request.headers.get("Range", "").strip())
    if not m or (not m[1] and not m[2]):
        r = FileResponse(chemin.open("rb"), content_type=genre)
        r["Accept-Ranges"] = "bytes"
        return r
    debut, fin = (int(m[1]), int(m[2]) if m[2] else taille - 1) if m[1] else (max(0, taille - int(m[2])), taille - 1)
    fin = min(fin, taille - 1)
    if debut > fin:
        r = HttpResponse(status=416)
        r["Content-Range"] = f"bytes */{taille}"
        return r

    def lire():
        with chemin.open("rb") as f:
            f.seek(debut)
            reste = fin - debut + 1
            while reste > 0 and (bloc := f.read(min(MORCEAU, reste))):
                reste -= len(bloc)
                yield bloc

    r = StreamingHttpResponse(lire(), status=206, content_type=genre)
    r["Content-Range"] = f"bytes {debut}-{fin}/{taille}"
    r["Content-Length"] = str(fin - debut + 1)
    r["Accept-Ranges"] = "bytes"
    return r
