#!/usr/bin/env bash

echo "term: ${TERM}"

echo "locale settings:"
echo "================"
# echo "localectl:"
# localectl status

echo "lang: ${LANG}"
echo "Character Encoding (locale charmap): $( locale charmap || true)"

echo "Locale: $( locale || true )"

# for var in LC_ALL LC_COLLATE LC_CTYPE LC_MESSAGES LC_MONETARY LC_NUMERIC LC_TIME LC_PAPER LC_NAME LC_ADDRESS LC_TELEPHONE LC_MEASUREMENT LC_IDENTIFICATION; do
#     printf "%s: %s\n" "$var" "${!var:-<unset>}"
# done

echo -e "\nTesting UTF-8 character output:"
echo "================"

echo "Norwegian letters (latin-1):"
printf "Norwegian (lowercase): æ (\\\xE6) (\\\u00E6) ø (\\\xF8) (\\\u00F8) å (\\\xE5) (\\\u00E5)\n"
printf "Norwegian (uppercase): Æ (\\\xC6) (\\\u00C6) Ø (\\\xD8) (\\\u00D8) Å (\\\xC5) (\\\u00C5)\n"

# https://theasciicode.com.ar/extended-ascii-code/capital-letter-a-ring-uppercase-ascii-code-143.html
# https://www.ascii-code.com/character/%C3%A5
# https://www.fileformat.info/info/unicode/font/wingdings/nonunicode.htm
# \UF04A = :-) simley

# å = desimal 134, hex E5, unicode U+00E5, a with ring above
# ø = desimal 248, hex F8, unicode U+00F8, o with stroke
# æ = desimal 230, hex E6, unicode U+00E6, ae ligature
# Å = desimal 197, hex C5, unicode U+00C5, A with ring above
# Ø = desimal 216, hex D8, unicode U+00D8, O with stroke
# Æ = desimal 198, hex C6, unicode U+00C6, AE ligature
# " = desimal 34, hex 22, unicode U+0022, quotation mark
# ‘ = desimal 8216, hex 2018, unicode U+2018, left single quotation mark
# ’ = desimal 8217, hex 2019, unicode U+2019, right single quotation mark
# “ = desimal 8220, hex 201C, unicode U+201C, left double quotation mark
# ” = desimal 8221, hex 201D, unicode U+201D, right double quotation mark
# – = desimal 8211, hex 2013, unicode U+2013, en dash
# — = desimal 8212, hex 2014, unicode U+2014, em dash
# … = desimal 8230, hex 2026, unicode U+2026", horizontal ellipsis

printf "Accents and diacritics (literal): é è ü ñ ç\n"
printf "Currency & symbols (literal): © € µ\n"

printf "Smart single quotes (literal): ‘ ’✅\n"
printf "Smart single quotes (utf8): \xE2\x80\x98 \xE2\x80\x99\n"
# shellcheck disable=SC1111
printf "Smart double quotes (literal): “ ”\n"
printf "Smart double quotes (utf8): \xE2\x80\x9C \xE2\x80\x9D\n"

printf "en dash: – (\\\xE2\\\x80\\\x93) (\\\u2013)\n"
printf "em dash: — (\\\xE2\\\x80\\\x94) (\\\u2014)\n"
printf "Ellipsis: … (\\\xE2\\\x80\\\xA6) (\\\u2026)\n"


printf "Programming ligatures (examples): a -> b, a => b, a <- b, a <= b, a >= b\n"
printf "Ligature operators: == === != !== ->> <<< >>> && || ++ -- ** := ::\n"


# Print emojis on one line with UTF-8 hex and Unicode codepoint escapes in parentheses
printf "Emoji: 😀 (\\xF0\\x9F\\x98\\x80 U+1F600) 🚀 (\\xF0\\x9F\\x9A\\x80 U+1F680)\n"
printf "Emoji: \uD83D\uDE00 (\\uD83D\\uDE00 U+1F600) \uD83D\uDE80 (\\uD83D\\uDE80 U+1F680)\n"

printf "More emojis: ✅❌❎❓\n"
printf "More emojis (utf8): \\xE2\\x9C\\x94 \\xE2\\x9D\\x8C \\xE2\\x9D\\x8E \\xE2\\x9D\\x93\n"
printf "More emojis (unicode): \\\u2705 \\\u274C \\\u274E \\\u2753\n"

printf "other checkmarks: ✔ ✖ ✘ ✚ ✪ ★ ☆\n"
printf "other checkmarks (utf8): \\xE2\\x9C\\x94 \\xE2\\x9C\\x96 \\xE2\\x9C\x98 \\xE2\\x9A\\x9A \\xE2\\x98\\xAA \\xE2\\x98\\x85 \\xE2\\x98\\x86\n"
printf "other checkmarks (unicode): \\\u2705 \\u2716 \\\u2718 \\\u272A \\\u272A \\\u2605 \\\u2606\n"

printf "\u2705 2705 white heavy check mark\n"
printf "\u274C 274C cross mark\n"
printf "\u274E 274E negative squared cross mark\n"
printf "\u2753 2753 black question mark ornament\n"
printf "\u2713 2713 check mark\n"
printf "\u2714 2714 heavy check mark\n"
printf "\u2716 2716 heavy multiplication x\n"
printf "\u2718 2718 heavy ballot x\n"

printf "\u2717 2717 ballot x\n"
printf "\u21BA 21BA clockwise open circle arrow\n"
printf "\u26A0 26A0 warning sign\n"

printf "python snake icon: 🐍 (\\xF0\\x9F\\x90\\x8D U+1F40D)\n"


printf "programming languages:\n"
printf "Rust: 🦀 (\\xF0\\x9F\\xA6\\x80 U+1F9A0)\n"
printf "Go: 🐹 (\\xF0\\x9F\\x90\n"
printf "Java: ☕ (\\xE2\\x98\\x95 U+2615)\n"
printf "JavaScript: ✨ (\\xE2\\x9C\\xA8 U+2728)\n"
printf "C#: 🎵 (\\xF0\\x9F\\x8E\\xB5 U+1F3B5)\n"
printf "PHP: 🐘 (\\xF0\\x9F\\x90\\x98 U+1F418)\n"
printf "Ruby: 💎 (\\xF0\\x9F\\x92\\x8E U+1F48E)\n"
printf "Swift: 🦅 (\\xF0\\x9F\\xA6\\x85 U+1F985)\n"
printf "Kotlin: 🅺 (\\xF0\\x9F\\x85\\xBA U+1F18A)\n"
printf "HTML5: 🅗 (\\xF0\\x9F\\x85\\x97 U+1F197)\n"
printf "CSS3: 🅒 (\\xF0\\x9F\\x85\\x92 U+1F192)\n"
printf "Docker: 🐳 (\\xF0\\x9F\\x90\\xB3 U+1F433)\n"
printf "Kubernetes: ☸️ (\\xE2\\x98\\xB8 U+2638)\n"
printf "Linux: 🐧 (\\xF0\\x9F\\x90\\xA7 U+1F427)\n"
printf "Apple: 🍎 (\\xF0\\x9F\\x8D\\x8E U+1F34E)\n"
printf "Windows: 🪟 (\\xF0\\x9F\\xAA\x9F U+1FA9F)\n"
printf "Android: 🤖 (\\xF0\\x9F\\xA4\\x96 U+1F916)\n"
printf "Linux penguin: 🐧 (\\xF0\\x9F\\x90\\xA7 U+1F427)\n"
printf "Apple logo: 🍏 (\\xF0\\x9F\\x8D\\x8F U+1F34F)\n"
printf "Windows logo: 🪟 (\\xF0\\x9F\\xAA\x9F U+1FA9F)\n"
printf "Android robot: 🤖 (\\xF0\\x9F\\xA4\\x96 U+1F916)\n"

# printf "Python (Nerd Font): \uE235\n"

