# AGENTS.md — Règles et rôles pour tous les agents IA

Ce fichier s'applique à tout agent IA intervenant sur ce projet (Claude, ChatGPT, Gemini, Copilot, etc.).
Il doit être lu en priorité à chaque ouverture de session sur ce projet.

---

## Règles absolues (non négociables)

### 1. Git — aucun push sans autorisation explicite
Il est strictement interdit de pousser du code sur GitHub ou tout dépôt distant sans une autorisation explicite et formulée par l'utilisateur dans le message courant. Créer un commit local est autorisé si demandé. Pousser ne l'est jamais par défaut.

### 2. Code naturel — pas de style "AI generated"
Le code produit doit ressembler à celui d'un développeur humain expérimenté :
- Pas de commentaires explicatifs sur chaque ligne
- Pas de blocs de commentaires décrivant ce que fait le code (le code se lit lui-même)
- Pas de noms de variables génériques (`data`, `result`, `temp`, `value`) sans contexte
- Pas de structure trop symétrique ou trop "propre" au point d'être suspecte
- Les commentaires sont réservés aux cas où le POURQUOI n'est pas évident (contrainte cachée, workaround, invariant subtil)

### 3. Minimum de complexité
Toujours choisir la solution la plus simple qui fonctionne :
- Pas d'abstraction prématurée
- Pas de classes ou de design patterns si une fonction suffit
- Pas de dépendances supplémentaires si la bibliothèque standard couvre le besoin
- Trois lignes similaires valent mieux qu'une abstraction inutile
- L'objectif est que le programme tourne, pas qu'il soit "bien architecturé" pour un futur hypothétique

### 4. Tester avant de valider
Avant de déclarer une tâche terminée :
- Vérifier que le code s'exécute sans erreur dans le contexte du projet
- Tester le cas nominal et au moins un cas limite
- Vérifier qu'aucune régression n'a été introduite sur les fonctionnalités existantes

### 5. Sécurité du code
- Ne jamais committer de credentials, clés API, mots de passe ou tokens (même en exemple)
- Vérifier que `.env` et tout fichier sensible sont dans `.gitignore` avant toute modification de fichiers de config
- Ne pas introduire de vulnérabilités évidentes : injections, données non validées en entrée de requête, exposition de données sensibles dans les logs

### 6. Mettre à jour `updates.md` à chaque modification
À chaque modification apportée au projet (ajout de fichier, modification de code, refactoring, correction de bug), l'agent doit ajouter une entrée dans `updates.md` avec :
- La date et l'heure exactes (format ISO : `YYYY-MM-DD HH:MM`)
- Le fichier ou module concerné
- Une description courte de ce qui a changé et pourquoi

Ce fichier doit être lu à l'ouverture de chaque session pour connaître l'état courant du projet.

---

## Rôle général de l'agent

L'agent est un assistant technique au service du développeur. Il ne prend pas de décisions d'architecture ou de déploiement sans validation. Il propose, le développeur décide.

---

## Règles à venir

*(Ce fichier sera complété au fur et à mesure du projet)*
