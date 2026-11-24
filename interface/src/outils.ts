import { useEffect, useState } from "react";
import type { Plan, RendusBramble, Scene } from "./api";

// --- navigation : l'adresse après # (« /episode/<session>/<code> ») ---

export function useAdresse(): string[] {
  const lireHash = () =>
    location.hash
      .replace(/^#\/?/, "")
      .split("/")
      .filter(Boolean)
      .map((p) => {
        try {
          return decodeURIComponent(p);
        } catch {
          return p; // un % mal formé : la partie telle quelle
        }
      });
  const [parties, setParties] = useState(lireHash);
  useEffect(() => {
    const changer = () => setParties(lireHash());
    window.addEventListener("hashchange", changer);
    return () => window.removeEventListener("hashchange", changer);
  }, []);
  return parties;
}

export const aller = (...parties: string[]) => {
  location.hash = "/" + parties.map(encodeURIComponent).join("/");
};

// --- textes ---

const langues = new Intl.DisplayNames(["fr"], { type: "language" });
export function nomLangue(code: string): string {
  try {
    const n = langues.of(code) ?? code;
    return n.charAt(0).toUpperCase() + n.slice(1);
  } catch {
    return code;
  }
}

export function duree(secondes: number): string {
  if (!isFinite(secondes) || secondes <= 0) return "—";
  const s = Math.round(secondes);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, "0")}`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

export function horloge(secondes: number): string {
  const s = Math.max(0, Math.round(secondes));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function dateLongue(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

export function dateCourte(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

export function joursAvant(iso: string): number {
  const aujourdhui = new Date();
  aujourdhui.setHours(12, 0, 0, 0);
  return Math.round((new Date(iso + "T12:00:00").getTime() - aujourdhui.getTime()) / 86400000);
}

export function quand(iso: string): string {
  const j = joursAvant(iso);
  if (j === 0) return "aujourd'hui";
  if (j === 1) return "demain";
  if (j === -1) return "hier";
  if (j > 1 && j < 7) return `dans ${j} jours`;
  return dateLongue(iso);
}

export const STATUTS: Record<string, { nom: string; ton: "neutre" | "ambre" | "vert" | "bleu" | "rouge" }> = {
  idee: { nom: "Idée", ton: "neutre" },
  script: { nom: "Script en cours", ton: "neutre" },
  scenario: { nom: "Script prêt", ton: "neutre" },
  prete: { nom: "Prêt à fabriquer", ton: "neutre" },
  fabrication: { nom: "En fabrication", ton: "ambre" },
  a_verifier: { nom: "À vérifier", ton: "ambre" },
  approuvee: { nom: "À publier", ton: "bleu" },
  programmee: { nom: "Programmé", ton: "bleu" },
  publiee: { nom: "Publié", ton: "vert" },
  suivie: { nom: "Publié", ton: "vert" },
  reportee: { nom: "Reporté", ton: "rouge" },
};

export function salutation(): string {
  const h = new Date().getHours();
  return h < 5 || h >= 18 ? "Bonsoir" : "Bonjour";
}

// --- la planche : un plan, ses scènes, ce qui est dit, sa durée, qui y paraît ---

export const MAX_IMAGE_S = 15; // règle de RT (24/11) : aucune image ne reste plus de 15 s à l'écran
const MOTS_PAR_SECONDE = 2; // lecture lente du soir, quand la voix n'est pas encore là (mesuré sur une scène de Bramble : ≈ 2 mots/s)

export interface PlanLu {
  n: number;
  numero: number;
  image?: string;
  description: string;
  texte: string;
  scenes: Scene[];
  duree: number;
  estimee: boolean;
  debut: number;
  bramble: boolean;
  personnages: string[];
  voix: string[];
}

export function lirePlanche(plans: Plan[], scenes: Scene[], rendus: RendusBramble | undefined, distribution: string[]): PlanLu[] {
  const parId = new Map(scenes.map((s) => [s.id, s]));
  const images = rendus?.images ?? {};
  let debut = 0;
  let derniereImage: string | undefined;
  return plans.map((p, i) => {
    const sc = p.scenes.map((id) => parId.get(id)).filter((s): s is Scene => !!s);
    const texte = sc.map((s) => s.narration ?? "").filter(Boolean).join(" ");
    const voix = p.scenes.map((id) => rendus?.voix[id]).filter((v): v is string => !!v);
    const mesuree = p.scenes.reduce((t, id) => t + (rendus?.durees[id] ?? 0), 0);
    const estimee = p.scenes.some((id) => !(rendus?.durees[id] ?? 0));
    const d = estimee ? Math.max(3, texte.split(/\s+/).filter(Boolean).length / MOTS_PAR_SECONDE) : mesuree;
    const image = images[p.n] ?? (p.bramble ? undefined : derniereImage);
    if (images[p.n]) derniereImage = images[p.n];
    const plan: PlanLu = {
      n: p.n,
      numero: i + 1,
      image,
      description: p.image,
      texte,
      scenes: sc,
      duree: d,
      estimee,
      debut,
      bramble: p.bramble,
      personnages: distribution.filter((nom) => cite(nom, `${p.image} ${texte}`)),
      voix,
    };
    debut += d;
    return plan;
  });
}

/** `nom` est-il cité comme un mot entier dans `texte` (lettres accentuées comprises, aucun caractère spécial interprété) ? */
export function cite(nom: string, texte: string): boolean {
  const echappe = nom.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![\\p{L}\\p{N}])${echappe}(?![\\p{L}\\p{N}])`, "u").test(texte);
}

/** L'image d'un épisode : celle du plan qui contient sa scène de miniature, sinon la première venue. */
export function imageEpisode(rendus: RendusBramble | undefined, scene: number): string | undefined {
  if (!rendus) return undefined;
  const cles = Object.keys(rendus.images)
    .map(Number)
    .sort((a, b) => a - b);
  if (!cles.length) return undefined;
  const avant = cles.filter((n) => n <= scene);
  return rendus.images[String(scene > 0 && avant.length ? avant[avant.length - 1] : cles[Math.min(2, cles.length - 1)])];
}

/** La raison du noyau quand la carte graphique est prise, dite simplement (vide : libre). */
export function carteOccupee(raison: string): string {
  if (!raison) return "Prête pour une fabrication.";
  if (raison.includes("Bramble")) return "Bramble Studio fabrique : Fabrique attend son tour.";
  if (raison.includes("fabrication")) return "Une fabrication de Fabrique est en cours.";
  if (raison.includes("outil")) return "Un outil s'installe : Fabrique attend.";
  return "Un autre programme l'utilise : Fabrique attend.";
}
