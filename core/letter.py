"""
core/letter.py — Génération de lettres de motivation par template fixe.

L'IA ne rédige RIEN. Elle extrait uniquement les valeurs des placeholders
depuis les données de l'offre. La lettre de Lilian reste intacte.
"""

import os
import json
import requests
from typing import Optional

# ── Template FIGÉ de Lilian ──────────────────────────────────────────────
# Seuls les placeholders entre [CROCHETS] seront remplacés.
# NE PAS MODIFIER LE TEXTE EN DEHORS DES PLACEHOLDERS.

LETTRE_TEMPLATE = """Madame, Monsieur,

Admis en BTS Professions Immobilières à l'ISTEF Toulouse pour la rentrée de septembre, je souhaite intégrer "[NOM_AGENCE]" dans une logique progressive et cohérente : un stage conventionné dans un premier temps, suivi d'une alternance dès mi-juin ou mi-juillet, afin d'arriver à la rentrée avec une base opérationnelle déjà structurée.

La période de mars à mi-juin correspond à mes créneaux pleinement disponibles pour m'investir en stage. Cette disponibilité me permettrait de m'immerger dans votre environnement, d'observer vos pratiques et de développer rapidement une compréhension concrète de vos méthodes et de votre positionnement singulier sur le marché [ZONE_GEOGRAPHIQUE].

Rejoindre "[NOM_AGENCE]" représente pour moi bien plus qu'une première expérience en immobilier. [DESCRIPTION_AGENCE]. Cette vision suppose une capacité à comprendre l'atmosphère d'un espace, à en identifier le public cible et à structurer un discours aligné avec ce positionnement.

Mon parcours m'a appris la discipline, la résilience et l'analyse stratégique. Il m'a surtout permis de développer une posture d'observation et d'adaptation : comprendre avant d'agir, analyser avant de proposer et inscrire chaque action dans une logique de cohérence professionnelle, ce qui me semble indispensable dans un univers aussi [ADJECTIF_UNIVERS] que le vôtre.

Je ne conçois pas ce stage comme une phase d'observation passive, mais comme une implication réelle : prospection ciblée, qualification de biens, accompagnement en visite, participation à la mise en valeur des annonces et compréhension approfondie du processus de commercialisation. L'alternance serait la continuité naturelle d'un engagement déjà démontré sur le terrain à vos côtés.

Je serais honoré de pouvoir vous rencontrer afin d'échanger plus concrètement sur ma démarche et sur la valeur que je pourrais apporter à votre [TYPE_STRUCTURE].

Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.

Lilian Chabrolle
06 64 77 44 97
Lilianchabrolle@hotmail.com
27 rue de Puymaurin 31400"""


# ── Prompt d'extraction — l'IA ne rédige rien, elle extrait ──────────────

PROMPT_EXTRACTION = """Tu es un assistant d'extraction de données. Tu ne rédiges RIEN.
Tu analyses une offre d'emploi immobilier et tu extrais exactement 5 valeurs.

OFFRE À ANALYSER :
- Titre : {titre}
- Entreprise : {entreprise}
- Ville : {ville}
- Description : {description}

RÈGLES STRICTES :
1. NOM_AGENCE : Le nom exact de l'entreprise/agence tel qu'il apparaît dans l'offre. Si absent, utilise le titre du poste + ville.
2. ZONE_GEOGRAPHIQUE : La zone de marché (ex: "toulousain", "de la métropole lilloise", "du centre-ville de Bordeaux"). Déduis-la de la ville.
3. DESCRIPTION_AGENCE : UNE SEULE phrase (max 30 mots) décrivant le positionnement ou la spécialité de l'agence, basée sur les infos de l'offre. Commence par "Votre agence..." ou "Votre cabinet...". Si aucune info, écris "Votre structure se distingue par son ancrage local et son approche personnalisée du conseil immobilier".
4. ADJECTIF_UNIVERS : UN SEUL adjectif qualifiant l'univers de l'agence (ex: "exigeant", "compétitif", "sélectif", "dynamique", "structuré"). Choisis en fonction du ton de l'offre.
5. TYPE_STRUCTURE : "agence", "cabinet", "groupe" ou "structure" — choisis le plus adapté.

RÉPONDS UNIQUEMENT en JSON valide, sans markdown, sans commentaire :
{{"NOM_AGENCE": "...", "ZONE_GEOGRAPHIQUE": "...", "DESCRIPTION_AGENCE": "...", "ADJECTIF_UNIVERS": "...", "TYPE_STRUCTURE": "..."}}"""


# ── Valeurs par défaut si l'IA échoue ────────────────────────────────────

VALEURS_DEFAUT = {
    "NOM_AGENCE": "votre agence",
    "ZONE_GEOGRAPHIQUE": "toulousain",
    "DESCRIPTION_AGENCE": "Votre structure se distingue par son ancrage local et son approche personnalisée du conseil immobilier",
    "ADJECTIF_UNIVERS": "exigeant",
    "TYPE_STRUCTURE": "agence",
}


def extraire_placeholders(
    titre: str,
    entreprise: str,
    ville: str,
    description: str,
    api_key: Optional[str] = None,
) -> dict[str, str]:
    """
    Appelle Claude via OpenRouter pour extraire les 5 valeurs de placeholders.
    Retourne un dict avec les 5 clés, ou les valeurs par défaut en cas d'échec.
    """
    cle_api = api_key or os.getenv("OPENROUTER_API_KEY", "")
    if not cle_api:
        print("[LETTER] ⚠️ Pas de clé OpenRouter — valeurs par défaut utilisées.")
        return _appliquer_defaut_ville(ville)

    prompt = PROMPT_EXTRACTION.format(
        titre=titre or "Non précisé",
        entreprise=entreprise or "Non précisée",
        ville=ville or "Non précisée",
        description=(description or "Aucune description")[:2000],  # Tronquer si trop long
    )

    try:
        reponse = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {cle_api}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-sonnet-4-5",
                "max_tokens": 300,
                "temperature": 0.1,  # Très déterministe pour l'extraction
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        reponse.raise_for_status()
        data = reponse.json()

        # Extraire le texte de la réponse
        contenu = data["choices"][0]["message"]["content"].strip()

        # Nettoyer si l'IA a mis des backticks markdown
        contenu = contenu.replace("```json", "").replace("```", "").strip()

        valeurs = json.loads(contenu)

        # Vérifier que toutes les clés sont présentes
        resultat = {}
        for cle in VALEURS_DEFAUT:
            valeur = valeurs.get(cle, "").strip()
            if valeur:
                resultat[cle] = valeur
            else:
                resultat[cle] = VALEURS_DEFAUT[cle]
                print(f"[LETTER] ⚠️ Clé '{cle}' vide — défaut utilisé.")

        print(f"[LETTER] ✅ Extraction réussie pour : {entreprise or titre}")
        return resultat

    except json.JSONDecodeError as e:
        print(f"[LETTER] ❌ JSON invalide de l'IA : {e}")
        return _appliquer_defaut_ville(ville)
    except requests.exceptions.RequestException as e:
        print(f"[LETTER] ❌ Erreur API OpenRouter : {e}")
        return _appliquer_defaut_ville(ville)
    except (KeyError, IndexError) as e:
        print(f"[LETTER] ❌ Réponse API inattendue : {e}")
        return _appliquer_defaut_ville(ville)


def _appliquer_defaut_ville(ville: str) -> dict[str, str]:
    """Retourne les valeurs par défaut en adaptant la zone géo à la ville."""
    defaut = VALEURS_DEFAUT.copy()
    if ville:
        ville_lower = ville.lower().strip()
        # Adapter la zone géographique à la ville de l'offre
        if "toulouse" in ville_lower:
            defaut["ZONE_GEOGRAPHIQUE"] = "toulousain"
        elif "paris" in ville_lower:
            defaut["ZONE_GEOGRAPHIQUE"] = "parisien"
        elif "lyon" in ville_lower:
            defaut["ZONE_GEOGRAPHIQUE"] = "lyonnais"
        elif "bordeaux" in ville_lower:
            defaut["ZONE_GEOGRAPHIQUE"] = "bordelais"
        elif "montpellier" in ville_lower:
            defaut["ZONE_GEOGRAPHIQUE"] = "montpelliérain"
        else:
            defaut["ZONE_GEOGRAPHIQUE"] = f"de {ville.strip()}"
    return defaut


def generer_lettre(
    offre_ou_titre,
    profil_ou_entreprise=None,
    ville: str = "",
    description: str = "",
    api_key: Optional[str] = None,
) -> str:
    """
    Génère la lettre de motivation complète.
    Accepte DEUX signatures :
      - generer_lettre(offre_dict, profil_dict)  ← appelé par app.py
      - generer_lettre(titre, entreprise, ville, description)  ← appel direct
    """
    # Détection automatique de la signature utilisée
    if isinstance(offre_ou_titre, dict):
        # Appelé depuis app.py : generer_lettre(offre, PROFIL)
        offre = offre_ou_titre
        titre = offre.get("titre", "")
        entreprise = offre.get("entreprise", "")
        ville = offre.get("ville", "")
        description = offre.get("description", "")
    else:
        # Appel direct avec des strings
        titre = offre_ou_titre
        entreprise = profil_ou_entreprise or ""

    valeurs = extraire_placeholders(titre, entreprise, ville, description, api_key)

    lettre = LETTRE_TEMPLATE
    for cle, valeur in valeurs.items():
        lettre = lettre.replace(f"[{cle}]", valeur)

    # Vérification finale : aucun placeholder restant
    placeholders_restants = [
        p for p in ["[NOM_AGENCE]", "[ZONE_GEOGRAPHIQUE]", "[DESCRIPTION_AGENCE]",
                     "[ADJECTIF_UNIVERS]", "[TYPE_STRUCTURE]"]
        if p in lettre
    ]
    if placeholders_restants:
        print(f"[LETTER] ⚠️ Placeholders non remplacés : {placeholders_restants}")
        # Forcer le remplacement par les défauts
        for p in placeholders_restants:
            cle = p.strip("[]")
            lettre = lettre.replace(p, VALEURS_DEFAUT[cle])

    return lettre


# ── Test rapide en standalone ────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Exemple avec une offre fictive
    lettre = generer_lettre(
        titre="Alternance BTS Professions Immobilières",
        entreprise="Immobilière du Sud",
        ville="Toulouse",
        description="Cabinet spécialisé dans l'immobilier de prestige à Toulouse. "
                    "Nous recherchons un alternant pour notre équipe transaction. "
                    "Gestion de biens haut de gamme, prospection, visites.",
    )
    print("=" * 60)
    print(lettre)
    print("=" * 60)
