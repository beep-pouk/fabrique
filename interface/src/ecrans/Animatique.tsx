// L'animatique : l'épisode entier en images fixes, avec ses voix et sa musique (monté par le noyau sur le processeur), pour juger le rythme
// avant toute animation. Frise des plans (images, durées réelles à l'écran), notes à la seconde, raccourcis : Espace, ← →, N.
import * as Infobulle from "@radix-ui/react-tooltip";
import { Clapperboard, Loader2, MessageSquarePlus, Pause, Play, RotateCcw, SkipBack, SkipForward, Trash2, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { agir, fichier, useLire, type Animatique as EtatAnimatique } from "../api";
import { duree, horloge, MAX_IMAGE_S, nomLangue, VALEURS, type PlanLu } from "../outils";
import { Bouton, cx, Erreur, Image, Pastille, recadrer, Squelette, Vide } from "../ui";
import { AnimationPlan } from "./AnimationPlan";

export function Animatique({ session, code, langue, plans, imageDe }: { session: string; code: string; langue: string; plans: PlanLu[]; imageDe(p: PlanLu): string | undefined }) {
  const chemin = `/sessions/${encodeURIComponent(session)}/scripts/${encodeURIComponent(code)}/animatique`;
  const [suivre, setSuivre] = useState(false);
  const { donnees: a, erreur, relire } = useLire<EtatAnimatique>(`${chemin}?langue=${encodeURIComponent(langue)}`, suivre ? 2000 : 0);
  const [charge, setCharge] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => setSuivre(a?.etat === "en_cours" || !!a?.autre), [a?.etat, a?.autre]);

  async function monter() {
    setCharge(true);
    setMessage("");
    try {
      await agir(`${chemin}?langue=${encodeURIComponent(langue)}`);
      setSuivre(true);
      await relire();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setCharge(false);
    }
  }

  if (!a) return erreur ? <Erreur texte={erreur} /> : <Squelette className="aspect-video w-full" />;
  const enCours = a.etat === "en_cours";
  const bouton = (
    <Bouton genre={a.video ? "second" : "principal"} icone={a.video ? <RotateCcw className="size-4" /> : <Clapperboard className="size-4" />} charge={charge} disabled={enCours || a.autre} onClick={monter}>
      {a.video ? "Remonter" : "Monter l'animatique"}
    </Bouton>
  );
  return (
    <div className="flex flex-col gap-5">
      {(enCours || a.autre) && <Avancee fait={a.fait} tout={a.tout} autre={a.autre && !enCours} />}
      {a.etat === "erreur" && <Erreur texte={`L'animatique n'a pas pu être montée : ${a.message}`} />}
      {message && <Erreur texte={message} />}
      {a.video ? (
        <Lecteur a={a} chemin={chemin} langue={langue} plans={plans} imageDe={imageDe} relire={relire} bouton={bouton} animation={chemin.replace(/animatique$/, "animation")} />
      ) : (
        !enCours && (
          <Vide
            icone={<Clapperboard className="size-5" />}
            titre={`Pas encore d'animatique en ${nomLangue(langue).toLowerCase()}`}
            texte="L'épisode entier en images fixes, avec les voix et la musique, pour juger le rythme avant l'animation. Quelques minutes sur le processeur : la carte graphique reste à Bramble Studio."
          >
            <div className="mt-2">{bouton}</div>
          </Vide>
        )
      )}
    </div>
  );
}

function Avancee({ fait, tout, autre }: { fait: number; tout: number; autre: boolean }) {
  const part = tout ? Math.min(1, fait / tout) : 0;
  return (
    <div role="status" className="flex items-center gap-4 rounded-carte border border-ligne bg-carte px-5 py-4">
      <Loader2 className="size-5 shrink-0 animate-spin text-ambre" />
      <div className="flex-1">
        <div className="text-[14px] font-medium">{autre ? "Une autre animatique se monte : relancez celle-ci quand elle sera finie." : "L'animatique se monte…"}</div>
        {!autre && (
          <div role="progressbar" aria-label="Montage de l'animatique" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(part * 100)} className="mt-2 h-1.5 overflow-hidden rounded-full bg-carte-2">
            <div className="h-full rounded-full bg-ambre transition-[width] duration-500" style={{ width: `${Math.max(3, part * 100)}%` }} />
          </div>
        )}
      </div>
      {!autre && tout > 0 && <span className="text-[13px] text-doux tabular-nums">{Math.round(part * 100)} %</span>}
    </div>
  );
}

function Lecteur({ a, chemin, langue, plans, imageDe, relire, bouton, animation }: {
  a: EtatAnimatique; chemin: string; langue: string; plans: PlanLu[]; imageDe(p: PlanLu): string | undefined; relire(): Promise<void>; bouton: React.ReactNode; animation: string;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const champ = useRef<HTMLInputElement>(null);
  const racine = useRef<HTMLDivElement>(null);
  const [t, setT] = useState(0);
  const [joue, setJoue] = useState(false);
  const [note, setNote] = useState("");
  const [tNote, setTNote] = useState<number | null>(null);
  const [erreur, setErreur] = useState("");
  const [occupe, setOccupe] = useState(false); // un appel à la fois : ni note en double, ni double retrait
  const parN = new Map(plans.map((p) => [p.n, p]));
  const reperes = a.plans.map((r, i) => ({ ...r, numero: parN.get(r.n)?.numero ?? i + 1, plan: parN.get(r.n) }));
  const fin = a.fin || reperes.reduce((s, r) => s + r.duree, 0) || 1;
  const courant = reperes.findIndex((r) => t >= r.debut && t < r.debut + r.duree);
  const r = reperes[courant];
  const longs = reperes.filter((x) => x.duree > MAX_IMAGE_S && !x.plan?.bramble).length;
  const affiche = reperes[0]?.plan && imageDe(reperes[0].plan);
  const ici = a.notes.filter((n) => n.langue === langue); // une seconde ne vaut que dans sa langue (voix de longueurs différentes)

  useEffect(() => {
    setJoue(false); // nouvelle vidéo (remontée, autre langue) : l'ancien élément est parti sans dire « pause »
    setT(0);
    setNote(""); // une note commencée tombait à la seconde de l'autre vidéo
    setTNote(null);
  }, [a.video]);

  useEffect(() => {
    // l'onglet cliqué garde le focus : Espace et les flèches iraient aux onglets (→ ouvrirait Vidéo) au lieu du lecteur
    if ((document.activeElement as HTMLElement | null)?.closest("[role=tab]")) racine.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (!joue) return;
    let id = 0;
    const pas = () => {
      setT(video.current?.currentTime ?? 0);
      id = requestAnimationFrame(pas);
    };
    id = requestAnimationFrame(pas);
    return () => cancelAnimationFrame(id);
  }, [joue]);

  const aller = useCallback((s: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(s, fin - 0.05));
    setT(v.currentTime);
  }, [fin]);
  const basculer = useCallback(() => {
    const v = video.current;
    if (v) void (v.paused ? v.play().catch(() => undefined) : v.pause());
  }, []);
  const voisin = useCallback((pas: number) => {
    const i = courant < 0 ? (pas > 0 ? 0 : reperes.length - 1) : Math.max(0, Math.min(reperes.length - 1, courant + pas));
    if (reperes[i]) aller(reperes[i].debut + 0.01);
  }, [courant, reperes, aller]);

  useEffect(() => {
    const touche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement | null;
      if (e.defaultPrevented || e.ctrlKey || e.altKey || e.metaKey || cible?.closest("input, textarea, [contenteditable=true], [role=menu], [role=dialog], [role=tab]")) return;
      if (e.key === " " && cible?.closest("button, a")) return; // Espace active le bouton qui a le focus
      if (e.key === " ") basculer();
      else if (e.key === "ArrowLeft") voisin(-1);
      else if (e.key === "ArrowRight") voisin(1);
      else if (e.key === "n" || e.key === "N") champ.current?.focus();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [basculer, voisin]);

  async function ajouter(e: FormEvent) {
    e.preventDefault();
    if (!note.trim() || occupe) return;
    setErreur("");
    setOccupe(true);
    try {
      await agir(`${chemin}/notes`, { t: tNote ?? t, texte: note, langue });
      setNote("");
      setTNote(null);
      champ.current?.blur();
      await relire();
    } catch (x) {
      setErreur(x instanceof Error ? x.message : String(x));
    } finally {
      setOccupe(false);
    }
  }

  async function retirer(id: string) {
    if (occupe) return;
    setErreur("");
    setOccupe(true);
    try {
      await agir(`${chemin}/notes/${encodeURIComponent(id)}/retirer`);
      await relire();
    } catch (x) {
      setErreur(x instanceof Error ? x.message : String(x));
    } finally {
      setOccupe(false);
    }
  }

  return (
    <div ref={racine} tabIndex={-1} className="grid gap-6 outline-none xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0">
        {a.perimee && (
          <div className="mb-4 flex items-center gap-2 rounded-[12px] border border-ambre/30 bg-ambre-sombre px-4 py-3 text-[14px] text-ambre-vif">
            <TriangleAlert className="size-4 shrink-0" /> Le script a changé depuis ce montage : remontez l'animatique pour voir la nouvelle version.
          </div>
        )}
        <div className="group relative overflow-hidden rounded-[16px] bg-black ring-1 ring-ligne">
          <video
            ref={video}
            key={a.video}
            src={fichier(a.video)}
            preload="auto"
            poster={affiche ? fichier(affiche, 1280) : undefined}
            className="aspect-video w-full cursor-pointer bg-black"
            onClick={basculer}
            onPlay={() => setJoue(true)}
            onPause={() => setJoue(false)}
            onEnded={() => setJoue(false)}
            onSeeked={(e) => setT(e.currentTarget.currentTime)}
            onTimeUpdate={(e) => !joue && setT(e.currentTarget.currentTime)}
          />
          {!joue && (
            <button onClick={basculer} aria-label="Lire" className="absolute inset-0 grid place-items-center bg-black/10 transition-colors hover:bg-black/20">
              <span className="grid size-16 place-items-center rounded-full bg-black/55 text-white ring-1 ring-white/15 backdrop-blur-md">
                <Play className="ml-1 size-7 fill-current" />
              </span>
            </button>
          )}
          {r && (
            <div className="titre-image pointer-events-none absolute top-4 left-5 text-[13px] font-semibold text-white">
              Plan {r.numero} <span className="font-normal text-white/70">{VALEURS[r.valeur ?? ""] ? `· ${VALEURS[r.valeur ?? ""]}` : `sur ${plans.length}`}</span>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Bouton genre="discret" aria-label="Plan précédent" onClick={() => voisin(-1)} icone={<SkipBack className="size-4" />} className="w-10 px-0" />
          <Bouton genre="second" aria-label={joue ? "Pause" : "Lire"} onClick={basculer} icone={joue ? <Pause className="size-4" /> : <Play className="size-4" />} className="w-12 px-0" />
          <Bouton genre="discret" aria-label="Plan suivant" onClick={() => voisin(1)} icone={<SkipForward className="size-4" />} className="w-10 px-0" />
          <span className="ml-2 text-[13px] text-doux tabular-nums">
            {horloge(t)} <span className="text-pale">/ {horloge(fin)}</span>
          </span>
          <span className="ml-auto flex items-center gap-3">
            {longs > 0 ? (
              <Pastille ton="ambre">
                <TriangleAlert className="size-3.5" /> {longs} plan{longs > 1 ? "s restent" : " reste"} plus de {MAX_IMAGE_S} s
              </Pastille>
            ) : (
              <Pastille ton="vert">Aucun plan plus de {MAX_IMAGE_S} s</Pastille>
            )}
            {bouton}
          </span>
        </div>

        <Frise reperes={reperes} fin={fin} t={t} courant={courant} notes={ici} aller={aller} imageDe={imageDe} />
        <div className="mt-2 flex justify-between text-[11px] text-pale tabular-nums">
          <span>0:00</span>
          <span>
            Montée le {new Date(a.date).toLocaleDateString("fr-FR", { day: "numeric", month: "long" })} à{" "}
            {new Date(a.date).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} · voix en {nomLangue(langue).toLowerCase()}
          </span>
          <span>{horloge(fin)}</span>
        </div>
      </div>

      <aside className="flex min-h-0 flex-col gap-4">
        <div className="overflow-hidden rounded-carte border border-ligne bg-carte">
          {r?.plan ? (
            <>
              <Image chemin={imageDe(r.plan)} largeur={1280} cadre={r.cadre} className="aspect-video" />
              <div className="p-4">
                <div className="mb-1.5 flex items-center justify-between text-[13px]">
                  <span className="font-medium">Plan {r.numero}{VALEURS[r.valeur ?? ""] && <span className="font-normal text-doux"> · {VALEURS[r.valeur ?? ""]}</span>}</span>
                  <span className={cx("tabular-nums", r.duree > MAX_IMAGE_S && !r.plan.bramble ? "font-semibold text-ambre-vif" : "text-doux")}>{duree(r.duree)} à l'écran</span>
                </div>
                <p className="line-clamp-4 text-[14px] leading-relaxed text-texte/90">{r.plan.texte || <span className="text-pale">Aucun texte dit.</span>}</p>
              </div>
            </>
          ) : (
            <div className="p-4 text-[14px] text-doux">{t > 0 && courant < 0 ? "Fin de l'épisode : la musique continue." : "Lancez la lecture : le plan en cours s'affiche ici."}</div>
          )}
        </div>

        {r?.cle && r.valeur !== "bramble" && !r.plan?.bramble && (
          <AnimationPlan chemin={animation} langue={langue} cle={r.cle} numero={r.numero} pause={() => video.current?.pause()} />
        )}

        <div className="flex min-h-0 flex-1 flex-col rounded-carte border border-ligne bg-carte">
          <div className="flex items-center justify-between border-b border-ligne px-4 py-3">
            <span className="text-[14px] font-medium">Notes</span>
            <span className="text-[12px] text-pale">{a.notes.length || "aucune"}</span>
          </div>
          <form onSubmit={ajouter} className="flex items-center gap-2 border-b border-ligne p-3">
            <input
              ref={champ}
              value={note}
              maxLength={500}
              onChange={(e) => setNote(e.target.value)}
              onFocus={() => {
                video.current?.pause();
                setTNote(video.current?.currentTime ?? t);
              }}
              onKeyDown={(e) => e.key === "Escape" && (setNote(""), setTNote(null), e.currentTarget.blur())}
              aria-label="Nouvelle note, au moment de la pause"
              placeholder={`Note à ${horloge(tNote ?? t)}… (N)`}
              className="h-10 min-w-0 flex-1 rounded-[10px] border border-ligne-forte bg-carte-2 px-3 text-[14px] outline-none placeholder:text-pale focus:border-ambre/60"
            />
            <Bouton type="submit" genre="second" aria-label="Ajouter la note" disabled={!note.trim()} charge={occupe} icone={<MessageSquarePlus className="size-4" />} className="w-10 px-0" />
          </form>
          {erreur && <div className="px-4 pt-3 text-[13px] text-rouge">{erreur}</div>}
          <ol className="flex max-h-[420px] flex-col overflow-y-auto p-1.5">
            {a.notes.map((n, i) => (
              <li key={n.id || i} className="group flex items-start gap-3 rounded-[10px] px-2.5 py-2 hover:bg-survol">
                <button
                  onClick={() => aller(n.t)}
                  disabled={n.langue !== langue}
                  aria-label={`Aller à ${horloge(n.t)}`}
                  className="mt-px shrink-0 rounded-md bg-ambre-sombre px-1.5 py-0.5 text-[12px] font-semibold text-ambre-vif tabular-nums disabled:bg-carte-2 disabled:text-pale"
                >
                  {horloge(n.t)}
                </button>
                <div className="copiable min-w-0 flex-1 text-[14px] leading-snug text-texte/90">
                  {n.texte}
                  {n.langue !== langue && <span className="ml-1.5 text-[12px] text-pale">(voix en {nomLangue(n.langue).toLowerCase()})</span>}
                  {n.ancienne && <span className="ml-1.5 text-[12px] text-pale">(version précédente du script)</span>}
                </div>
                <button onClick={() => n.id && retirer(n.id)} disabled={occupe || !n.id} aria-label="Retirer la note" className="shrink-0 rounded-md p-1 text-pale opacity-0 transition-opacity group-hover:opacity-100 hover:text-rouge focus:opacity-100">
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
            {!a.notes.length && <li className="px-3 py-6 text-center text-[13px] leading-relaxed text-pale">Mettez la vidéo en pause au bon moment et écrivez ce qui ne va pas : la note garde la seconde.</li>}
          </ol>
        </div>
      </aside>
    </div>
  );
}

type Repere = EtatAnimatique["plans"][number] & { numero: number; plan?: PlanLu };

function Frise({ reperes, fin, t, courant, notes, aller, imageDe }: {
  reperes: Repere[]; fin: number; t: number; courant: number; notes: EtatAnimatique["notes"]; aller(s: number): void; imageDe(p: PlanLu): string | undefined;
}) {
  const zone = useRef<HTMLDivElement>(null);
  const cliquer = (e: React.MouseEvent) => {
    const b = zone.current?.getBoundingClientRect();
    if (b) aller(((e.clientX - b.left) / b.width) * fin);
  };
  const queue = fin - reperes.reduce((s, r) => s + r.duree, 0);
  const passages: Repere[] = []; // une image par passage (ses plans se suivent dessus) : des vignettes assez larges pour se voir
  for (const r of reperes) {
    const d = passages[passages.length - 1];
    if (d && d.n === r.n && Math.abs(d.debut + d.duree - r.debut) < 0.05) passages[passages.length - 1] = { ...d, duree: d.duree + r.duree };
    else passages.push(r);
  }
  return (
    <div className="relative mt-5 pt-3">
      {notes.map((n, i) => (
        <span key={n.id || i} className="absolute top-0 z-10 size-2 -translate-x-1/2 rounded-full bg-ambre-vif shadow-[0_0_0_2px_#0b0d10]" style={{ left: `${Math.min(100, (n.t / fin) * 100)}%` }} />
      ))}
      <div ref={zone} onClick={cliquer} className="relative flex h-16 cursor-pointer overflow-hidden rounded-[10px] bg-[#2b333f]">
        {passages.map((p, i) => {
          const image = p.plan && imageDe(p.plan);
          return image && p.duree > fin / 120 ? (
            <img key={i} src={fichier(image, 320)} alt="" style={{ left: `${(p.debut / fin) * 100}%`, width: `${(p.duree / fin) * 100}%` }} className="absolute inset-y-0 h-full object-cover opacity-70" />
          ) : null;
        })}
        {reperes.map((r, i) => {
          const long = r.duree > MAX_IMAGE_S && !r.plan?.bramble;
          return (
            <Infobulle.Root key={i}>
              <Infobulle.Trigger asChild>
                <div style={{ flexGrow: r.duree }} className={cx("relative min-w-px basis-0 border-r border-black/70", long && "bg-ambre/70", i === courant && "bg-white/15 ring-2 ring-white ring-inset")}>
                  {r.anime && <span className="absolute inset-x-0 bottom-0 h-1 bg-vert" />}
                </div>
              </Infobulle.Trigger>
              <Infobulle.Portal>
                <Infobulle.Content sideOffset={6} className="z-50 overflow-hidden rounded-lg border border-ligne-forte bg-carte-2 text-[12px] shadow-haut">
                  {r.plan && r.cadre && (
                    <div className="relative aspect-video w-48 overflow-hidden">
                      <img src={fichier(imageDe(r.plan) ?? "", 640)} alt="" style={recadrer(r.cadre)} className="absolute object-cover" />
                    </div>
                  )}
                  <div className="px-3 py-2">
                    Plan {r.numero}
                    {VALEURS[r.valeur ?? ""] && ` · ${VALEURS[r.valeur ?? ""]}`} · {horloge(r.debut)} · {duree(r.duree)}
                    {long && <span className="text-ambre-vif"> · trop long</span>}
                    {r.anime && <span className="text-vert"> · animé</span>}
                  </div>
                </Infobulle.Content>
              </Infobulle.Portal>
            </Infobulle.Root>
          );
        })}
        {queue > 0.5 && <div style={{ flexGrow: queue }} className="basis-0 bg-[repeating-linear-gradient(135deg,#1a1f27_0_6px,#151920_6px_12px)]" title="Fin musicale" />}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow-[0_0_8px_rgb(255_255_255/0.6)]" style={{ left: `${(t / fin) * 100}%` }} />
      </div>
    </div>
  );
}
