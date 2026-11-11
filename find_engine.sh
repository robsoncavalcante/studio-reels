#!/usr/bin/env bash
# Imprime o caminho do motor Studio Reels (ou instala a partir de um zip anexado). Saída vazia = não encontrado.
for d in "$STUDIO_REELS_HOME" "$PWD/studio-reels" "$HOME/studio-reels" /home/claude/studio-reels /mnt/user-data/outputs/studio-reels /mnt/user-data/uploads/studio-reels; do
  [ -n "$d" ] && [ -f "$d/studio.py" ] && { echo "$d"; exit 0; }
done
Z=$(ls -t /mnt/user-data/uploads/*studio-reels*.zip "$PWD"/*studio-reels*.zip "$HOME"/*studio-reels*.zip 2>/dev/null | head -1)
if [ -n "$Z" ]; then mkdir -p "$HOME/studio-reels-src" && unzip -qo "$Z" -d "$HOME/studio-reels-src" && f=$(find "$HOME/studio-reels-src" -maxdepth 3 -name studio.py | head -1) && [ -n "$f" ] && dirname "$f" && exit 0; fi
exit 1
