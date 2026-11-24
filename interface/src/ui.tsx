// Les composants de Fabrique : un seul jeu, partout (boutons, pastilles, images, cartes, en-têtes, états vides, écoute).
import { clsx } from "clsx";
import { ImageOff, Loader2, Pause, Play } from "lucide-react";
import { useEffect, useState, useSyncExternalStore, type ButtonHTMLAttributes, type ReactNode } from "react";
import { twMerge } from "tailwind-merge";
import { fichier } from "./api";

export const cx = (...c: Parameters<typeof clsx>) => twMerge(clsx(c));

type Genre = "principal" | "second" | "discret" | "danger";

export function Bouton({
  genre = "second",
  icone,
  className,
  children,
  charge,
  ...reste
}: ButtonHTMLAttributes<HTMLButtonElement> & { genre?: Genre; icone?: ReactNode; charge?: boolean }) {
  return (
    <button
      {...reste}
      disabled={reste.disabled || charge}
      className={cx(
        "inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-[10px] px-4 text-[14px] font-medium whitespace-nowrap transition-all duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45",
        genre === "principal" && "bg-ambre text-[#1b1406] shadow-[0_8px_24px_-10px_rgb(240_169_60/0.7)] hover:bg-ambre-vif",
        genre === "second" && "border border-ligne-forte bg-carte-2/80 text-texte backdrop-blur hover:border-[#465061] hover:bg-survol",
        genre === "discret" && "text-doux hover:bg-survol hover:text-texte",
        genre === "danger" && "border border-rouge/40 bg-rouge-sombre text-rouge hover:bg-rouge/20",
        className,
      )}
    >
      {charge ? <Loader2 className="size-4 animate-spin" /> : icone}
      {children}
    </button>
  );
}

const TONS = {
  neutre: "bg-white/[0.06] text-doux ring-white/10",
  ambre: "bg-ambre-sombre text-ambre-vif ring-ambre/25",
  vert: "bg-vert-sombre text-vert ring-vert/25",
  bleu: "bg-bleu-sombre text-bleu ring-bleu/25",
  rouge: "bg-rouge-sombre text-rouge ring-rouge/25",
};

export function Pastille({ ton = "neutre", children, className }: { ton?: keyof typeof TONS; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium ring-1 ring-inset", TONS[ton], className)}>
      {children}
    </span>
  );
}

/** Une image du disque, réduite à `largeur` par le noyau ; un reflet pendant le chargement, un repère sobre si elle manque. */
export function Image({ chemin, largeur = 640, className, alt = "", position }: { chemin?: string; largeur?: number; className?: string; alt?: string; position?: string }) {
  const [etat, setEtat] = useState<"charge" | "ok" | "erreur">(chemin ? "charge" : "erreur");
  useEffect(() => setEtat(chemin ? "charge" : "erreur"), [chemin]);
  return (
    <div className={cx("relative overflow-hidden bg-carte-2", className)}>
      {etat === "charge" && <div className="attente absolute inset-0" />}
      {etat === "erreur" ? (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(circle_at_50%_40%,#1d2330,#12161c)] text-pale">
          <ImageOff className="size-6 opacity-60" strokeWidth={1.5} />
        </div>
      ) : (
        <img
          src={fichier(chemin!, largeur)}
          alt={alt}
          loading="lazy"
          decoding="async"
          draggable={false}
          onLoad={() => setEtat("ok")}
          onError={() => setEtat("erreur")}
          style={position ? { objectPosition: position } : undefined}
          className={cx("absolute inset-0 size-full object-cover transition-opacity duration-500", etat === "ok" ? "opacity-100" : "opacity-0")}
        />
      )}
    </div>
  );
}

export function Carte({ className, children, onClick }: { className?: string; children: ReactNode; onClick?: () => void }) {
  return (
    <div onClick={onClick} className={cx("rounded-carte border border-ligne bg-carte", onClick && "cursor-pointer", className)}>
      {children}
    </div>
  );
}

export function EnTete({ surtitre, titre, children, sous }: { surtitre?: ReactNode; titre: ReactNode; children?: ReactNode; sous?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4 pb-7">
      <div className="min-w-0">
        {surtitre && <div className="mb-2 text-[12px] font-semibold tracking-[0.14em] text-ambre uppercase">{surtitre}</div>}
        <h1 className="text-[30px] leading-tight font-semibold tracking-[-0.02em] text-balance">{titre}</h1>
        {sous && <div className="mt-2 text-[15px] text-doux">{sous}</div>}
      </div>
      {children && <div className="flex items-center gap-2.5">{children}</div>}
    </header>
  );
}

export function Vide({ icone, titre, texte, children }: { icone: ReactNode; titre: string; texte?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-carte border border-dashed border-ligne-forte/70 px-8 py-16 text-center">
      <div className="grid size-12 place-items-center rounded-2xl bg-carte-2 text-doux">{icone}</div>
      <div className="text-[16px] font-medium">{titre}</div>
      {texte && <div className="max-w-md text-[14px] leading-relaxed text-doux">{texte}</div>}
      {children}
    </div>
  );
}

export function Squelette({ className }: { className?: string }) {
  return <div className={cx("attente rounded-carte", className)} />;
}

export function Erreur({ texte }: { texte: string }) {
  return <div className="rounded-carte border border-rouge/30 bg-rouge-sombre/60 px-5 py-4 text-[14px] text-rouge">{texte}</div>;
}

// --- écoute : un seul son à la fois dans toute l'application ---

const lecteur = new Audio();
let enCours = ""; // la clé de ce qui joue
const abonnes = new Set<() => void>();
const prevenir = () => abonnes.forEach((f) => f());
lecteur.addEventListener("ended", () => {
  const suite = file.shift();
  if (suite) {
    lecteur.src = fichier(suite);
    lecteur.play();
  } else {
    enCours = "";
    prevenir();
  }
});
lecteur.addEventListener("error", () => {
  enCours = "";
  file = [];
  prevenir();
});
let file: string[] = [];

export function ecouter(cle: string, sons: string[]) {
  if (enCours === cle) {
    lecteur.pause();
    enCours = "";
    file = [];
  } else if (sons.length) {
    enCours = cle;
    file = sons.slice(1);
    lecteur.src = fichier(sons[0]);
    lecteur.play().catch(() => {
      enCours = "";
      prevenir();
    });
  }
  prevenir();
}

export function arreterEcoute() {
  if (!enCours) return;
  lecteur.pause();
  enCours = "";
  file = [];
  prevenir();
}

export function useEcoute(): string {
  return useSyncExternalStore(
    (f) => {
      abonnes.add(f);
      return () => abonnes.delete(f);
    },
    () => enCours,
  );
}

export function BoutonEcoute({ cle, sons, etiquette, petit }: { cle: string; sons: string[]; etiquette?: string; petit?: boolean }) {
  const joue = useEcoute() === cle;
  if (!sons.length) return null;
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        ecouter(cle, sons);
      }}
      title={joue ? "Arrêter" : "Écouter"}
      className={cx(
        "inline-flex items-center gap-2 rounded-full font-medium transition-colors",
        petit ? "size-8 justify-center" : "h-9 pr-4 pl-1.5 text-[13px]",
        joue ? "bg-ambre text-[#1b1406]" : "bg-black/55 text-texte ring-1 ring-white/15 backdrop-blur-md hover:bg-black/75",
      )}
    >
      <span className={cx("grid place-items-center rounded-full", petit ? "" : "size-6", !petit && (joue ? "bg-black/15" : "bg-white/10"))}>
        {joue ? <Pause className="size-3.5" fill="currentColor" /> : <Play className="size-3.5 translate-x-px" fill="currentColor" />}
      </span>
      {!petit && (etiquette ?? "Écouter")}
    </button>
  );
}

export function Avatar({ chemin, nom, taille = 28, className }: { chemin?: string; nom: string; taille?: number; className?: string }) {
  return (
    <span title={nom} className={cx("inline-block shrink-0 overflow-hidden rounded-full ring-2 ring-carte", className)} style={{ width: taille, height: taille }}>
      {chemin ? (
        <Image chemin={chemin} largeur={320} className="size-full" position="50% 30%" />
      ) : (
        <span className="grid size-full place-items-center bg-survol text-[11px] font-semibold text-doux">{nom.slice(0, 1)}</span>
      )}
    </span>
  );
}
