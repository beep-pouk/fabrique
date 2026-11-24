import * as Dialogue from "@radix-ui/react-dialog";
import { Mic, Users, X } from "lucide-react";
import { useState } from "react";
import type { Personnage } from "../api";
import { nomLangue } from "../outils";
import { useStudio } from "../studio";
import { BoutonEcoute, cx, EnTete, Image, Pastille, Squelette, Vide } from "../ui";

const ROLES: Record<string, string> = { narrateur: "Narrateur", ami: "Ami", heros: "Héros", héros: "Héros" };
const role = (r: string) => ROLES[r] ?? (r ? r.charAt(0).toUpperCase() + r.slice(1) : "Personnage");

export function Personnages() {
  const { session, univers, personnages } = useStudio();
  const [ouvert, setOuvert] = useState<Personnage | null>(null);
  const liste = [...personnages].sort((a, b) => Number(b.voix.length > 0) - Number(a.voix.length > 0) || a.nom.localeCompare(b.nom));
  const vedette = liste[0]?.voix.length ? liste[0] : undefined;
  const autres = vedette ? liste.slice(1) : liste;

  return (
    <>
      <EnTete surtitre={session?.nom} titre="Personnages" sous={univers && `${liste.length} personnage${liste.length > 1 ? "s" : ""}`} />
      {!univers && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-6">
          {Array.from({ length: 10 }, (_, i) => (
            <Squelette key={i} className="aspect-[4/5]" />
          ))}
        </div>
      )}
      {univers && !liste.length && <Vide icone={<Users className="size-5" />} titre="Aucun personnage" texte="Les personnages de la série apparaîtront ici avec leurs images." />}

      {vedette && (
        <button
          onClick={() => setOuvert(vedette)}
          className="group mb-10 grid w-full overflow-hidden rounded-[20px] border border-ligne bg-carte text-left transition-colors hover:border-ligne-forte md:grid-cols-[minmax(280px,420px)_1fr]"
        >
          <Image chemin={vedette.references[0]?.chemin} largeur={960} className="aspect-square md:aspect-auto md:h-full" position="50% 35%" />
          <div className="flex flex-col justify-center gap-4 p-10">
            <Pastille ton="ambre" className="self-start">
              <Mic className="size-3.5" /> {role(vedette.role)}
            </Pastille>
            <div className="text-[34px] font-semibold tracking-[-0.02em]">{vedette.nom}</div>
            {vedette.description && <p className="max-w-[640px] text-[15px] leading-relaxed text-doux">{vedette.description}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {vedette.voix.map((v) => (
                <BoutonEcoute key={v.langue} cle={`voix-${vedette.id}-${v.langue}`} sons={[v.chemin]} etiquette={nomLangue(v.langue)} />
              ))}
            </div>
          </div>
        </button>
      )}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-x-6 gap-y-8">
        {autres.map((p) => (
          <button key={p.id} onClick={() => setOuvert(p)} className="group flex flex-col justify-start text-left outline-none">
            <div className="relative overflow-hidden rounded-carte ring-1 ring-ligne transition-all duration-300 group-hover:shadow-haut group-hover:ring-ligne-forte group-focus-visible:ring-2 group-focus-visible:ring-ambre">
              <Image chemin={p.references[0]?.chemin} largeur={640} className="aspect-[4/5] transition-transform duration-500 group-hover:scale-[1.04]" position="50% 30%" />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/75 via-black/0 to-black/0" />
              <div className="absolute right-4 bottom-3.5 left-4">
                <div className="titre-image text-[18px] font-semibold">{p.nom}</div>
                <div className="titre-image text-[12px] text-white/70">{role(p.role)}</div>
              </div>
              {p.references.length > 1 && (
                <span className="absolute top-3 right-3 rounded-full bg-black/55 px-2 py-0.5 text-[11px] font-medium text-white/85 backdrop-blur">
                  {p.references.length} images
                </span>
              )}
            </div>
            {p.description && <p className="mt-3 line-clamp-2 px-0.5 text-[13px] leading-relaxed text-doux">{p.description}</p>}
          </button>
        ))}
      </div>

      <Fiche personnage={ouvert} fermer={() => setOuvert(null)} />
    </>
  );
}

function Fiche({ personnage: p, fermer }: { personnage: Personnage | null; fermer(): void }) {
  const [vue, setVue] = useState(0);
  const ref = p?.references[Math.min(vue, (p?.references.length ?? 1) - 1)];
  return (
    <Dialogue.Root
      open={!!p}
      onOpenChange={(o) => {
        if (!o) {
          fermer();
          setVue(0);
        }
      }}
    >
      <Dialogue.Portal>
        <Dialogue.Overlay className="animate-entree fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" />
        {p && (
          <Dialogue.Content className="animate-entree fixed top-1/2 left-1/2 z-50 grid max-h-[90vh] w-[min(1160px,92vw)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-[18px] border border-ligne-forte bg-carte shadow-haut outline-none md:grid-cols-[1.15fr_1fr]">
            <div className="flex min-h-0 flex-col bg-black/30">
              <Image chemin={ref?.chemin} largeur={1280} className="min-h-[360px] flex-1" />
              {p.references.length > 1 && (
                <div className="flex gap-2 overflow-x-auto p-3">
                  {p.references.map((r, i) => (
                    <button
                      key={r.chemin}
                      onClick={() => setVue(i)}
                      title={r.vue}
                      className={cx("shrink-0 overflow-hidden rounded-lg ring-2 transition-all", i === vue ? "ring-ambre" : "opacity-60 ring-transparent hover:opacity-100")}
                    >
                      <Image chemin={r.chemin} largeur={320} className="h-16 w-16" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex min-h-0 flex-col overflow-y-auto p-8">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <Dialogue.Title className="text-[28px] font-semibold tracking-[-0.02em]">{p.nom}</Dialogue.Title>
                  <div className="mt-1 text-[14px] text-doux">{role(p.role)}</div>
                </div>
                <Dialogue.Close className="grid size-9 place-items-center rounded-full bg-carte-2 text-doux hover:bg-survol hover:text-texte">
                  <X className="size-4" />
                </Dialogue.Close>
              </div>
              <Dialogue.Description className="copiable mt-5 text-[15px] leading-relaxed text-texte/85">
                {p.description || "Pas encore de description."}
              </Dialogue.Description>
              {ref?.vue && (
                <div className="mt-6 text-[13px] text-doux">
                  <span className="text-pale">Image : </span>
                  {ref.vue}
                </div>
              )}
              {p.voix.length > 0 && (
                <div className="mt-8">
                  <div className="mb-3 text-[12px] font-semibold tracking-[0.1em] text-pale uppercase">Sa voix</div>
                  <div className="flex flex-wrap gap-2">
                    {p.voix.map((v) => (
                      <BoutonEcoute key={v.langue} cle={`voix-${p.id}-${v.langue}`} sons={[v.chemin]} etiquette={nomLangue(v.langue)} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Dialogue.Content>
        )}
      </Dialogue.Portal>
    </Dialogue.Root>
  );
}
