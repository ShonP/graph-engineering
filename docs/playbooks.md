# Playbooks

Generated from `graphs/*.md` by `graph-control render --write`; `render --check` fails when this file drifts, so edit the graphs, not this file. A hexagon is a gate node (`gate: yes`); an edge label is the `when:` condition of the node it enters.

## [bug](../graphs/bug.md)

```mermaid
flowchart LR
  report["report (planner)"]
  reproduce["reproduce (qa)"]
  diagnose["diagnose (implementer)"]
  sibling-search["sibling-search (researcher)"]
  plan{{"plan (planner)"}}
  implement["implement (implementer)"]
  review["review (reviewer)"]
  qa["qa (qa)"]
  fix["fix (implementer)"]
  merge{{"merge (engine)"}}
  post-deploy["post-deploy (qa)"]
  retro["retro (retro)"]
  report --> reproduce
  reproduce --> diagnose
  diagnose --> sibling-search
  sibling-search --> plan
  plan --> implement
  implement --> review
  implement --> qa
  review --> fix
  qa --> fix
  fix --> merge
  merge --> post-deploy
  post-deploy --> retro
```

## [feature](../graphs/feature.md)

```mermaid
flowchart LR
  goal["goal (planner)"]
  research-ux["research-ux (researcher)"]
  research-tech["research-tech (researcher)"]
  research-competitor["research-competitor (researcher)"]
  research-impact["research-impact (researcher)"]
  design["design (ux-designer)"]
  plan{{"plan (planner)"}}
  implement["implement (implementer)"]
  review["review (reviewer)"]
  qa["qa (qa)"]
  fix["fix (implementer)"]
  merge{{"merge (engine)"}}
  post-deploy["post-deploy (qa)"]
  retro["retro (retro)"]
  goal -->|"ui"| research-ux
  goal --> research-tech
  goal -->|"product-discovery"| research-competitor
  goal --> research-impact
  research-ux -->|"ui"| design
  research-tech --> plan
  research-competitor -->|"ui"| design
  research-impact --> plan
  design --> plan
  plan --> implement
  implement --> review
  implement --> qa
  review --> fix
  qa --> fix
  fix --> merge
  merge --> post-deploy
  post-deploy --> retro
```

## [infra](../graphs/infra.md)

```mermaid
flowchart LR
  goal["goal (planner)"]
  research-tech["research-tech (researcher)"]
  research-impact["research-impact (researcher)"]
  plan{{"plan (planner)"}}
  implement["implement (implementer)"]
  review["review (reviewer)"]
  verify["verify (qa)"]
  fix["fix (implementer)"]
  merge{{"merge (engine)"}}
  post-deploy["post-deploy (qa)"]
  retro["retro (retro)"]
  goal --> research-tech
  goal --> research-impact
  research-tech --> plan
  research-impact --> plan
  plan --> implement
  implement --> review
  implement --> verify
  review --> fix
  verify --> fix
  fix --> merge
  merge --> post-deploy
  post-deploy --> retro
```

## [quick](../graphs/quick.md)

```mermaid
flowchart LR
  intake["intake (engine)"]
  impact["impact (researcher)"]
  design["design (ux-designer)"]
  plan{{"plan (planner)"}}
  implement["implement (implementer)"]
  review["review (reviewer)"]
  qa["qa (qa)"]
  fix["fix (implementer)"]
  merge{{"merge (engine)"}}
  post-deploy["post-deploy (qa)"]
  retro["retro (retro)"]
  intake --> impact
  intake -->|"ui"| design
  impact --> plan
  design --> plan
  plan --> implement
  implement --> review
  implement --> qa
  review --> fix
  qa --> fix
  fix --> merge
  merge --> post-deploy
  post-deploy --> retro
```

## [research](../graphs/research.md)

```mermaid
flowchart LR
  brief["brief (engine)"]
  research["research (researcher)"]
  verify["verify (researcher)"]
  report{{"report (engine)"}}
  brief --> research
  research -->|"deep"| verify
  verify --> report
```
