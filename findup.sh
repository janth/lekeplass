#!/usr/bin/env zsh

# sane settings
set -e
set -u
set -o pipefail

# zsh globs
# https://zsh.sourceforge.io/Doc/Release/Expansion.html

# dir=${PWD:A}
# topdir=${HOME:A}

dir=${PWD}
topdir=${HOME}

# options (use getopts; support long options by normalization)
all=0
reverse=0
absolute=0

# parse options with getopt (supports long options)
PARSED=$(getopt -o arhAt: -l all,reverse,help,absolute,topdir: -- "$@") || { printf 'Failed parsing options\n' >&2; exit 2; }
eval set -- "$PARSED"
while true; do
  case "$1" in
    -a|--all) all=1; shift ;;
    -r|--reverse) reverse=1; shift ;;
    -A|--absolute) absolute=1; shift ;;
    -t|--topdir) topdir="$2"; topdir=${topdir:A}; shift 2 ;;
    -h|--help) printf 'Usage: %s [-a|--all] [-r|--reverse] [-A|--absolute] [-t|--topdir TOPDIR] file1 <file2> ...\n' "$0"; exit 0 ;;
    --) shift; break ;;
    *) shift; break ;;
  esac
done

if [[ "$#" -eq 0 ]] ; then
  printf 'Error: No target file specified.\n' >&2
  exit 2
fi

# if [[ $absolute -eq 0 ]] ; then
#   echo "Finding files, reporting paths relative to topdir: $topdir"
#   # build relative path of '..' segments from PWD up to topdir
#   cur=${PWD:A}
#   parts=()
#   while [[ "$cur" != "$topdir" && "$cur" != "${cur:h}" ]] ; do
#     parts+=('..')
#     cur=${cur:h}
#   done

#   if [[ "$cur" != "$topdir" ]] ; then
#     # topdir not an ancestor — fall back to absolute topdir
#     topdir_relative="$topdir"
#   else
#     if (( ${#parts[@]} == 0 )); then
#       topdir_relative="."
#     else
#       topdir_relative="${(j:/:)parts}"
#     fi
#   fi
# fi

# topdir_relative="$topdir"  # for now, just use absolute
# echo "topdir: $topdir (relative: $topdir_relative)"

# collect directories from PWD up to topdir (inclusive)
dir=${PWD}
dirs=()
while true; do
  dirs+=("$dir")
  [[ "$dir" == "$topdir" ]] && break
  parent=${dir:h}
  [[ "$parent" == "$dir" ]] && break
  dir=$parent
done

# echo "dirs collected:"
# printf "dirs: %s\n" "${dirs[@]}"
# echo

if [[ $reverse -eq 0 ]] ; then
  searchdirs=("${dirs[@]}")  # copy
else
  searchdirs=("${(Oa)dirs[@]}")  # sort ascending
fi

# echo "dirs collected:"
# printf "dirs: %s\n" "${searchdirs[@]}"
# echo


targets=("$@")
overall_found=0

for target in "${targets[@]}"; do
  # echo "Searching for target: $target"
  found=0
  matches=()
  for d in "${searchdirs[@]}"; do
    # echo "  Checking directory: $d for $target "
    if [[ -e "$d/$target" ]] ; then
      fullpath="$d/$target"
      matches+=("$fullpath")
      found=1
      overall_found=1
      if [[ $all -eq 0 ]] ; then
        break
      fi
    fi
  done

  # print using collected matches (absolute paths converted to ~ when under $topdir)
  for fp in "${matches[@]}"; do
    if [[ "$fp" == "$topdir"* ]] ; then
      rel="${fp#$topdir}"
      if [[ "$rel" = /* ]] ; then
        rel="~$rel"
      else
        rel="~/$rel"
      fi
      printf '%s\n' "$rel"
    else
      printf '%s\n' "$fp"
    fi
  done
  [[ "$target" != "${targets[-1]}" ]] && echo

  # if [[ $found -eq 0 ]] ; then
  #   printf 'Not found: %s\n' "$target" >&2
  # fi
done

if [[ $overall_found -eq 1 ]] ; then
  exit 0
else
  exit 1
fi