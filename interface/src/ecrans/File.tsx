import * as Dialogue from "@radix-ui/react-dialog";
import * as Progression from "@radix-ui/react-progress";
import { CircleAlert, CircleCheck, Clock3, Moon, Pause, Play, X } from "lucide-react";
import { useState } from "react";
import { agir, useLire, type Script, type TacheFile } from "../api";
import { duree, imageEpisode, nomLangue } from "../outils";
import { useStudio } from "../studio";
import { Bouton, Carte, cx, EnTete, Erreur, Image, Pastille, Squelette } from "../ui";
import type { RendusBramble } from "../api";

export interface BrambleEnCours {
  actif: boolean;
  code: string;
  langue: string;
  etape: string;
  reste_min: number | null;
  total_min: number | null;
  image: string;
}

const ETAPES: Record<string, string> = {
  voix: "Enregistrement des voix",
  images: "Dessin des images",
  anim: "Animation",
  calques: "Animation",
  bramble: "Bramble à l'écran",
  musique: "Musique",
  montage: "Montage",
  final: "Finitions",
  controle: "Contrôle de la vidéo",
};

export const nomEtape = (e: string) => ETAPES[e] ?? (e ? e.charAt(0).toUpperCase() + e.slice(1) : "Fabrication");

function finVers(minutes: number): string {
  const d = new Date(Date.now() + minutes * 60000);
  const demain = d.getDate() !== new Date().getDate();
  return `${demain ? "demain " : ""}vers ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function Barre({ valeur, className }: { valeur: number; className?: string }) {
  return (
    <Progression.Root value={valeur} className={cx("relative h-2 overflow-hidden rounded-full bg-white/10", className)}>
      <Progression.Indicator
        className="h-full rounded-full bg-gradient-to-r from-ambre to-ambre-vif transition-transform duration-700"
        style={{ transform: `translateX(-${100 - Math.max(2, Math.min(100, valeur))}%)` }}
      />
    </Progression.Root>
  );
}

/** Ce que Bramble Studio fabrique : l'image du plan en cours, l'étape, le temps restant. */
export function CarteBramble({ etat, compacte }: { etat: BrambleEnCours; compacte?: boolean }) {
  const { session } = useStudio();
  const { donnees: scripts } = useLire<Script[]>(session ? `/sessions/${session.id}/scripts` : null);
  const script = scripts?.find((s) => s.code === etat.code);
  const fait = etat.total_min && etat.reste_min != null ? 100 * (1 - etat.reste_min / etat.total_min) : 0;
  return (
    <Carte className={cx("grid overflow-hidden", compacte ? "md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]" : "lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]")}>
      <div className="relative">
        <Image chemin={etat.image} largeur={compacte ? 960 : 1280} className="aspect-video h-full w-full" />
        <span className="absolute top-4 left-4 inline-flex items-center gap-2 rounded-full bg-black/60 px-3 py-1 text-[12px] font-medium text-white backdrop-blur">
          <span className="size-2 animate-pulse rounded-full bg-ambre" /> En direct
        </span>
      </div>
      <div className={cx("flex flex-col justify-center", compacte ? "gap-3 p-7" : "gap-4 p-10")}>
        <div className="text-[12px] font-semibold tracking-[0.14em] text-ambre uppercase">Bramble Studio fabrique</div>
        <div className={cx("font-semibold tracking-[-0.015em] text-balance", compacte ? "text-[20px] leading-snug" : "text-[26px] leading-tight")}>
          {script?.titre ?? etat.code}
        </div>
        <div className="flex flex-wrap gap-2">
          <Pastille>{nomLangue(etat.langue)}</Pastille>
          <Pastille ton="ambre">{nomEtape(etat.etape)}</Pastille>
        </div>
        {etat.reste_min != null && (
          <div className="mt-2">
            <Barre valeur={fait} />
            <div className="mt-2.5 flex justify-between text-[13px] text-doux">
              <span>encore {duree(etat.reste_min * 60)}</span>
              <span>fini {finVers(etat.reste_min)}</span>
            </div>
          </div>
        )}
        {!compacte && (
          <p className="mt-2 text-[13px] leading-relaxed text-pale">
            La carte graphique est à Bramble Studio pendant ses rendus. Les fabrications de Fabrique attendent leur tour et repartent seules ensuite.
          </p>
        )}
      </div>
    </Carte>
  );
}

const ETATS: Record<string, { nom: string; ton: "neutre" | "ambre" | "vert" | "rouge" | "bleu" }> = {
  attente: { nom: "En attente", ton: "neutre" },
  en_cours: { nom: "En cours", ton: "ambre" },
  pause: { nom: "En pause", ton: "bleu" },
  erreur: { nom: "Arrêtée", ton: "rouge" },
  finie: { nom: "Terminée", ton: "vert" },
  annulee: { nom: "Annulée", ton: "neutre" },
};

export function File() {
  const { donnees: bramble } = useLire<BrambleEnCours>("/bramble/en-cours", 15000);
  const { donnees: taches, erreur, relire } = useLire<TacheFile[]>("/file", 5000);
  const actives = (taches ?? []).filter((t) => ["attente", "en_cours", "pause", "erreur"].includes(t.etat));
  const passees = (taches ?? []).filter((t) => ["finie", "annulee"].includes(t.etat));
  const enCours = actives.find((t) => t.etat === "en_cours");

  return (
    <>
      <EnTete titre="Fabrication" sous="Ce qui se fabrique sur ce PC, et ce qui attend son tour." />
      {erreur && <Erreur texte={erreur} />}
      <section className="mb-10">
        {!bramble || !taches ? (
          <Squelette className="h-[380px]" />
        ) : bramble.actif ? (
          <CarteBramble etat={bramble} />
        ) : enCours ? (
          <TacheEnCours tache={enCours} />
        ) : (
          <Carte className="flex items-center gap-6 bg-[radial-gradient(ellipse_at_20%_0%,#1c2433,#151920_60%)] p-10">
            <div className="grid size-14 place-items-center rounded-2xl bg-ambre-sombre text-ambre-vif">
              <Moon className="size-6" />
            </div>
            <div>
              <div className="text-[20px] font-semibold">L'atelier est au repos</div>
              <div className="mt-1 text-[14px] text-doux">Rien ne se fabrique en ce moment. Une fabrication lancée apparaîtra ici avec ses images.</div>
            </div>
          </Carte>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-4 flex items-center gap-3 text-[17px] font-semibold">
          À venir
        </h2>
        {actives.filter((t) => t !== enCours).length ? (
          <div className="flex flex-col gap-2">
            {actives
              .filter((t) => t !== enCours)
              .map((t) => (
                <LigneTache key={t.id} tache={t} relire={relire} />
              ))}
          </div>
        ) : (
          <div className="rounded-carte border border-dashed border-ligne-forte/70 px-6 py-8 text-center text-[14px] text-doux">Aucune fabrication en attente.</div>
        )}
      </section>

      {passees.length > 0 && (
        <section>
          <h2 className="mb-4 text-[17px] font-semibold">Cette semaine</h2>
          <div className="flex flex-col gap-2">
            {passees.map((t) => (
              <LigneTache key={t.id} tache={t} relire={relire} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function TacheEnCours({ tache }: { tache: TacheFile }) {
  const [faits, tous] = tache.progression.split("/").map(Number);
  return (
    <Carte className="p-8">
      <div className="text-[12px] font-semibold tracking-[0.14em] text-ambre uppercase">En cours</div>
      <div className="mt-2 text-[24px] font-semibold">{tache.titre}</div>
      <div className="mt-1 text-[14px] text-doux">{tache.session}</div>
      {tous > 0 && <Barre valeur={(100 * faits) / tous} className="mt-6" />}
      <div className="mt-2.5 flex justify-between text-[13px] text-doux">
        <span>{tous > 0 ? `${faits} sur ${tous} étapes` : ""}</span>
        <span>{tache.reste_s ? `encore ${duree(tache.reste_s)}` : ""}</span>
      </div>
    </Carte>
  );
}

function LigneTache({ tache: t, relire }: { tache: TacheFile; relire(): void }) {
  const [attente, setAttente] = useState(false);
  const [confirmer, setConfirmer] = useState(false);
  const [message, setMessage] = useState("");
  const e = ETATS[t.etat] ?? { nom: t.etat, ton: "neutre" as const };
  const faire = async (action: string) => {
    setAttente(true);
    try {
      await agir(`/file/${t.id}/${action}`);
      relire();
    } catch (x) {
      setMessage(x instanceof Error ? x.message : String(x));
    } finally {
      setAttente(false);
      setConfirmer(false);
    }
  };
  const Icone = t.etat === "finie" ? CircleCheck : t.etat === "erreur" ? CircleAlert : Clock3;
  return (
    <div className="flex items-center gap-4 rounded-[12px] border border-ligne bg-carte px-5 py-3.5">
      <Icone className={cx("size-5 shrink-0", t.etat === "finie" ? "text-vert" : t.etat === "erreur" ? "text-rouge" : "text-pale")} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-medium">{t.titre}</div>
        <div className="truncate text-[12px] text-pale">{message || t.raison || t.session}</div>
      </div>
      {t.pret_vers && <span className="text-[12px] text-doux">prête le {t.pret_vers}</span>}
      <Pastille ton={e.ton}>{e.nom}</Pastille>
      {["attente", "en_cours"].includes(t.etat) && (
        <Bouton genre="discret" className="h-8 px-2.5" charge={attente} onClick={() => faire("pause")} icone={<Pause className="size-4" />} title="Mettre en pause" />
      )}
      {["pause", "erreur"].includes(t.etat) && (
        <Bouton genre="discret" className="h-8 px-2.5" charge={attente} onClick={() => faire("reprendre")} icone={<Play className="size-4" />} title="Reprendre" />
      )}
      {["attente", "pause", "erreur"].includes(t.etat) && (
        <Dialogue.Root open={confirmer} onOpenChange={setConfirmer}>
          <Dialogue.Trigger asChild>
            <Bouton genre="discret" className="h-8 px-2.5" icone={<X className="size-4" />} title="Annuler" />
          </Dialogue.Trigger>
          <Dialogue.Portal>
            <Dialogue.Overlay className="animate-entree fixed inset-0 z-40 bg-black/70" />
            <Dialogue.Content className="animate-entree fixed top-1/2 left-1/2 z-50 w-[440px] -translate-x-1/2 -translate-y-1/2 rounded-[16px] border border-ligne-forte bg-carte p-7 shadow-haut outline-none">
              <Dialogue.Title className="text-[18px] font-semibold">Annuler cette fabrication ?</Dialogue.Title>
              <Dialogue.Description className="mt-2 text-[14px] leading-relaxed text-doux">
                « {t.titre} » sort de la file. Ce qui est déjà fait reste sur le disque.
              </Dialogue.Description>
              <div className="mt-6 flex justify-end gap-2">
                <Dialogue.Close asChild>
                  <Bouton genre="discret">Garder</Bouton>
                </Dialogue.Close>
                <Bouton genre="danger" charge={attente} onClick={() => faire("annuler")}>
                  Annuler la fabrication
                </Bouton>
              </div>
            </Dialogue.Content>
          </Dialogue.Portal>
        </Dialogue.Root>
      )}
    </div>
  );
}

/** L'image d'un épisode pour les autres écrans (vignette d'un script, rendus de Bramble). */
export function useImageEpisode(code?: string, vignette = 0) {
  const { session } = useStudio();
  const { donnees } = useLire<RendusBramble>(session && code ? `/sessions/${session.id}/scripts/${code}/bramble?langue=` : null);
  return imageEpisode(donnees, vignette);
}
