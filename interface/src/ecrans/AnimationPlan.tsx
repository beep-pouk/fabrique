// Plan par plan (étape 5) : les essais d'animation du plan en cours, refaits avec une consigne, comparés côte à côte, le meilleur gardé ;
// l'animatique remontée prend l'essai gardé à la place du mouvement de caméra.
import * as Dialogue from "@radix-ui/react-dialog";
import { Check, Columns2, Loader2, Play, Sparkles, TriangleAlert, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { agir, fichier, useLire, type Animation, type EssaiAnimation } from "../api";
import { Bouton, cx, Pastille } from "../ui";

// etiquette : le nom du plan découpé (« 12b ») ; cadre : le sien (un essai fait sur un autre découpage, autre langue ou version, n'est pas montré)
export function AnimationPlan({ chemin, langue, cle, etiquette, cadre, pause }: { chemin: string; langue: string; cle: string; etiquette: string; cadre?: number[]; pause(): void }) {
  const [suivre, setSuivre] = useState(false);
  const { donnees: a, erreur: lecture, relire } = useLire<Animation>(chemin, suivre ? 3000 : 0);
  const [consigne, setConsigne] = useState("");
  const [message, setMessage] = useState("");
  const [erreur, setErreur] = useState("");
  const [charge, setCharge] = useState(false);
  const [comparer, setComparer] = useState(false);
  useEffect(() => setSuivre(!!a?.occupe), [a?.occupe]);
  useEffect(() => {
    setMessage("");
    setErreur("");
    setConsigne(""); // une consigne commencée ne part jamais sur le plan suivant
  }, [cle]);
  const plan = a?.plans[cle];
  const essais = (plan?.essais ?? []).filter((e) => !cadre || JSON.stringify(e.cadre) === JSON.stringify(cadre)).reverse();
  const garde = essais.some((e) => e.n === plan?.garde) ? (plan?.garde ?? 0) : 0;
  const faits = essais.filter((e) => e.etat === "fait");

  async function faire(action: () => Promise<{ message: string }>) {
    setCharge(true);
    setErreur("");
    setMessage("");
    try {
      setMessage((await action()).message);
      await relire();
    } catch (x) {
      setErreur(x instanceof Error ? x.message : String(x));
    } finally {
      setCharge(false);
    }
  }
  const animer = (e: FormEvent) => {
    e.preventDefault();
    void faire(async () => {
      const r = await agir(chemin, { cle, consigne, langue });
      setConsigne("");
      setSuivre(true);
      return r;
    });
  };
  const garder = (n: number) => void faire(() => agir(`${chemin}/garder`, { cle, n }));

  return (
    <div className="rounded-carte border border-ligne bg-carte">
      <div className="flex items-center justify-between gap-2 border-b border-ligne px-4 py-3">
        <span className="text-[14px] font-medium">Animation du plan {etiquette}</span>
        {garde ? (
          <Pastille ton="vert">
            <Check className="size-3.5" /> essai {garde} gardé
          </Pastille>
        ) : (
          <Pastille>caméra sur l'image</Pastille>
        )}
      </div>
      {essais.length > 0 && (
        <ol className="flex max-h-[380px] flex-col gap-3 overflow-y-auto p-3">
          {essais.map((e) => (
            <Essai key={e.n} e={e} garde={garde === e.n} garder={garder} occupe={charge} />
          ))}
        </ol>
      )}
      {faits.length > 1 && (
        <div className="px-3 pb-1">
          <Bouton genre="second" icone={<Columns2 className="size-4" />} className="w-full" onClick={() => (pause(), setComparer(true))}>
            Comparer les {faits.length} essais
          </Bouton>
        </div>
      )}
      <form onSubmit={animer} className="p-3">
        <textarea
          value={consigne}
          onChange={(e) => setConsigne(e.target.value)}
          onFocus={pause}
          maxLength={600}
          rows={2}
          aria-label="Consigne d'animation"
          placeholder={essais.length ? "Ce qui doit changer… (vide : le mouvement prévu par le script, nouveau tirage)" : "Ce qui doit bouger… (vide : le mouvement prévu par le script)"}
          className="w-full resize-none rounded-[10px] border border-ligne-forte bg-carte-2 px-3 py-2 text-[14px] leading-snug outline-none placeholder:text-pale focus:border-ambre/60"
        />
        <div className="mt-2 flex items-center justify-between gap-3">
          <span className="text-[12px] leading-snug text-pale">
            {a?.occupe ? (a.ici ? "Un essai s'anime…" : "Un essai d'un autre épisode s'anime…") : "5 à 8 min de carte graphique, seulement quand Bramble Studio ne s'en sert pas"}
          </span>
          <Bouton type="submit" genre="principal" icone={<Sparkles className="size-4" />} charge={charge} disabled={!a || a.occupe}>
            {essais.length ? "Refaire" : "Animer"}
          </Bouton>
        </div>
        {message && <p className="mt-2 text-[13px] text-vert">{message}</p>}
        {(erreur || (!a && lecture)) && <p className="mt-2 text-[13px] text-rouge">{erreur || `Les essais ne se lisent pas : ${lecture}`}</p>}
      </form>
      <Comparer ouvert={comparer} fermer={() => setComparer(false)} essais={faits} garde={garde} garder={garder} etiquette={etiquette} />
    </div>
  );
}

function Essai({ e, garde, garder, occupe }: { e: EssaiAnimation; garde: boolean; garder(n: number): void; occupe: boolean }) {
  return (
    <li className={cx("shrink-0 overflow-hidden rounded-[12px] border bg-carte-2/60", garde ? "border-vert/50" : "border-ligne")}>
      {e.etat === "fait" ? (
        <video src={fichier(e.video)} controls muted loop playsInline preload="metadata" className="aspect-video w-full bg-black" />
      ) : (
        <div className="grid aspect-video place-items-center bg-black/40 px-4 text-center text-[13px] leading-snug text-doux">
          {e.etat === "erreur" ? (
            <span className="flex flex-col items-center gap-2 text-rouge">
              <TriangleAlert className="size-5" /> {e.message || "L'essai a échoué."}
            </span>
          ) : (
            <span className="flex flex-col items-center gap-2">
              <Loader2 className="size-5 animate-spin text-ambre" /> {e.etat === "en_cours" ? "S'anime sur la carte graphique…" : "Démarre…"}
            </span>
          )}
        </div>
      )}
      <div className="flex items-start gap-2 p-2.5">
        <div className="min-w-0 flex-1">
          <div className="text-[12px] font-semibold text-doux">
            Essai {e.n}
            {e.simule && <span className="font-normal text-pale"> · simulé (sans carte)</span>}
          </div>
          <p className="copiable line-clamp-2 text-[13px] leading-snug text-texte/85" title={e.consigne}>
            {e.consigne}
          </p>
        </div>
        {e.etat === "fait" && (
          <Bouton genre={garde ? "second" : "discret"} className="h-8 px-2.5 text-[13px]" icone={garde ? <Check className="size-3.5" /> : undefined} disabled={occupe} onClick={() => garder(garde ? 0 : e.n)}>
            {garde ? "Gardé" : "Garder"}
          </Bouton>
        )}
      </div>
    </li>
  );
}

function Comparer({ ouvert, fermer, essais, garde, garder, etiquette }: {
  ouvert: boolean; fermer(): void; essais: EssaiAnimation[]; garde: number; garder(n: number): void; etiquette: string;
}) {
  const videos = useRef<(HTMLVideoElement | null)[]>([]);
  const ensemble = () =>
    videos.current.forEach((v) => {
      if (!v) return;
      v.currentTime = 0;
      void v.play().catch(() => undefined);
    });
  return (
    <Dialogue.Root open={ouvert} onOpenChange={(o) => !o && fermer()}>
      <Dialogue.Portal>
        <Dialogue.Overlay className="animate-entree fixed inset-0 z-40 bg-black/75 backdrop-blur-sm" />
        <Dialogue.Content className="animate-entree fixed top-1/2 left-1/2 z-50 flex max-h-[92vh] w-[min(1560px,94vw)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-[18px] border border-ligne-forte bg-carte shadow-haut outline-none">
          <div className="flex items-center justify-between gap-4 border-b border-ligne px-6 py-4">
            <div>
              <Dialogue.Title className="text-[20px] font-semibold tracking-[-0.01em]">Plan {etiquette} : les essais côte à côte</Dialogue.Title>
              <Dialogue.Description className="mt-0.5 text-[13px] text-doux">Lus ensemble, sans son : gardez celui qui ressemble le plus à un vrai dessin animé.</Dialogue.Description>
            </div>
            <div className="flex items-center gap-2">
              <Bouton genre="principal" icone={<Play className="size-4" />} onClick={ensemble}>
                Lire ensemble
              </Bouton>
              <Dialogue.Close aria-label="Fermer" className="grid size-9 place-items-center rounded-full bg-carte-2 text-doux hover:bg-survol hover:text-texte">
                <X className="size-4" />
              </Dialogue.Close>
            </div>
          </div>
          <div className={cx("grid gap-4 overflow-y-auto p-6", essais.length > 2 ? "grid-cols-3" : "grid-cols-2")}>
            {essais.map((e, i) => (
              <figure key={e.n} className={cx("overflow-hidden rounded-[14px] border bg-carte-2", e.n === garde ? "border-vert/60" : "border-ligne")}>
                <video
                  ref={(v) => {
                    videos.current[i] = v;
                  }}
                  src={fichier(e.video)}
                  muted
                  loop
                  playsInline
                  preload="auto"
                  onClick={(x) => void (x.currentTarget.paused ? x.currentTarget.play().catch(() => undefined) : x.currentTarget.pause())}
                  className="aspect-video w-full cursor-pointer bg-black"
                />
                <figcaption className="flex items-start gap-3 p-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-semibold">Essai {e.n}</div>
                    <p className="copiable mt-0.5 line-clamp-3 text-[13px] leading-snug text-texte/80">{e.consigne}</p>
                  </div>
                  <Bouton genre={e.n === garde ? "second" : "principal"} icone={e.n === garde ? <Check className="size-4" /> : undefined} onClick={() => garder(e.n === garde ? 0 : e.n)}>
                    {e.n === garde ? "Gardé" : "Garder celui-ci"}
                  </Bouton>
                </figcaption>
              </figure>
            ))}
          </div>
        </Dialogue.Content>
      </Dialogue.Portal>
    </Dialogue.Root>
  );
}
