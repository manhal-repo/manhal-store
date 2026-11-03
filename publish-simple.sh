#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

STORE_REPO="manhal-repo/manhal-store"
RELEASE_TAG="files"
CATALOG_FILE="public/catalog/apps.json"
APP_ID="com.devbelmel.universalprinter"

APK_PATH=""; EXE_PATH=""; ICON_PATH=""; ANDROID_VER=""; WINDOWS_VER=""
ANDROID_VER_CODE=""
FROM_RELEASE=""
CATALOG_ONLY=0
GOOGLE_PLAY_URL=""
SCREENSHOTS=""
VIDEO_PATH=""
VIDEO_THUMB=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apk)              APK_PATH="$2"; shift 2 ;;
    --exe)              EXE_PATH="$2"; shift 2 ;;
    --icon)             ICON_PATH="$2"; shift 2 ;;
    --android-ver)      ANDROID_VER="$2"; shift 2 ;;
    --android-ver-code) ANDROID_VER_CODE="$2"; shift 2 ;;
    --windows-ver)      WINDOWS_VER="$2"; shift 2 ;;
    --google-play-url)  GOOGLE_PLAY_URL="$2"; shift 2 ;;
    --screenshots)      SCREENSHOTS="$2"; shift 2 ;;
    --video)            VIDEO_PATH="$2"; shift 2 ;;
    --video-thumb)      VIDEO_THUMB="$2"; shift 2 ;;
    --app-id)           APP_ID="$2"; shift 2 ;;
    --from-release)     FROM_RELEASE="$2"; shift 2 ;;
    --catalog-only)     CATALOG_ONLY=1; shift ;;
    *) echo "Unknown: $1"; exit 2 ;;
  esac
done

# ---------- استيراد APK من GitHub release (build.yml) ----------
if [ -n "$FROM_RELEASE" ]; then
  TMPDIR_DL="$(mktemp -d)"
  echo "==> Downloading from release build-$FROM_RELEASE"
  gh release download "build-$FROM_RELEASE" --repo "manhal-repo/mystore-complete" \
    -p 'build-info.json' -p '*.apk' -D "$TMPDIR_DL" 2>&1 | tail -3
  APK_FOUND="$(find "$TMPDIR_DL" -maxdepth 1 -name '*.apk' | head -1)"
  INFO_FOUND="$TMPDIR_DL/build-info.json"
  [ -n "$APK_FOUND" ] || { echo "No APK in release"; exit 1; }
  [ -f "$INFO_FOUND" ] || { echo "No build-info.json"; exit 1; }
  APK_PATH="$APK_FOUND"
  if [ -z "$ANDROID_VER_CODE" ]; then
    ANDROID_VER_CODE="$(jq -r --arg pkg "$APP_ID" '.builds[] | select(.package==$pkg) | .versionCode' "$INFO_FOUND" | head -1)"
  fi
  if [ -z "$ANDROID_VER" ]; then
    ANDROID_VER="$(jq -r --arg pkg "$APP_ID" '.builds[] | select(.package==$pkg) | .versionName' "$INFO_FOUND" | head -1)"
  fi
  echo "  imported: $(basename "$APK_FOUND")  version=$ANDROID_VER  versionCode=$ANDROID_VER_CODE"
fi

# ---------- التحقق من APK ----------
[ -n "$APK_PATH" ] || { echo "No --apk and no --from-release"; exit 1; }
[ -f "$APK_PATH" ] || { echo "APK not found: $APK_PATH"; exit 1; }
APK_PATH="$(realpath "$APK_PATH")"

# ---------- استخراج versionCode إن لم يُحدَّد ----------
extract_version_code() {
  local apk="$1" vc=""
  if command -v aapt2 >/dev/null 2>&1; then
    vc=$(aapt2 dump badging "$apk" 2>/dev/null | sed -n "s/.*versionCode='\\([0-9]*\\)'.*/\\1/p" | head -n1)
  fi
  if [ -z "$vc" ] && command -v aapt >/dev/null 2>&1; then
    vc=$(aapt dump badging "$apk" 2>/dev/null | sed -n "s/.*versionCode='\\([0-9]*\\)'.*/\\1/p" | head -n1)
  fi
  echo "$vc"
}
if [ -z "${ANDROID_VER_CODE:-}" ]; then
  ANDROID_VER_CODE=$(extract_version_code "$APK_PATH")
fi
if [ -z "$ANDROID_VER_CODE" ]; then
  echo "WARNING: versionCode unknown. Install aapt2 or pass --android-ver-code N (or use --from-release)."
fi

# ---------- التحقق من EXE ----------
EXE_TARGET=""; EXE_SHA=""; EXE_SIZE=0; URL_W=""
if [ -n "$EXE_PATH" ]; then
  [ -f "$EXE_PATH" ] || { echo "EXE not found: $EXE_PATH"; exit 1; }
  EXE_PATH="$(realpath "$EXE_PATH")"
  EXE_SHA=$(sha256sum "$EXE_PATH" | awk '{print $1}')
  EXE_SIZE=$(stat -c %s "$EXE_PATH")
  EXE_TARGET="uprinter-${WINDOWS_VER}-win-x64.exe"
  URL_W="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$EXE_TARGET"
fi

APK_TARGET=""
APK_SHA=$(sha256sum "$APK_PATH" | awk '{print $1}')
APK_SIZE=$(stat -c %s "$APK_PATH")
if [ "$CATALOG_ONLY" -eq 0 ]; then
  APK_TARGET="app-release-${ANDROID_VER}.apk"
fi
URL_A=""
if [ "$CATALOG_ONLY" -eq 0 ]; then
  URL_A="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$APK_TARGET"
elif [ -n "$FROM_RELEASE" ]; then
  # في وضع catalog-only، استعمل رابط الـrelease الأصلي من mystore-complete
  URL_A="https://github.com/manhal-repo/mystore-complete/releases/download/build-$FROM_RELEASE/$(basename "$APK_PATH")"
fi

echo "==> Metadata"
echo "  APK: size=$APK_SIZE sha=$APK_SHA ver=$ANDROID_VER verCode=$ANDROID_VER_CODE url=$URL_A"
[ -n "$EXE_PATH" ] && echo "  EXE: size=$EXE_SIZE sha=$EXE_SHA url=$URL_W"

echo "==> Checking prerequisites"
gh auth status >/dev/null 2>&1 || { echo "Run: gh auth login"; exit 1; }
gh repo view "$STORE_REPO" >/dev/null 2>&1 || { echo "Cannot access $STORE_REPO"; exit 1; }

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ---------- ضمان وجود release tag ----------
if [ "$CATALOG_ONLY" -eq 0 ] || [ -n "$EXE_PATH" ]; then
  gh release view "$RELEASE_TAG" --repo "$STORE_REPO" >/dev/null 2>&1 \
    || gh release create "$RELEASE_TAG" --repo "$STORE_REPO" --title "Store Files" --notes "Downloads"
fi

# ---------- رفع APK ----------
if [ "$CATALOG_ONLY" -eq 0 ]; then
  echo "==> Uploading APK as $APK_TARGET"
  gh release upload "$RELEASE_TAG" "$APK_PATH#$APK_TARGET" --repo "$STORE_REPO" --clobber
  TMPA=$(mktemp); printf '%s  %s' "$APK_SHA" "$APK_TARGET" > "$TMPA"
  gh release upload "$RELEASE_TAG" "$TMPA#${APK_TARGET}.sha256" --repo "$STORE_REPO" --clobber
  rm -f "$TMPA"
fi

# ---------- رفع EXE ----------
if [ -n "$EXE_PATH" ]; then
  echo "==> Uploading EXE as $EXE_TARGET"
  gh release upload "$RELEASE_TAG" "$EXE_PATH#$EXE_TARGET" --repo "$STORE_REPO" --clobber
  TMPE=$(mktemp); printf '%s  %s' "$EXE_SHA" "$EXE_TARGET" > "$TMPE"
  gh release upload "$RELEASE_TAG" "$TMPE#${EXE_TARGET}.sha256" --repo "$STORE_REPO" --clobber
  rm -f "$TMPE"
fi

# ---------- أيقونة/صور/فيديو (كما كان) ----------
ICON_TARGET=""; URL_I=""
if [ -n "$ICON_PATH" ] && [ -f "$ICON_PATH" ]; then
  EXT="${ICON_PATH##*.}"
  ICON_TARGET="icon-${APP_ID}.${EXT}"
  gh release upload "$RELEASE_TAG" "$ICON_PATH#$ICON_TARGET" --repo "$STORE_REPO" --clobber
  URL_I="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$ICON_TARGET"
fi

SHOT_URLS=""; SHOT_COUNT=0
if [ -n "$SCREENSHOTS" ]; then
  IFS=',' read -ra SHOT_ARR <<< "$SCREENSHOTS"
  for shot in "${SHOT_ARR[@]}"; do
    shot=$(echo "$shot" | xargs)
    [ -f "$shot" ] || { echo "  skip: $shot"; continue; }
    SHOT_COUNT=$((SHOT_COUNT+1))
    EXT="${shot##*.}"
    TARGET="shot-${APP_ID}-${SHOT_COUNT}.${EXT}"
    gh release upload "$RELEASE_TAG" "$shot#$TARGET" --repo "$STORE_REPO" --clobber
    U="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$TARGET"
    [ -z "$SHOT_URLS" ] && SHOT_URLS="$U" || SHOT_URLS="$SHOT_URLS|$U"
  done
fi

VIDEO_URL=""; VIDEO_THUMB_URL=""
if [ -n "$VIDEO_PATH" ] && [ -f "$VIDEO_PATH" ]; then
  EXT="${VIDEO_PATH##*.}"
  TARGET="video-${APP_ID}.${EXT}"
  gh release upload "$RELEASE_TAG" "$VIDEO_PATH#$TARGET" --repo "$STORE_REPO" --clobber
  VIDEO_URL="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$TARGET"
  if [ -n "$VIDEO_THUMB" ] && [ -f "$VIDEO_THUMB" ]; then
    T2="video-thumb-${APP_ID}.${VIDEO_THUMB##*.}"
    gh release upload "$RELEASE_TAG" "$VIDEO_THUMB#$T2" --repo "$STORE_REPO" --clobber
    VIDEO_THUMB_URL="https://github.com/$STORE_REPO/releases/download/$RELEASE_TAG/$T2"
  fi
fi

# ---------- تحديث apps.json ----------
echo "==> Cloning store repo"
TMP=$(mktemp -d)
git clone --depth 1 "https://github.com/$STORE_REPO.git" "$TMP" >/dev/null 2>&1 || { echo "clone failed"; rm -rf "$TMP"; exit 1; }
CAT="$TMP/$CATALOG_FILE"

SHOT_JSON="[]"
if [ -n "$SHOT_URLS" ]; then
  SHOT_JSON=$(printf '%s' "$SHOT_URLS" | awk -F'|' 'BEGIN{printf "["} {printf "%s\"%s\"", (NR>1?",":""), $0} END{printf "]"}')
fi

# نمرر versionCode كسلسلة، ونحوّلها داخل jq فقط إن كانت رقماً
jq --arg id "$APP_ID" \
   --arg av "$ANDROID_VER" --arg avc "$ANDROID_VER_CODE" \
   --arg as "$APK_SIZE" --arg ah "$APK_SHA" --arg au "$URL_A" \
   --arg wv "$WINDOWS_VER" --arg ws "$EXE_SIZE" --arg wh "$EXE_SHA" --arg wu "$URL_W" \
   --arg icon "$URL_I" --arg now "$NOW" --arg gp "$GOOGLE_PLAY_URL" \
   --arg video "$VIDEO_URL" --arg vthumb "$VIDEO_THUMB_URL" \
   --argjson shots "$SHOT_JSON" '
  def vcode: (try ($avc|tonumber) catch null);
  (.apps[] | select(.id == $id)) |=
  (
    .downloads = (
      ((.downloads // []) | map(select(.os != "android" and .os != "windows")))
      +
      ([{ os: "android", version: $av, size: ($as|tonumber), sha256: $ah, url: $au, uploadedAt: $now }]
       | map(if vcode != null then . + {versionCode: vcode} else . end))
      +
      (if $wu != "" then [{ os: "windows", version: $wv, size: ($ws|tonumber), sha256: $wh, url: $wu, uploadedAt: $now }] else [] end)
    )
    | .updatedAt = $now
    | (if $icon != "" then .icon = $icon | .appIconUrl = $icon else . end)
    | (if $gp   != "" then .googlePlayUrl = $gp else . end)
    | (if $video != "" then .video = $video else . end)
    | (if $vthumb != "" then .videoThumbnail = $vthumb else . end)
    | (if ($shots | length) > 0 then .screenshots = $shots else . end)
  )
' "$CAT" > "$CAT.new" && mv "$CAT.new" "$CAT"

(
  cd "$TMP"
  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"
  git add "$CATALOG_FILE"
  git diff --cached --quiet && echo "  no changes" || {
    git commit -m "Update $APP_ID: Android $ANDROID_VER ($ANDROID_VER_CODE), Windows $WINDOWS_VER" >/dev/null
    git push
    echo "  pushed"
  }
)
rm -rf "$TMP"
echo
echo "DONE."
