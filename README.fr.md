# Azurik — Menu debug

Version de test **0.1.1** pour le jeu Xbox **PAL / Europe**. Le menu debug déjà intégré au jeu reçoit
une entrée **Freecam** qui active la caméra du code triche d'origine.
Le monde continue de fonctionner pendant qu'Azurik reste immobile. Sa propre
animation et sa physique sont suspendues durant la caméra libre.

Le correctif utilise le programme commun du jeu et la caméra du royaume chargé.
Il s'applique à **tous les royaumes jouables** de cette version européenne,
sans restriction à W1. Leur fonctionnement reste à vérifier dans le jeu.
Activez la caméra pendant une partie chargée, hors écran titre et chargement.

**Freecam apparaît comme quatrième entrée du menu debug d'Azurik**, au même
endroit que les trois entrées européennes d'origine **Change level...**,
**Play Movie...** et **Game state...**. Les trois entrées existantes sont
conservées. Aucun sous-menu supplémentaire n'est nécessaire. Le logiciel
Windows installe ce changement dans l'ISO ; le menu s'utilise ensuite en jeu.

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
