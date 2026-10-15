# Azurik — Menu debug

La version **1.1.0** enrichit le menu debug déjà présent dans *Azurik: Rise of
Perathia* : caméra libre, aperçus de boîtes de texte et de voix d'oracles, et ajout
de clés. En pleine partie, appuyez sur **BLANC → A → B en moins d'une seconde**.
Après une fermeture normale, relâchez les boutons et recommencez pour rouvrir le
menu, sans refaire le code triche.

Le menu du jeu est **en anglais** et affiche **Debug Menu - 1.1.0**. Le logiciel
Windows installe cette version dans une nouvelle copie de votre ISO **PAL / Europe**.
Ce dépôt et ses téléchargements ne contiennent aucune copie du jeu.

[Télécharger la version 1.1.0](https://github.com/Azurik-Modding-Hub/Azurik-Debug-Menu/releases/tag/v1.1.0)
· [Documentation anglaise](README.md)
· [Guide détaillé en anglais](docs/LABORATORY.md)
· [Azurik Level Editor](https://github.com/Azurik-Modding-Hub/Azurik-Level-Editor)

![Interface réelle du logiciel Windows 1.1.0](docs/screenshots/patcher-1.1.0.png)

Capture de l'interface du logiciel Windows 1.1.0 ; elle ne montre pas un test en jeu.

![Organisation du menu 1.1.0 — schéma explicatif](docs/screenshots/native-menu-1.1.0.png)

Schéma explicatif de l'organisation du menu ; ce n'est pas une capture du jeu.

## Fonctionnalités

Le menu principal comporte **six entrées** : **Change level...**, **Play Movie...**,
**Game state...**, **Freecam**, **Text boxes** et **Oracles**.

- **Freecam** active la caméra libre d'origine. Les commandes de déplacement,
  d'attaque et de saut d'Azurik sont bloquées ; ses animations de repos, sa physique
  et le monde continuent. **BLANC** ou **BACK** quitte la caméra, **Y** masque ou
  réaffiche le HUD.
- **Text boxes** propose 67 séquences originales de boîtes de texte, avec leurs
  voix lorsqu'elles existent. Les panneaux des sceaux et les messages liés aux
  fragments/sceaux sont ici. Les enregistrements sans panneau identifié portent
  explicitement **(voice only)**.
- **Oracles** contient les introductions des royaumes et les autres conseils
  parlés. Les messages de fragments/sceaux restent dans Text boxes. **Stop voice**
  arrête un aperçu audio.
- **Game state → Keys (5 inventory slots)** donne accès aux 20 types de clés
  vérifiés, classés par royaume. **Give: ...** utilise la routine d'inventaire
  d'origine. Une clé portée n'est pas dupliquée ; si les cinq places sont prises,
  aucune clé n'est remplacée.

La rubrique **Animations** et la lecture manuelle d'animations ont été retirées.
Les animations normales du jeu sont conservées. Le code commun de la caméra
s'applique à tous les royaumes jouables de la version européenne prise en charge ;
leur fonctionnement complet reste à confirmer en jeu.

## Installation

1. Téléchargez et extrayez le logiciel Windows de la
   [release 1.1.0](https://github.com/Azurik-Modding-Hub/Azurik-Debug-Menu/releases/tag/v1.1.0).
2. Ouvrez **Azurik Freecam Patcher.exe** et choisissez votre ISO/XISO d'Azurik.
3. Choisissez un nom de **nouvelle ISO**. Le logiciel copie, modifie et vérifie
   l'image. Il ne remplace aucun fichier de sortie existant.
4. Chargez cette nouvelle ISO dans Xemu et redémarrez complètement la console.
   Ne reprenez pas un ancien instantané conservant l'ancien programme.
5. Dans une partie chargée, appuyez sur **BLANC → A → B en moins d'une seconde**.

Vérifiez l'en-tête **Debug Menu - 1.1.0** et les six entrées principales. Un ancien
nom ou seulement trois/quatre entrées signifie qu'une ancienne version est encore
chargée. L'ISO source reste conservée ; la relancer permet de revenir au jeu d'origine.

## Commandes

| Action | Boutons Xbox |
| --- | --- |
| Ouvrir ou rouvrir le menu | **BLANC**, puis **A**, puis **B**, en moins d'une seconde |
| Autre raccourci | **L3 + START** |
| Valider une entrée | Commandes natives du menu, validation avec **START** |
| Activer la caméra libre | **Freecam**, puis **START** |
| Déplacer et orienter la caméra | Commandes natives de la caméra |
| Masquer / afficher le HUD en Freecam | **Y** |
| Quitter la Freecam | **BLANC** ou **BACK** |

La seconde démarre à l'appui sur BLANC. Vous pouvez relâcher les boutons entre les
étapes ou les maintenir. Relâchez les boutons avant une nouvelle séquence. Après
expiration, recommencez avec un nouvel appui sur BLANC. Le menu fermé normalement
est réutilisé : le raccourci n'empile pas plusieurs fenêtres. Le code d'origine
reste disponible.

BLANC seul quitte toujours la Freecam. Les commandes supplémentaires de triche
qui pouvaient provoquer un saut ou une poussée avec BLANC restent désactivées.
Le HUD retrouve son état précédent en quittant la caméra.

EDIT : You need to clear the cache for the changes you make to take effect ! Don’t worry, this won’t affect your save files in any way!

Pour le cache Xbox, utilisez uniquement **X / Y / Z**. Gardez la partition **E**
et le disque virtuel contenant vos sauvegardes. Le logiciel ne les efface pas et
ne modifie pas les paramètres de Xemu ni l'EEPROM.

## Compatibilité et limites

Seul le programme européen d'origine pris en charge est accepté. Une ISO avec des
niveaux modifiés convient si son `default.xbe` reste d'origine. Les fichiers des
niveaux ne sont pas changés par ce logiciel. Les autres régions, les fichiers
incomplets et les exécutables déjà modifiés sont refusés.

Les aperçus de panneaux et de voix sont lancés après la fermeture du menu, dans le
même monde chargé, sans modifier les drapeaux de quête. L'ajout de clés modifie
l'inventaire et peut être conservé par une sauvegarde normale du jeu. Un aperçu de
voix ne crée pas d'apparition d'oracle ni de nouveau panneau correspondant.
La langue du jeu détermine la lecture ; les voix originales des panneaux de démo
existent uniquement en anglais. La différence de nom d'origine entre le panneau
et la voix du miroir E6 n'est pas corrigée par cet outil limité à l'exécutable.

Les portails déclenchés par le personnage restent liés à sa position. La gravité,
les plateformes mobiles et les actions scriptées continuent normalement.

**247 tests automatisés ont réussi**, avec l'installation de la version actuelle
par le logiciel et la ligne de commande. Le programme Windows compilé a produit
le correctif 1.1.0 attendu et une ISO entièrement vérifiée, sans modifier l'originale.
Ces tests natifs isolés et la relecture de l'ISO ne remplacent pas une partie dans
Xemu. **Le fonctionnement complet en jeu reste à confirmer**, notamment les
ouvertures/fermetures répétées, les transitions, le HUD, les voix, les panneaux,
le repos d'Azurik et la reprise de ses commandes.
