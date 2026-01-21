# ruletestrepo
Repo for testing github branch rules


## Doc

gh:

https://cli.github.com/manual/gh_ruleset


api:

https://docs.github.com/en/rest/repos/rules?apiVersion=2022-11-28#update-a-repository-ruleset


## Notes

`Only visible teams can be added as reviewers.`

## API get ruleset
```
curl -L --header 'Accept: application/vnd.github+json' --header 'X-GitHub-Api-Version: 2022-11-28' https://api.github.com/repos/jan-thomas-m/ruletestrepo/rulesets/11980045 > ruleset-test1.json
```

## gh examples

```
gh ruleset list

Showing 1 of 1 rulesets in jan-thomas-m/ruletestrepo and its parents

ID        NAME   SOURCE                            STATUS  RULES
11980045  test1  jan-thomas-m/ruletestrepo (repo)  active  6
```


```
gh ruleset view 11980045

test1
ID: 11980045
Source: jan-thomas-m/ruletestrepo (Repository)
Enforcement: Active
You can bypass: never

Bypass List
This ruleset cannot be bypassed

Conditions
- ref_name: [exclude: []] [include: [~DEFAULT_BRANCH]]

Rules
- code_quality: [severity: all]
- code_scanning: [code_scanning_tools: [map[alerts_threshold:all security_alerts_threshold:all tool:CodeQL]]]
- deletion
- non_fast_forward
- pull_request: [allowed_merge_methods: [squash rebase]] [dismiss_stale_reviews_on_push: true] [require_code_owner_review: true] [require_last_push_approval: true] [required_approving_review_count: 1] [required_review_thread_resolution: true] [required_reviewers: []]
- required_linear_history
- required_signatures

```

## Security

See [.github/SECURITY.md](.github/SECURITY.md) (from https://github.com/standard/.github/blob/master/SECURITY.md)
