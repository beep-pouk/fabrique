import { CalendarDays, Clapperboard } from "lucide-react";
import { useLire, type RendusBramble, type Script } from "../api";
import { aller, dateCourte, imageEpisode, joursAvant, quand, STATUTS } from "../outils";
import { useStudio } from "../studio";
import { cx, EnTete, Erreur, Image, Pastille, Squelette, Vide } from "../ui";

export function Episodes() {
  const { session } = useStudio();
  const { donnees, erreur } = useLire<Script[]>(session ? `/sessions/${session.id}/scripts` : null);
  const episodes = (donnees ?? []).filter((s) => !s.code.includes("."));
  const prochain = episodes.find((s) => s.date_prevue && joursAvant(s.date_prevue) >= 0);
  const saisons = new Map<string, Script[]>();
  for (const e of episodes) {
    const s = /^s(\d+)e/i.exec(e.code)?.[1];
    const cle = s ? `Saison ${Number(s)}` : "Épisodes";
    saisons.set(cle, [...(saisons.get(cle) ?? []), e]);
  }

  return (
    <>
      <EnTete
        surtitre={session?.essais ? "Essais" : session?.nom}
        titre="Épisodes"
        sous={
          donnees &&
          (episodes.length
            ? `${episodes.length} épisode${episodes.length > 1 ? "s" : ""}${prochain ? ` · prochain ${quand(prochain.date_prevue)}` : ""}`
            : undefined)
        }
      />
      {erreur && <Erreur texte={erreur} />}
      {!donnees && !erreur && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
          {Array.from({ length: 8 }, (_, i) => (
            <Squelette key={i} className="aspect-[16/12]" />
          ))}
        </div>
      )}
      {donnees && !episodes.length && (
        <Vide icone={<Clapperboard className="size-5" />} titre="Aucun épisode pour l'instant" texte="Les scripts de cette série apparaîtront ici, chacun avec ses images." />
      )}
      {[...saisons].map(([nom, liste]) => (
        <section key={nom} className="mb-10">
          {saisons.size > 1 || nom !== "Épisodes" ? <h2 className="mb-4 text-[15px] font-semibold text-doux">{nom}</h2> : null}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-x-6 gap-y-8">
            {liste.map((e) => (
              <CarteEpisode key={e.code} script={e} prochain={e === prochain} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

export function CarteEpisode({ script, prochain, grande }: { script: Script; prochain?: boolean; grande?: boolean }) {
  const { session, portraits } = useStudio();
  const { donnees: rendus } = useLire<RendusBramble>(session ? `/sessions/${session.id}/scripts/${script.code}/bramble?langue=` : null);
  const statut = STATUTS[script.statut] ?? { nom: script.statut, ton: "neutre" as const };
  const numero = /e(\d+)$/i.exec(script.code)?.[1];
  return (
    <button onClick={() => session && aller("episode", session.id, script.code)} className="group flex flex-col justify-start text-left outline-none">
      <div
        className={cx(
          "relative overflow-hidden rounded-carte ring-1 ring-ligne transition-all duration-300 group-hover:ring-ligne-forte group-hover:shadow-haut group-focus-visible:ring-2 group-focus-visible:ring-ambre",
          prochain && "ring-2 ring-ambre/70 group-hover:ring-ambre",
        )}
      >
        <Image
          chemin={imageEpisode(rendus, script.vignette) ?? (rendus && script.personnages.map((n) => portraits[n.toLowerCase()]).find(Boolean))}
          position="50% 30%"
          largeur={grande ? 960 : 640}
          className="aspect-video transition-transform duration-500 ease-out group-hover:scale-[1.035]"
        />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/0 to-black/0" />
        <div className="absolute top-3 left-3 flex gap-2">
          {prochain && <Pastille ton="ambre" className="bg-ambre text-[#1b1406] ring-0">Prochain</Pastille>}
        </div>
        <div className="absolute right-3.5 bottom-3 left-3.5 flex items-end justify-between gap-3 text-[12px] font-medium text-white/90">
          <span className="titre-image">{numero ? `Épisode ${Number(numero)}` : script.code}</span>
          {script.date_prevue && (
            <span className="titre-image inline-flex items-center gap-1.5">
              <CalendarDays className="size-3.5" />
              {dateCourte(script.date_prevue)}
            </span>
          )}
        </div>
      </div>
      <div className="mt-3 px-0.5">
        <div className="line-clamp-2 text-[15px] leading-snug font-medium text-texte transition-colors group-hover:text-white">{script.titre}</div>
        <div className="mt-2">
          <Pastille ton={statut.ton}>{statut.nom}</Pastille>
        </div>
      </div>
    </button>
  );
}
