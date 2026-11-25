// Essais d'animation (étape 2) : la même scène par Bramble Studio et par Fabrique, côte à côte, lues ensemble (un seul son, une seule frise).
import { Pause, Play, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { fichier, type Comparaison as Essai } from "../api";
import { duree, horloge } from "../outils";
import { Bouton, cx } from "../ui";

export function Comparaisons({ essais }: { essais: Essai[] }) {
  const [choisi, setChoisi] = useState(0);
  if (!essais.length) return null;
  const e = essais[Math.min(choisi, essais.length - 1)];
  return (
    <section className="mb-10">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-[12px] font-semibold tracking-[0.1em] text-ambre-vif uppercase">
            <Sparkles className="size-3.5" /> Essai d'animation
          </div>
          <h2 className="text-[20px] font-semibold">{e.titre}</h2>
          <p className="mt-1 text-[14px] text-doux">
            {e.plans.length} plans animés de {duree(Math.min(...e.plans.map((p) => p.duree)))} à {duree(Math.max(...e.plans.map((p) => p.duree)))}, à côté de la même
            scène dans la vidéo de Bramble Studio.
          </p>
        </div>
        {essais.length > 1 && (
          <div className="flex gap-1">
            {essais.map((x, i) => (
              <button key={x.dossier} onClick={() => setChoisi(i)} className={cx("h-9 rounded-[10px] px-3 text-[13px]", i === choisi ? "bg-survol font-medium" : "text-doux hover:bg-carte-2")}>
                Essai {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>
      <CoteACote key={e.dossier} e={e} />
    </section>
  );
}

function CoteACote({ e }: { e: Essai }) {
  const gauche = useRef<HTMLVideoElement>(null);
  const droite = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0);
  const [joue, setJoue] = useState(false);
  const fin = e.duree || 1;
  const courant = e.plans.findIndex((p) => t >= p.debut && t < p.debut + p.duree);

  useEffect(() => {
    if (!joue) return;
    let id = 0;
    const pas = () => {
      const d = droite.current;
      const g = gauche.current;
      if (d && g) {
        if (Math.abs(g.currentTime - d.currentTime) > 0.08) g.currentTime = d.currentTime; // une seule horloge : celle de Fabrique (le son)
        setT(d.currentTime);
      }
      id = requestAnimationFrame(pas);
    };
    id = requestAnimationFrame(pas);
    return () => cancelAnimationFrame(id);
  }, [joue]);

  const basculer = useCallback(() => {
    const d = droite.current;
    const g = gauche.current;
    if (!d || !g) return;
    if (d.paused) {
      g.currentTime = d.currentTime;
      void Promise.all([d.play(), g.play()]).catch(() => undefined);
    } else {
      d.pause();
      g.pause();
    }
  }, []);
  const aller = (s: number) => {
    for (const v of [gauche.current, droite.current]) if (v) v.currentTime = Math.max(0, Math.min(s, fin - 0.05));
    setT(Math.max(0, Math.min(s, fin)));
  };

  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        {[
          { ref: gauche, src: e.bramble, nom: "Bramble Studio", sous: "images fixes et calques", muet: true },
          { ref: droite, src: e.fabrique, nom: "Fabrique", sous: "personnages animés", muet: false },
        ].map((c) => (
          <figure key={c.nom} className="relative overflow-hidden rounded-[14px] bg-black ring-1 ring-ligne">
            <video
              ref={c.ref}
              src={`${fichier(c.src)}#t=0.1`} // une image dès l'ouverture, avant la lecture
              muted={c.muet}
              preload="auto"
              playsInline
              onClick={basculer}
              onPlay={() => !c.muet && setJoue(true)}
              onPause={() => !c.muet && setJoue(false)}
              onEnded={() => !c.muet && setJoue(false)}
              className="aspect-video w-full cursor-pointer bg-black"
            />
            <figcaption className="titre-image pointer-events-none absolute top-3 left-4 text-[13px] font-semibold text-white">
              {c.nom} <span className="font-normal text-white/70">· {c.sous}</span>
            </figcaption>
          </figure>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Bouton genre="principal" aria-label={joue ? "Pause" : "Lire les deux"} onClick={basculer} icone={joue ? <Pause className="size-4" /> : <Play className="size-4" />}>
          {joue ? "Pause" : "Lire les deux"}
        </Bouton>
        <span className="text-[13px] text-doux tabular-nums">
          {horloge(t)} <span className="text-pale">/ {horloge(fin)}</span>
        </span>
        {courant >= 0 && <span className="ml-auto text-[13px] text-doux">Plan {courant + 1} sur {e.plans.length} · {duree(e.plans[courant].duree)}</span>}
      </div>
      <div
        className="relative mt-3 flex h-3 cursor-pointer gap-[2px] overflow-hidden rounded-full"
        onClick={(x) => {
          const b = x.currentTarget.getBoundingClientRect();
          aller(((x.clientX - b.left) / b.width) * fin);
        }}
      >
        {e.plans.map((p, i) => (
          <div key={i} style={{ flexGrow: p.duree }} className={cx("basis-0", i === courant ? "bg-ambre" : i < courant ? "bg-ambre/45" : "bg-carte-2")} />
        ))}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: `${(t / fin) * 100}%` }} />
      </div>
    </div>
  );
}
