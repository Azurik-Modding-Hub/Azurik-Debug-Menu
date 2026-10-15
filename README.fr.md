# Azurik — Menu debug

Version **1.0.0** pour le jeu Xbox **PAL / Europe**. Le menu debug déjà intégré au jeu reçoit
une entrée **Freecam** qui active la caméra du code triche d'origine.
Le monde continue de fonctionner. Les commandes de déplacement, de saut et
d'attaque d'Azurik sont neutralisées pendant la caméra libre ; ses animations
d'attente, sa physique et ses mises à jour continuent normalement.

Le correctif utilise le programme commun du jeu et la caméra du royaume chargé.
Il s'applique à **tous les royaumes jouables** de cette version européenne,
sans restriction à W1. Leur fonctionnement reste à vérifier dans le jeu.
Activez la caméra pendant une partie chargée, hors écran titre et chargement.

**Freecam apparaît comme quatrième entrée du menu debug d'Azurik**, au même
endroit que les trois entrées européennes d'origine **Change level...**,
**Play Movie...** et **Game state...**. Les trois entrées existantes sont
conservées. Aucun sous-menu supplémentaire n'est nécessaire. Le logiciel
Windows installe ce changement dans l'ISO ; le menu s'utilise ensuite en jeu.

L'ancien texte de build est remplacé dans l'en-tête par
**Commande menue - 1.0.0**. Pour ouvrir ce menu pendant une partie,
appuyez sur **L3 + START**, choisissez **Freecam**, puis confirmez avec **START**.

La version **1.0.0 corrige Azurik qui reste figé après la sortie**. Le blocage
précédent coupait aussi la remise à jour du personnage pour les images suivantes.
Le correctif bloque maintenant uniquement ses commandes par le chemin natif du
jeu, et conserve son animation. Le drapeau natif de la caméra libère les commandes
dès la sortie, même si une ancienne référence à la caméra subsiste brièvement.
L'animation d'attente et la reprise des commandes restent à confirmer dans Xemu.

La gravité, les plateformes mobiles et les scripts gardent leur fonctionnement
normal pendant la caméra libre.

[Télécharger le correctif de test 1.0.0](https://github.com/Azurik-Modding-Hub/Azurik-Debug-Menu/releases/tag/v1.0.0)

## Utilisation

1. Ouvrez **Azurik Freecam Patcher.exe** depuis les téléchargements du dépôt.
2. Choisissez votre ISO Xbox d'Azurik, puis le nom d'une **nouvelle ISO**.
3. Attendez la copie et la vérification. L'original et les sauvegardes sont conservés.
4. Chargez cette nouvelle ISO dans Xemu et redémarrez complètement la console.
5. En jeu, utilisez **L3 + START** pour ouvrir le menu debug. Sélectionnez
   **Freecam**, puis validez avec **START**.
6. **Y** masque ou réaffiche le HUD. **Blanc** quitte la caméra libre;
   **BACK** fonctionne aussi. Le HUD retrouve son état précédent à la sortie.

Le code d'origine fonctionne également : **RT, bas, haut, bas, haut, R3, L3**.
Utilisez la croix directionnelle, relâchez chaque bouton entre les étapes et
ne maintenez pas RT pendant toute la séquence.

EDIT : You need to clear the cache for the changes you make to take effect ! Don’t worry, this won’t affect your save files in any way!

Pour le cache Xbox, utilisez uniquement **X / Y / Z**. Gardez la partition **E**
et le disque virtuel contenant vos sauvegardes. Le logiciel ne les efface pas.
Évitez de reprendre un ancien snapshot de Xemu qui conserve l'ancien programme.
Si le menu ne comporte que trois entrées, vérifiez que Xemu utilise bien la
nouvelle ISO, puis redémarrez complètement cette copie.

## Compatibilité et vérifications

Le programme d'origine doit être la version PAL / Europe prise en charge.
Une ISO avec des niveaux déjà modifiés est acceptée si son `default.xbe` reste
d'origine. Les niveaux, dont W1, ne sont pas changés par cet outil.
Les anciennes ISO et les fichiers existants ne sont pas remplacés.

Les instructions ont été vérifiées dans des tests x86 isolés et le contenu de
l'ISO est relu après construction. **Le fonctionnement complet dans le jeu
reste à tester**, notamment les collisions, les transitions de menu et le HUD.
Les portails déclenchés par le personnage restent liés au personnage.

Ce dépôt contient les sources et l'outil d'installation; il ne contient aucune
copie du jeu. Pour revenir à l'état d'origine, utilisez votre ISO précédente.

## Prochains ajouts

Ce dépôt accueillera les futurs outils ajoutés à ce même menu debug du jeu.
La première version de test concerne la caméra libre. L'outil Windows installe
la modification dans une nouvelle ISO; le menu s'utilise ensuite dans Azurik.

[Documentation anglaise et installation depuis Python](README.md)
· [Azurik Level Editor](https://github.com/Azurik-Modding-Hub/Azurik-Level-Editor)

## Aperçu de développement 1.1.0-dev.3

Appuyer sur **BLANC, puis A, puis B en moins d’une seconde** ouvre le menu.
Les boutons peuvent être relâchés entre les appuis. Blanc ne déclenche plus
les commandes supplémentaires de saut ou de poussée du personnage. **L3 + START** reste disponible.
Le menu est en anglais : **Text boxes**, **Oracles** et **Game state → Keys**.
Les panneaux de sceaux et les messages de fragments/sceaux sont classés dans
Text boxes ; les aperçus de voix sans panneau confirmé portent **voice only**.
La rubrique Animations et la simulation manuelle ont été retirées. Les animations
normales du jeu et le repos d’Azurik en Freecam restent actifs. Les 20 types de
clés sont accessibles dans la limite des cinq places, sans remplacer les clés
portées. [Fonctionnement, raccourcis et limites](docs/LABORATORY.md).
