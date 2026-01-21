#!/bin/zsh

setopt errexit
setopt pipefail

fisk=$1

[[ -z "${fisk}" ]] && exit 1

git switch -c "${fisk}"
touch "${fisk}"
git add "${fisk}"
git commit -m "adding ${fisk}" "${fisk}"
git push --verbose --tags --prune --set-upstream origin "$( git rev-parse --abbrev-ref HEAD || true )"
gh pr create --fill
git switch -
