/* Lanceur natif de Fabrique (« Fabrique.exe »), repris de Bramble Studio.
   Charge runtime\python312.dll dans CE processus et joue « -B -m fabrique <arguments> » : chaque processus de Fabrique porte le nom de l'exe.
   Sous-système fenêtre (jamais de console), sans bibliothèque C : kernel32, user32, shell32 seulement.
   Les chemins de Python viennent de runtime\python312._pth (à côté de la DLL), jamais de PYTHONHOME ni de PYTHONPATH :
   les outils lancés par l'app (ComfyUI, environnements, WSL) en hériteraient. */
#include <windows.h>
#include <shellapi.h>

#define MAXC 32768 /* longueur maximale d'un chemin long de Windows */
#define DLL L"\\runtime\\python312.dll"
#define LISTE L"fichiers.txt" /* écrit par outils_dev/construire.py : chaque fichier du programme, chemin relatif, UTF-16, un par ligne */
#define VERSIONS L"\\versions\\" /* à côté du programme : <racine>\versions\Fabrique <n> - Installation.exe */

typedef int (*py_main)(int, wchar_t **);
/* statiques : pas de grande pile sans la bibliothèque C (__chkstk) */
static wchar_t exe[MAXC], dll[MAXC], chemin[MAXC + 4], manque[MAXC], installateur[MAXC], message[1100];

static void echec(const wchar_t *texte)
{
    MessageBoxW(NULL, texte, L"Fabrique", MB_OK | MB_ICONERROR);
    ExitProcess(1);
}

/* Combien de fichiers de la liste manquent dans `dossier` (le premier dans « manque ») ; la liste elle-même effacée ou illisible compte (elle est
   livrée avec ce lanceur). Seul un fichier introuvable compte : un refus d'accès n'empêche pas de démarrer.
   Préfixe \\?\ : un chemin de plus de 260 caractères n'est jamais un faux manque. */
static int manquants(const wchar_t *dossier)
{
    HANDLE h;
    DWORD taille, lus;
    wchar_t *liste, *l, *p, *fin;
    int n = 0;

    lstrcpyW(chemin, dossier[0] == L'\\' ? L"" : L"\\\\?\\");
    lstrcatW(chemin, dossier);
    fin = chemin + lstrlenW(chemin);
    lstrcpyW(fin, LISTE);
    h = CreateFileW(chemin, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    taille = h == INVALID_HANDLE_VALUE ? INVALID_FILE_SIZE : GetFileSize(h, NULL);
    liste = taille == INVALID_FILE_SIZE ? NULL : HeapAlloc(GetProcessHeap(), 0, taille + 2 * sizeof *liste);
    if (!liste || !ReadFile(h, liste, taille, &lus, NULL) || lus != taille) {
        if (h != INVALID_HANDLE_VALUE)
            CloseHandle(h);
        lstrcpyW(manque, LISTE);
        return 1;
    }
    CloseHandle(h);
    liste[taille / sizeof *liste] = 0;
    for (l = liste; *l; l = p) {
        for (p = l; *p && *p != L'\r' && *p != L'\n'; p++)
            ;
        while (*p == L'\r' || *p == L'\n')
            *p++ = 0;
        if (*l && fin - chemin + lstrlenW(l) < MAXC) {
            lstrcpyW(fin, l);
            if (GetFileAttributesW(chemin) == INVALID_FILE_ATTRIBUTES && (GetLastError() == ERROR_FILE_NOT_FOUND || GetLastError() == ERROR_PATH_NOT_FOUND)
                && !n++)
                lstrcpyW(manque, l);
        }
    }
    return n;
}

/* Le programme abîmé (fichiers effacés : désinstallation interrompue, 22/11) ne meurt plus en silence : réparation proposée par le plus récent
   installateur du dossier versions (les données ne sont pas dans le programme). `fin` : la dernière barre de `dll` (« …\programme\ »). */
static void verifier(wchar_t *fin)
{
    WIN32_FIND_DATAW d;
    FILETIME recent = {0, 0};
    HANDLE f;
    wchar_t *nom;
    int n = manquants(dll);

    if (!n)
        return;
    f = OpenMutexW(SYNCHRONIZE, FALSE, L"StudioKids.Fabrique.Installation"); /* SetupMutex de installateur/fabrique.iss */
    if (f)
        echec(L"Fabrique est en train de s'installer ou de se mettre à jour.\n\nRelancez Fabrique quand l'installation est finie.");
    for (*fin = 0; fin > dll && *fin != L'\\'; fin--) /* remonte de « …\programme » à « … » */
        ;
    lstrcpyW(fin, VERSIONS L"Fabrique * - Installation.exe");
    nom = fin + lstrlenW(VERSIONS);
    installateur[0] = 0;
    f = FindFirstFileW(dll, &d);
    if (f != INVALID_HANDLE_VALUE) {
        do
            if (CompareFileTime(&d.ftLastWriteTime, &recent) > 0 && nom - dll + lstrlenW(d.cFileName) < MAXC) {
                recent = d.ftLastWriteTime;
                lstrcpyW(nom, d.cFileName);
                lstrcpyW(installateur, dll);
            }
        while (FindNextFileW(f, &d));
        FindClose(f);
    }
    if (!installateur[0]) {
        wsprintfW(message, L"Fabrique est abîmé : %d fichier(s) du programme manquent, dont « %.300s ».\n\n"
                           L"Réinstallez Fabrique (aucun installateur dans le dossier « versions »).", n, manque);
        echec(message);
    }
    wsprintfW(message, L"Fabrique est abîmé : %d fichier(s) du programme manquent, dont « %.300s ».\n\n"
                       L"Réparer maintenant avec « %.200s » ? Vos sessions et vos données sont gardées.", n, manque, installateur + (nom - dll));
    if (MessageBoxW(NULL, message, L"Fabrique", MB_YESNO | MB_ICONERROR) == IDYES
        && (INT_PTR)ShellExecuteW(NULL, L"open", installateur, NULL, NULL, SW_SHOWNORMAL) <= 32) /* refusé (droits, antivirus) : le dire */
        echec(L"L'installateur n'a pas pu être lancé.\n\nOuvrez le dossier « versions » de Fabrique et lancez le plus récent vous-même.");
    ExitProcess(1);
}

void entree(void)
{
    int argc = 0, i, rt;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc), **args, *p, *fin = NULL;
    DWORD n = GetModuleFileNameW(NULL, exe, MAXC);
    HMODULE python;
    py_main Py_Main;

    if (!argv || !n || n + lstrlenW(DLL) >= MAXC)
        echec(L"Fabrique n'a pas pu lire son propre emplacement.");
    lstrcpyW(dll, exe);
    for (p = dll; *p; p++)
        if (*p == L'\\')
            fin = p;
    if (!fin)
        echec(L"Fabrique n'a pas pu lire son propre emplacement.");
    rt = argc == 1 || (argc == 2 && !lstrcmpiW(argv[1], L"--fond")); /* lancée par RT (clic, démarrage de Windows), pas par un programme */
    if (rt) {
        fin[1] = 0;
        verifier(fin);
    }
    lstrcpyW(fin, DLL);
    python = LoadLibraryExW(dll, NULL, LOAD_WITH_ALTERED_SEARCH_PATH); /* ses DLL voisines (vcruntime140) viennent du même dossier */
    Py_Main = python ? (py_main)GetProcAddress(python, "Py_Main") : NULL;
    if (!Py_Main && !rt) /* appelée par un programme (installateur : « libre », « arreter », cachés) : une boîte invisible le bloquerait */
        ExitProcess(1);
    if (!Py_Main)
        echec(L"Fabrique est incomplet : le dossier « runtime » est absent ou abîmé.\n\nRéinstallez Fabrique.");
    args = HeapAlloc(GetProcessHeap(), 0, (argc + 4) * sizeof *args);
    if (!args)
        echec(L"Mémoire insuffisante pour démarrer Fabrique.");
    args[0] = exe;
    args[1] = L"-B"; /* le dossier du programme n'est jamais écrit : le code y est précompilé */
    args[2] = L"-m";
    args[3] = L"fabrique";
    for (i = 1; i < argc; i++)
        args[i + 3] = argv[i];
    args[argc + 3] = NULL;
    ExitProcess((UINT)Py_Main(argc + 3, args));
}
