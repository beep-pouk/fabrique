import { ArrowRight, CalendarDays, CircleCheck, Moon, TriangleAlert } from "lucide-react";
import { useLire, type ElementCalendrier, type Etat, type Script } from "../api";
import { aller, dateLongue, joursAvant, quand, salutation } from "../outils";
import { useStudio } from "../studio";
import { Bouton, Carte, EnTete, Image, Squelette } from "../ui";
import { CarteEpisode } from "./Episodes";
import { CarteBramble, useImageEpisode, type BrambleEnCours } from "./File";

const A_FAIRE: Record<string, string> = { a_verifier: "Vidéo à regarder et approuver", approuvee: "Vidéo prête à publier", reportee: "Épisode reporté : nouvelle date à choisir" };

export function Accueil() {
  const { session } = useStudio();
  const { donnees: scripts } = useLire<Script[]>(session ? `/sessions/${session.id}/scripts` : null);
  const { donnees: calendrier } = useLire<ElementCalendrier[]>("/calendrier", 30000);
  const { donnees: etat } = useLire<Etat>("/etat", 15000);
  const { donnees: bramble } = useLire<BrambleEnCours>("/bramble/en-cours", 15000);

  const episodes = (scripts ?? []).filter((s) => !s.code.includes("."));
  const a_venir = episodes.filter((s) => s.date_prevue && joursAvant(s.date_prevue) >= 0);
  const prochain = a_venir[0] ?? episodes[0];
  const taches = (calendrier ?? []).filter((c) => A_FAIRE[c.statut]);
  const alertes = etat?.alertes ?? [];
  const aujourdhui = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <>
      <EnTete surtitre={aujourdhui} titre={salutation()} sous={session && !session.essais ? session.nom : undefined} />

      {scripts ? prochain ? <Vedette script={prochain} /> : null : <Squelette className="mb-10 h-[420px]" />}

      <div className="mb-12 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        <section>
          <h2 className="mb-4 text-[17px] font-semibold">Ce qui vous attend</h2>
          {!calendrier || !etat ? (
            <Squelette className="h-[200px]" />
          ) : taches.length || alertes.length ? (
            <div className="flex flex-col gap-2">
              {alertes.map((a) => (
                <div key={a} className="flex items-start gap-3 rounded-[12px] border border-rouge/25 bg-rouge-sombre/50 px-4 py-3.5 text-[14px]">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-rouge" /> {a}
                </div>
              ))}
              {taches.map((t) => (
                <button
                  key={t.session + t.code}
                  onClick={() => aller("episode", t.session, t.code)}
                  className="flex items-center gap-4 rounded-[12px] border border-ligne bg-carte px-4 py-3 text-left transition-colors hover:border-ligne-forte hover:bg-carte-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] font-medium">{t.titre}</div>
                    <div className="text-[12px] text-ambre-vif">{A_FAIRE[t.statut]}</div>
                  </div>
                  <ArrowRight className="size-4 text-pale" />
                </button>
              ))}
            </div>
          ) : (
            <Carte className="flex h-[calc(100%-44px)] min-h-[200px] flex-col items-center justify-center gap-3 p-8 text-center">
              <div className="grid size-12 place-items-center rounded-2xl bg-vert-sombre text-vert">
                <CircleCheck className="size-6" />
              </div>
              <div className="text-[16px] font-medium">Rien ne vous attend</div>
              <div className="max-w-xs text-[13px] leading-relaxed text-doux">Aucune vidéo à regarder ni à publier. Tout est à jour.</div>
            </Carte>
          )}
        </section>
        <section>
          <h2 className="mb-4 text-[17px] font-semibold">À l'atelier</h2>
          {!bramble ? (
            <Squelette className="h-[260px]" />
          ) : bramble.actif ? (
            <CarteBramble etat={bramble} compacte />
          ) : (
            <Carte className="flex h-[calc(100%-44px)] min-h-[200px] items-center gap-5 bg-[radial-gradient(ellipse_at_10%_0%,#1c2433,#151920_60%)] p-8">
              <div className="grid size-12 place-items-center rounded-2xl bg-ambre-sombre text-ambre-vif">
                <Moon className="size-5" />
              </div>
              <div>
                <div className="text-[17px] font-semibold">L'atelier est au repos</div>
                <div className="mt-1 text-[13px] text-doux">Rien ne se fabrique en ce moment.</div>
              </div>
            </Carte>
          )}
        </section>
      </div>

      {a_venir.length > 1 && (
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[17px] font-semibold">Prochains épisodes</h2>
            <a href="#/episodes" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-doux hover:text-texte">
              Tous les épisodes <ArrowRight className="size-4" />
            </a>
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-6">
            {a_venir.slice(1, 5).map((s) => (
              <CarteEpisode key={s.code} script={s} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function Vedette({ script }: { script: Script }) {
  const { session } = useStudio();
  const image = useImageEpisode(script.code, script.vignette);
  const numero = /e(\d+)$/i.exec(script.code)?.[1];
  const ouvrir = () => session && aller("episode", session.id, script.code);
  return (
    <section className="group relative mb-12 cursor-pointer overflow-hidden rounded-[22px] ring-1 ring-ligne" onClick={ouvrir}>
      <Image chemin={image} largeur={1280} className="h-[clamp(320px,46vh,460px)] w-full transition-transform duration-[1.2s] ease-out group-hover:scale-[1.02]" />
      <div className="absolute inset-0 bg-gradient-to-r from-[#07090c]/95 via-[#07090c]/55 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#07090c]/70 via-transparent to-transparent" />
      <div className="absolute inset-0 flex max-w-[720px] flex-col justify-end p-12">
        <div className="mb-3 text-[12px] font-semibold tracking-[0.16em] text-ambre-vif uppercase">
          {script.date_prevue && joursAvant(script.date_prevue) >= 0 ? `Prochain épisode · ${quand(script.date_prevue)}` : "Épisode"}
        </div>
        <h2 className="titre-image text-[44px] leading-[1.05] font-semibold tracking-[-0.028em] text-balance">{script.titre}</h2>
        <div className="titre-image mt-4 flex items-center gap-4 text-[14px] text-white/75">
          {numero && <span>Épisode {Number(numero)}</span>}
          {script.date_prevue && (
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="size-4" /> {dateLongue(script.date_prevue)}
            </span>
          )}
        </div>
        <div className="mt-7 flex gap-3">
          <Bouton genre="principal" icone={<ArrowRight className="size-4" />} onClick={ouvrir} className="h-11 px-5 text-[15px]">
            Ouvrir la planche
          </Bouton>
        </div>
      </div>
    </section>
  );
}
