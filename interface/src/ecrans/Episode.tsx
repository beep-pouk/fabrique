import * as Dialogue from "@radix-ui/react-dialog";
import * as Menu from "@radix-ui/react-dropdown-menu";
import * as Onglets from "@radix-ui/react-tabs";
import * as Infobulle from "@radix-ui/react-tooltip";
import { ArrowLeft, CalendarDays, Check, ChevronDown, Clapperboard, Clock3, Film, Images, Languages, LayoutGrid, Mic, TriangleAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fichier, useLire, type Animatique as EtatAnimatique, type Comparaison, type Personnage, type RendusBramble, type ScriptDetail } from "../api";
import { dateLongue, duree, horloge, imageEpisode, lirePlanche, MAX_IMAGE_S, nomLangue, tropLong, VALEURS, type PlanLu } from "../outils";
import { useStudio } from "../studio";
import { Avatar, BoutonEcoute, Bouton, cx, Erreur, Image, Pastille, Squelette, Vide } from "../ui";
import { Animatique } from "./Animatique";
import { Comparaisons } from "./Comparaison";

export function Episode({ session, code, onglet: demande, depart }: { session: string; code: string; onglet?: string; depart?: number }) {
  const { univers, portraits, distribution } = useStudio();
  const { donnees: script, erreur } = useLire<ScriptDetail>(`/sessions/${session}/scripts/${code}`);
  const base = script?.contenu.language ?? "en";
  const [langue, setLangue] = useState<string | null>(null);
  const voixDe = langue ?? base;
  const { donnees: rendus } = useLire<RendusBramble>(`/sessions/${session}/scripts/${code}/bramble?langue=${encodeURIComponent(voixDe)}`);
  const { donnees: essais } = useLire<Comparaison[]>(`/sessions/${session}/scripts/${code}/comparaisons`);
  const [onglet, setOnglet] = useState(demande ?? "planche");
  const barre = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (onglet !== "planche") barre.current?.scrollIntoView({ block: "start", behavior: demande === onglet ? "instant" : "smooth" }); // les lecteurs dans la fenêtre
  }, [onglet, demande, !!script]); // une fois le script lu : la page a sa hauteur

  const narrateur = univers?.personnages.find((p) => p.voix.length);
  const { donnees: anim } = useLire<EtatAnimatique>(`/sessions/${encodeURIComponent(session)}/scripts/${encodeURIComponent(code)}/animatique?langue=${encodeURIComponent(voixDe)}`);
  const plans = useMemo(() => {
    const lus = script ? lirePlanche(script.plans, script.contenu.scenes ?? [], rendus, distribution) : [];
    const coupes = new Map<number, NonNullable<EtatAnimatique["plans"]>>(); // l'animatique montée : vraies durées à l'écran (pauses et tenues comprises) et découpage
    for (const r of anim?.plans ?? []) coupes.set(r.n, [...(coupes.get(r.n) ?? []), r]);
    return coupes.size
      ? lus.map((p) => {
          const c = coupes.get(p.n);
          return c ? { ...p, debut: c[0].debut, duree: c.reduce((s, r) => s + r.duree, 0), estimee: false, decoupe: c[0].valeur ? c : undefined } : p;
        })
      : lus;
  }, [script, rendus, distribution, anim]);
  const total = anim?.plans.length ? anim.plans.reduce((t, r) => t + r.duree, 0) : plans.reduce((t, p) => t + p.duree, 0);
  const longs = plans.filter(tropLong).length;
  const presents = distribution.filter((n) => plans.some((p) => p.personnages.includes(n)) && n !== narrateur?.nom);
  const numero = /e(\d+)$/i.exec(code)?.[1];

  if (erreur && !script) return <Erreur texte={erreur} />;
  return (
    <>
      <a href="#/episodes" className="mb-5 inline-flex items-center gap-2 text-[13px] font-medium text-doux transition-colors hover:text-texte">
        <ArrowLeft className="size-4" /> Épisodes
      </a>

      <section className="relative mb-8 overflow-hidden rounded-[20px] ring-1 ring-ligne">
        <Image chemin={imageEpisode(rendus, script?.contenu.thumbnail_scene ?? 0)} largeur={1280} className="h-[380px] w-full" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#07090c]/95 via-[#07090c]/70 to-[#07090c]/0" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#07090c]/80 via-transparent to-transparent" />
        <div className="absolute inset-0 flex flex-col justify-end p-10">
          <div className="max-w-[760px]">
            <div className="mb-3 flex items-center gap-3 text-[13px] font-medium text-ambre-vif">
              <span className="tracking-[0.12em] uppercase">{numero ? `Épisode ${Number(numero)}` : code}</span>
              {script?.date_prevue && (
                <span className="inline-flex items-center gap-1.5 text-white/75">
                  <CalendarDays className="size-3.5" /> prévu {dateLongue(script.date_prevue)}
                </span>
              )}
            </div>
            {script ? (
              <h1 className="titre-image text-[40px] leading-[1.08] font-semibold tracking-[-0.025em] text-balance">{script.titre}</h1>
            ) : (
              <Squelette className="h-12 w-[560px]" />
            )}
            {script?.contenu.theme && <p className="titre-image mt-3 line-clamp-2 max-w-[640px] text-[15px] leading-relaxed text-white/75">{script.contenu.theme}</p>}
            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3 text-[13px] text-white/80">
              <span className="inline-flex items-center gap-2">
                <Images className="size-4 text-white/60" /> {plans.length} plans
              </span>
              <span className="inline-flex items-center gap-2">
                <Clock3 className="size-4 text-white/60" /> {total ? duree(total) : "—"}
              </span>
              {rendus && rendus.langues.length > 0 && (
                <span className="inline-flex items-center gap-2">
                  <Languages className="size-4 text-white/60" /> {rendus.langues.length} langue{rendus.langues.length > 1 ? "s" : ""}
                </span>
              )}
              {presents.length > 0 && (
                <span className="flex items-center gap-2.5">
                  <span className="flex -space-x-2">
                    {presents.slice(0, 5).map((n) => (
                      <Avatar key={n} nom={n} chemin={portraits[n]} taille={30} className="ring-[#0b0d10]" />
                    ))}
                  </span>
                  {presents.slice(0, 3).join(", ")}
                  {presents.length > 3 && ` +${presents.length - 3}`}
                </span>
              )}
            </div>
          </div>
        </div>
        {rendus && rendus.videos.length > 0 && (
          <div className="absolute top-6 right-6">
            <Bouton genre="second" icone={<Film className="size-4" />} onClick={() => setOnglet("video")} className="bg-black/45">
              Regarder
            </Bouton>
          </div>
        )}
      </section>

      <Onglets.Root value={onglet} onValueChange={setOnglet}>
        <div ref={barre} className="sticky top-0 z-20 -mx-10 mb-6 flex items-center justify-between gap-6 border-b border-ligne bg-fond/90 px-10 backdrop-blur-xl 2xl:-mx-14 2xl:px-14">
          <Onglets.List className="flex gap-1">
            {[
              { id: "planche", nom: "Planche", icone: LayoutGrid },
              { id: "animatique", nom: "Animatique", icone: Clapperboard },
              { id: "video", nom: "Vidéo", icone: Film },
            ].filter((o) => o.id !== "animatique" || !script || script.plans.length > 0).map((o) => ( // un format sans plans n'a pas d'animatique
              <Onglets.Trigger
                key={o.id}
                value={o.id}
                className="relative flex h-12 items-center gap-2 px-4 text-[14px] font-medium text-doux outline-none transition-colors hover:text-texte data-[state=active]:text-texte data-[state=active]:after:absolute data-[state=active]:after:inset-x-3 data-[state=active]:after:-bottom-px data-[state=active]:after:h-0.5 data-[state=active]:after:rounded-full data-[state=active]:after:bg-ambre"
              >
                <o.icone className="size-4" /> {o.nom}
              </Onglets.Trigger>
            ))}
          </Onglets.List>
          {onglet !== "video" && rendus && rendus.langues.length > 0 && <ChoixLangue langues={rendus.langues} valeur={voixDe} changer={setLangue} />}
        </div>

        <Onglets.Content value="planche" className="outline-none">
          {!script ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(330px,1fr))] gap-6">
              {Array.from({ length: 6 }, (_, i) => (
                <Squelette key={i} className="h-[330px]" />
              ))}
            </div>
          ) : plans.length ? (
            <Planche plans={plans} total={total} longs={longs} portraits={portraits} narrateur={narrateur} animatique={!!anim?.plans.length} />
          ) : (
            <Vide icone={<LayoutGrid className="size-5" />} titre="Pas encore de planche" texte="La planche se construit à partir du script : elle apparaîtra dès qu'il sera prêt." />
          )}
        </Onglets.Content>

        <Onglets.Content value="animatique" className="outline-none">
          {script && <Animatique session={session} code={code} langue={voixDe} plans={plans} imageDe={(p) => imagePlan(p, narrateur)} depart={depart} />}
        </Onglets.Content>

        <Onglets.Content value="video" className="outline-none">
          <Comparaisons essais={essais ?? []} />
          <Videos rendus={rendus} titre={script?.titre ?? ""} affiche={imageEpisode(rendus, script?.contenu.thumbnail_scene ?? 0)} />
        </Onglets.Content>
      </Onglets.Root>
    </>
  );
}

function ChoixLangue({ langues, valeur, changer }: { langues: string[]; valeur: string; changer(l: string): void }) {
  return (
    <Menu.Root>
      <Menu.Trigger className="flex h-9 items-center gap-2 rounded-[10px] border border-ligne-forte bg-carte px-3 text-[13px] font-medium outline-none hover:bg-survol">
        <Mic className="size-4 text-doux" /> Voix : {nomLangue(valeur)}
        <ChevronDown className="size-4 text-pale" />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content align="end" sideOffset={6} className="animate-entree z-50 min-w-[200px] rounded-[12px] border border-ligne-forte bg-carte-2 p-1.5 shadow-haut">
          {langues.map((l) => (
            <Menu.Item
              key={l}
              onSelect={() => changer(l)}
              className="flex h-9 cursor-default items-center gap-2.5 rounded-lg px-2.5 text-[13px] outline-none data-[highlighted]:bg-survol"
            >
              <span className="flex-1">{nomLangue(l)}</span>
              {l === valeur && <Check className="size-4 text-ambre" />}
            </Menu.Item>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

function imagePlan(p: PlanLu, narrateur?: Personnage): string | undefined {
  if (!p.bramble) return p.image;
  const pose = p.scenes[0]?.bramble;
  const portrait = narrateur?.references[0]?.chemin;
  return pose && portrait ? portrait.replace(/reference\.png$/i, `poses\\${pose}.png`) : portrait;
}

function Planche({ plans, total, longs, portraits, narrateur, animatique }: { plans: PlanLu[]; total: number; longs: number; portraits: Record<string, string>; narrateur?: Personnage; animatique: boolean }) {
  const [ouvert, setOuvert] = useState<PlanLu | null>(null);
  const estimee = plans.some((p) => p.estimee);
  return (
    <>
      <div className="mb-7 rounded-carte border border-ligne bg-carte p-5">
        <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
          <div className="text-[14px] font-medium">
            Rythme de l'épisode <span className="ml-2 font-normal text-doux">{animatique ? "durées de l'animatique" : estimee ? "durées estimées d'après le texte" : "durées des voix"}</span>
          </div>
          {longs > 0 ? (
            <Pastille ton="ambre">
              <TriangleAlert className="size-3.5" /> {longs} image{longs > 1 ? "s restent" : " reste"} plus de {MAX_IMAGE_S} s
            </Pastille>
          ) : (
            <Pastille ton="vert">
              <Check className="size-3.5" /> Aucune image plus de {MAX_IMAGE_S} s
            </Pastille>
          )}
        </div>
        <div className="flex h-11 gap-[2px] overflow-hidden rounded-[8px]">
          {plans.map((p) => (
            <Infobulle.Root key={p.n}>
              <Infobulle.Trigger asChild>
                <button
                  onClick={() => document.getElementById(`plan-${p.n}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
                  style={{ flexGrow: p.duree }}
                  className={cx(
                    "relative min-w-[3px] basis-0 overflow-hidden transition-[filter] hover:brightness-125",
                    tropLong(p) ? "bg-ambre" : p.bramble ? "bg-[#3a4a66]" : "bg-[#2b333f]",
                  )}
                >
                  {p.image && !p.bramble && p.duree > total / 60 && (
                    <img src={fichier(p.image, 320)} alt="" className={cx("absolute inset-0 size-full object-cover", tropLong(p) ? "opacity-35" : "opacity-60")} />
                  )}
                </button>
              </Infobulle.Trigger>
              <Infobulle.Portal>
                <Infobulle.Content sideOffset={6} className="z-50 rounded-lg border border-ligne-forte bg-carte-2 px-3 py-2 text-[12px] shadow-haut">
                  Plan {p.numero} · {horloge(p.debut)} · {duree(p.duree)}
                  {p.decoupe && p.decoupe.length > 1 && ` · ${p.decoupe.length} plans cadrés`}
                  {tropLong(p) && <span className="text-ambre-vif"> · trop long</span>}
                </Infobulle.Content>
              </Infobulle.Portal>
            </Infobulle.Root>
          ))}
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-pale tabular-nums">
          <span>0:00</span>
          <span>{horloge(total / 2)}</span>
          <span>{horloge(total)}</span>
        </div>
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(330px,1fr))] gap-6">
        {plans.map((p) => (
          <CartePlan key={p.n} plan={p} image={imagePlan(p, narrateur)} portraits={portraits} ouvrir={() => setOuvert(p)} />
        ))}
      </div>

      <Dialogue.Root open={!!ouvert} onOpenChange={(o) => !o && setOuvert(null)}>
        <Dialogue.Portal>
          <Dialogue.Overlay className="animate-entree fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" />
          {ouvert && (
            <Dialogue.Content className="animate-entree fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[min(1180px,92vw)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-[18px] border border-ligne-forte bg-carte shadow-haut outline-none">
              <div className="relative">
                <Image chemin={imagePlan(ouvert, narrateur)} largeur={1280} className="aspect-video max-h-[62vh] w-full" />
                <Dialogue.Close aria-label="Fermer" className="absolute top-4 right-4 grid size-9 place-items-center rounded-full bg-black/55 text-white backdrop-blur hover:bg-black/75">
                  <X className="size-4" />
                </Dialogue.Close>
                <div className="absolute bottom-4 left-4">
                  <BoutonEcoute cle={`plan-${ouvert.n}`} sons={ouvert.voix} etiquette="Écouter le plan" />
                </div>
              </div>
              <div className="grid gap-8 overflow-y-auto p-7 md:grid-cols-[minmax(0,1fr)_280px]">
                <div>
                  <Dialogue.Title className="text-[20px] font-semibold">Plan {ouvert.numero}</Dialogue.Title>
                  <Dialogue.Description className="copiable mt-3 text-[16px] leading-relaxed text-texte/90">
                    {ouvert.texte ? `« ${ouvert.texte} »` : "Aucun texte dit sur ce plan."}
                  </Dialogue.Description>
                  {ouvert.description && (
                    <div className="mt-6">
                      <div className="mb-1.5 text-[12px] font-semibold tracking-[0.1em] text-pale uppercase">Ce que montre l'image</div>
                      <p className="copiable text-[14px] leading-relaxed text-doux">{ouvert.description}</p>
                    </div>
                  )}
                  {ouvert.decoupe && ouvert.decoupe.length > 1 && (
                    <div className="mt-6">
                      <div className="mb-2.5 text-[12px] font-semibold tracking-[0.1em] text-pale uppercase">Découpage en plans</div>
                      <div className="flex flex-wrap gap-3">
                        {ouvert.decoupe.map((d, i) => (
                          <figure key={i} className="w-[172px]">
                            <Image chemin={imagePlan(ouvert, narrateur)} largeur={640} cadre={d.cadre} className="aspect-video rounded-[10px] ring-1 ring-ligne" />
                            <figcaption className="mt-1.5 flex justify-between text-[12px] text-doux">
                              <span>{VALEURS[d.valeur ?? ""] ?? "plan"}</span>
                              <span className={cx("tabular-nums", d.duree > MAX_IMAGE_S && "font-semibold text-ambre-vif")}>{duree(d.duree)}</span>
                            </figcaption>
                          </figure>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex flex-col gap-4 text-[13px]">
                  <Info nom="Début" valeur={horloge(ouvert.debut)} />
                  <Info nom="Durée" valeur={`${duree(ouvert.duree)}${ouvert.estimee ? " (estimée)" : ""}`} alerte={tropLong(ouvert)} />
                  <Info nom="Scènes" valeur={ouvert.scenes.map((s) => s.id).join(", ")} />
                  {ouvert.personnages.length > 0 && (
                    <div>
                      <div className="mb-2 text-pale">Personnages</div>
                      <div className="flex flex-wrap gap-2">
                        {ouvert.personnages.map((n) => (
                          <span key={n} className="inline-flex items-center gap-2 rounded-full bg-carte-2 py-1 pr-3 pl-1 ring-1 ring-ligne">
                            <Avatar nom={n} chemin={portraits[n]} taille={24} /> {n}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Dialogue.Content>
          )}
        </Dialogue.Portal>
      </Dialogue.Root>
    </>
  );
}

function Info({ nom, valeur, alerte }: { nom: string; valeur: string; alerte?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-ligne pb-3">
      <span className="text-pale">{nom}</span>
      <span className={cx("font-medium tabular-nums", alerte && "text-ambre-vif")}>{valeur}</span>
    </div>
  );
}

function CartePlan({ plan: p, image, portraits, ouvrir }: { plan: PlanLu; image?: string; portraits: Record<string, string>; ouvrir(): void }) {
  const long = tropLong(p);
  return (
    <div id={`plan-${p.n}`} className="group flex scroll-mt-24 flex-col overflow-hidden rounded-carte border border-ligne bg-carte transition-colors hover:border-ligne-forte">
      <button onClick={ouvrir} className="relative block text-left outline-none">
        <Image chemin={image} largeur={640} className="aspect-video" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/30" />
        <span className="titre-image absolute top-3 left-3.5 text-[13px] font-semibold text-white">Plan {p.numero}</span>
        <span className="titre-image absolute right-3.5 bottom-3 text-[12px] font-medium text-white/85 tabular-nums">{horloge(p.debut)}</span>
        <span
          className={cx(
            "absolute top-3 right-3 rounded-full px-2.5 py-0.5 text-[12px] font-semibold tabular-nums backdrop-blur-md",
            long ? "bg-ambre text-[#1b1406]" : "bg-black/55 text-white",
          )}
        >
          {p.estimee && "≈ "}
          {duree(p.duree)}
          {p.decoupe && p.decoupe.length > 1 && <span className="font-normal opacity-80"> · {p.decoupe.length} plans</span>}
        </span>
      </button>
      <div className="flex flex-1 flex-col p-4">
        <p className="line-clamp-4 text-[14px] leading-relaxed text-texte/90">{p.texte || <span className="text-pale">Aucun texte dit.</span>}</p>
        <div className="mt-auto flex items-center justify-between gap-3 pt-4">
          <div className="flex -space-x-1.5">
            {p.personnages.slice(0, 4).map((n) => (
              <Avatar key={n} nom={n} chemin={portraits[n]} taille={26} />
            ))}
          </div>
          <BoutonEcoute cle={`plan-${p.n}`} sons={p.voix} petit />
        </div>
      </div>
    </div>
  );
}

function Videos({ rendus, titre, affiche }: { rendus?: RendusBramble; titre: string; affiche?: string }) {
  const [choisie, setChoisie] = useState(0);
  if (!rendus) return <Squelette className="aspect-video w-full" />;
  if (!rendus.videos.length)
    return <Vide icone={<Film className="size-5" />} titre="Pas encore de vidéo" texte="La vidéo finie de cet épisode apparaîtra ici, dans chaque langue." />;
  const v = rendus.videos[Math.min(choisie, rendus.videos.length - 1)];
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="overflow-hidden rounded-[16px] bg-black ring-1 ring-ligne">
        <video key={v.chemin} src={fichier(v.chemin)} poster={affiche ? fichier(affiche, 1280) : undefined} controls preload="metadata" className="aspect-video w-full bg-black" controlsList="nodownload noplaybackrate" />
      </div>
      <div>
        <div className="mb-1 text-[15px] font-medium">{titre}</div>
        <div className="mb-5 text-[13px] text-doux">Version fabriquée par Bramble Studio</div>
        <div className="mb-2 text-[12px] font-semibold tracking-[0.1em] text-pale uppercase">Langue</div>
        <div className="flex flex-col gap-1">
          {rendus.videos.map((x, i) => (
            <button
              key={x.chemin}
              onClick={() => setChoisie(i)}
              className={cx(
                "flex h-10 items-center justify-between rounded-[10px] px-3 text-[14px] transition-colors",
                x === v ? "bg-survol font-medium text-texte" : "text-doux hover:bg-carte-2 hover:text-texte",
              )}
            >
              {nomLangue(x.langue)}
              {x === v && <Check className="size-4 text-ambre" />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
