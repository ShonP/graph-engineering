export const meta = {
  name: 'sdd-ready-queue',
  description: 'Run a plan you already have on a ready queue: one worktree per task, at most 4 writers, each task merged as soon as it passes review',
  whenToUse: 'A hand-written subagent-driven plan with depends_on edges, run by hand. Prefer /graph-ship, which has gates. Run with dry_run: true first.',
  phases: [
    { title: 'Validate', detail: 'ids, dependencies, cycles and the writer cap' },
    { title: 'Run', detail: 'implement, review, fix and merge each task as its dependencies merge' },
  ],
}

const MAX_WRITERS = 4
const FIX_ROUNDS = 3
const FULL = 'graph-engineering:implementer'
const SIMPLE = 'graph-engineering:implementer-simple'
const REVIEWER = 'graph-engineering:reviewer'
const ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/
const BRANCH = /^[A-Za-z0-9][A-Za-z0-9._\/-]*$/
const PATH = /^\/[A-Za-z0-9._\/-]+$/
const STATUSES = ['DONE', 'DONE_WITH_CONCERNS', 'PARTIAL', 'BLOCKED', 'NEEDS_CONTEXT', 'NEEDS_SETUP', 'ESCALATE']
const GREEN = ['DONE', 'DONE_WITH_CONCERNS']
const IDS = { type: 'array', items: { type: 'string' } }
const IMPL = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: STATUSES }, summary: { type: 'string' }, green_commit: { type: 'string' },
    done_cases: IDS, remaining_cases: IDS, remaining_scope: { type: 'string' }, elapsed_min: { type: 'number' },
  },
  required: ['status', 'summary'],
}
const REVIEW = {
  type: 'object',
  properties: { findings: { type: 'array', items: { type: 'object', properties: {
    severity: { type: 'string', enum: ['blocking', 'important', 'nit'] }, title: { type: 'string' }, detail: { type: 'string' },
  }, required: ['severity', 'title'] } } },
  required: ['findings'],
}
const MERGE = {
  type: 'object',
  properties: { merged: { type: 'boolean' }, merge_sha: { type: 'string' }, detail: { type: 'string' } },
  required: ['merged', 'detail'],
}

function validate(input) {
  if (!input || typeof input !== 'object' || !Array.isArray(input.tasks) || !input.tasks.length) return 'args.tasks must be a non-empty array'
  if (input.max_writers !== undefined && !Number.isFinite(input.max_writers)) return 'max_writers must be a number'
  if (!input.dry_run) {
    if (!ID.test(input.run_id || '')) return 'run_id must match ' + ID
    if (!BRANCH.test(input.run_branch || '')) return 'run_branch must match ' + BRANCH
    for (const key of ['repo_root', 'worktree_root']) if (!PATH.test(input[key] || '')) return key + ' must be an absolute path matching ' + PATH
  }
  const seen = new Set()
  for (const task of input.tasks) {
    if (!task || !ID.test(task.id || '')) return 'task id must match ' + ID + ': ' + JSON.stringify(task && task.id)
    if (seen.has(task.id)) return 'duplicate task id ' + task.id
    seen.add(task.id)
    if (task.depends_on !== undefined && !Array.isArray(task.depends_on)) return task.id + ': depends_on must be an array'
    if (input.dry_run && !(typeof task.estimate_min === 'number' && task.estimate_min >= 0)) return task.id + ': dry_run needs estimate_min >= 0'
    if (!input.dry_run && (typeof task.brief !== 'string' || !task.brief)) return task.id + ': brief is required'
  }
  for (const task of input.tasks) for (const dep of task.depends_on || []) if (!seen.has(dep)) return task.id + ': unknown dependency ' + dep
  const cycle = cycleMembers(normalize(input.tasks))
  return cycle.length ? 'dependency cycle through ' + cycle.join(', ') : null
}

function normalize(tasks) {
  return tasks.map(task => Object.assign({}, task, { depends_on: Array.from(new Set(task.depends_on || [])) }))
}

function cycleMembers(tasks) {
  const indegree = {}
  for (const task of tasks) indegree[task.id] = task.depends_on.length
  const queue = tasks.filter(task => !task.depends_on.length).map(task => task.id)
  while (queue.length) {
    const id = queue.shift()
    for (const task of tasks) if (task.depends_on.includes(id) && --indegree[task.id] === 0) queue.push(task.id)
  }
  return tasks.filter(task => indegree[task.id] > 0).map(task => task.id)
}

function tailLength(tasks) {
  const tail = {}
  const visit = id => {
    if (tail[id] === undefined) tail[id] = 1 + Math.max(0, ...tasks.filter(t => t.depends_on.includes(id)).map(t => visit(t.id)))
    return tail[id]
  }
  for (const task of tasks) visit(task.id)
  return tail
}

function readySet(tasks, done, running, parked, width) {
  const tail = tailLength(tasks)
  return tasks
    .filter(t => !done.has(t.id) && !running.has(t.id) && !parked.has(t.id) && t.depends_on.every(d => done.has(d)))
    .sort((a, b) => tail[b.id] - tail[a.id])
    .slice(0, Math.max(0, width - running.size))
    .map(t => t.id)
}

function simulate(tasks, width) {
  const done = new Set(), running = new Map(), trace = []
  let clock = 0
  for (;;) {
    for (const id of readySet(tasks, done, running, new Set(), width)) {
      const end = clock + tasks.find(t => t.id === id).estimate_min
      running.set(id, end)
      trace.push({ id, start: clock, end })
    }
    if (!running.size) break
    clock = Math.min(...running.values())
    for (const [id, end] of running) if (end === clock) { running.delete(id); done.add(id) }
  }
  return { dry_run: true, max_writers: width, makespan: clock, order: trace.map(t => t.id), trace }
}

function where(input, task) {
  const branch = input.run_id + '-' + task.id
  return { branch, worktree: input.worktree_root + '/' + branch }
}

function implementPrompt(input, task) {
  const { branch, worktree } = where(input, task)
  const remainder = task.remainder_of
    ? `\nThis is the remainder of ${task.remainder_of}, whose green work is merged. Remaining scope: ${task.remaining_scope}. Remaining cases: ${task.remaining_cases.join(', ')}.`
    : ''
  return `Implement task ${task.id} of run ${input.run_id}. GRAPH_RUN_ID=${input.run_id}-${task.id.toLowerCase()}. Brief: ${task.brief}${remainder}
Create your worktree from the run branch head, unless ${worktree} already exists from an earlier dispatch. From ${input.repo_root}:
  sha=$(git rev-parse ${input.run_branch})
  git worktree add -b ${branch} ${worktree} $sha
Your first command inside it is git merge-base --is-ancestor $sha HEAD; non-zero is BLOCKED. Commit only in ${worktree}.
Return status (${STATUSES.join(', ')}) and summary; for PARTIAL also green_commit, done_cases, remaining_cases, remaining_scope, elapsed_min.`
}

function scopeNote(task, latest) {
  const list = ids => (ids && ids.length ? ids.join(', ') : '(none listed)')
  const remainder = task.remainder_of
    ? `\nThis is the remainder of ${task.remainder_of}, whose work is already merged; the scope here is only: ${task.remaining_scope} (cases ${list(task.remaining_cases)}).`
    : ''
  if (latest.status !== 'PARTIAL') return remainder
  return `${remainder}\nThe work is PARTIAL by design. Built (done_cases): ${list(latest.done_cases)}. Not built, and queued as a separate remainder task: remaining_scope ${latest.remaining_scope || '(none given)'}, remaining_cases ${list(latest.remaining_cases)}.`
}

function reviewPrompt(input, task, latest) {
  const { branch, worktree } = where(input, task)
  return `Review task ${task.id} of run ${input.run_id}: the diff of branch ${branch} (worktree ${worktree}) against git merge-base ${branch} ${input.run_branch}, held to the brief ${task.brief}.${scopeNote(task, latest)}
Judge only what is in scope and built; the absence of the not-built remaining scope is not a finding. Return findings with severity blocking, important or nit per review-protocol; an empty list when clean.`
}

function fixPrompt(input, task, findings, round, latest) {
  const { worktree } = where(input, task)
  const last = round === FIX_ROUNDS
    ? '\nThis is the last round and a fresh diagnosis: superpowers:systematic-debugging is REQUIRED. Load it and state a new hypothesis for why earlier rounds did not clear these findings before any edit.'
    : ''
  return `Fix round ${round} of ${FIX_ROUNDS} for task ${task.id} of run ${input.run_id}. GRAPH_RUN_ID=${input.run_id}-${task.id.toLowerCase()}-r${round}. Work in the existing worktree ${worktree}; do not create another. Brief: ${task.brief}.${scopeNote(task, latest)}${last}
Fix every finding below test-first and commit. Return DONE or DONE_WITH_CONCERNS only when the whole scope is built; if part of it is still not built, return PARTIAL with green_commit, done_cases, remaining_cases and remaining_scope as they stand now.\n${JSON.stringify(findings, null, 2)}`
}

function mergePrompt(input, task) {
  const { branch, worktree } = where(input, task)
  return `Merge task ${task.id} into ${input.run_branch}. Find the worktree that has ${input.run_branch} checked out (git -C ${input.repo_root} worktree list --porcelain); if none does, return merged false. There, if ${branch} has no commits outside ${input.run_branch}, skip the merge and say no change; otherwise run git merge --no-ff ${branch} -m "Merge task ${task.id}". On a conflict run git merge --abort and return merged false naming the paths. After a merge or no change, remove only this task: git worktree remove ${worktree} then git branch -d ${branch}, without force flags; a refusal goes in detail. Return merged, merge_sha (the run branch head) and detail.`
}

async function runTask(input, task, merge) {
  const label = task.id
  let type = task.size === 'small' ? SIMPLE : FULL
  let result = await agent(implementPrompt(input, task), { label: 'implement ' + label, phase: 'Run', agentType: type, schema: IMPL })
  if (result && result.status === 'ESCALATE' && type === SIMPLE) {
    log(`${label}: ESCALATE, re-dispatching once to ${FULL}`)
    type = FULL
    result = await agent(implementPrompt(input, task), { label: 'implement ' + label, phase: 'Run', agentType: FULL, schema: IMPL })
  }
  let latest = result
  let stop = unusable(task, latest, 'implementer')
  if (stop) return { parked: stop }
  for (let round = 1; ; round++) {
    const review = await agent(reviewPrompt(input, task, latest), { label: 'review ' + label, phase: 'Run', agentType: REVIEWER, schema: REVIEW })
    if (!review) return { parked: 'reviewer returned no result' }
    const open = review.findings.filter(f => f.severity !== 'nit')
    if (!open.length) break
    if (round > FIX_ROUNDS) return { parked: `${open.length} blocking or important findings after ${FIX_ROUNDS} fix rounds` }
    const fixType = round === FIX_ROUNDS ? FULL : type
    log(`${label}: fix round ${round} on ${fixType}, ${open.length} findings`)
    latest = await agent(fixPrompt(input, task, open, round, latest), { label: `fix ${label} r${round}`, phase: 'Run', agentType: fixType, schema: IMPL })
    stop = unusable(task, latest, 'fix round ' + round)
    if (stop) return { parked: stop }
  }
  const merged = await merge(task)
  if (!merged || !merged.merged) return { parked: 'merge: ' + (merged ? merged.detail : 'no result') }
  return { merge_sha: merged.merge_sha, result: latest }
}

function unusable(task, result, step) {
  if (!result) return step + ' returned no result'
  if (result.status === 'PARTIAL') return task.remainder_of ? `${step}: PARTIAL again on a remainder: ${result.summary}` : null
  return GREEN.includes(result.status) ? null : `${step}: ${result.status}: ${result.summary}`
}

async function schedule(input, width) {
  const tasks = normalize(input.tasks)
  const done = new Set(), parked = new Map(), running = new Map(), dispatched = new Set()
  const merged = [], remainders = [], trace = []
  let mergeChain = Promise.resolve()
  const merge = task => {
    const next = mergeChain.then(() => agent(mergePrompt(input, task), { label: 'merge ' + task.id, phase: 'Run', agentType: SIMPLE, schema: MERGE, effort: 'low' }))
    mergeChain = next.catch(() => null)
    return next
  }
  const park = (id, reason) => {
    parked.set(id, { id, reason, worktree: dispatched.has(id) ? where(input, { id }).worktree : null })
    trace.push({ id, event: 'parked' })
    log(`parked ${id}: ${reason}`)
    for (const t of tasks) if (t.depends_on.includes(id) && !parked.has(t.id)) park(t.id, 'depends on parked ' + id)
  }
  for (;;) {
    for (const id of readySet(tasks, done, running, parked, width)) {
      const task = tasks.find(t => t.id === id)
      dispatched.add(id)
      trace.push({ id, event: 'dispatch' })
      log(`dispatch ${id} (${running.size + 1}/${width} writers)`)
      running.set(id, runTask(input, task, merge).catch(e => ({ parked: 'error: ' + e })).then(outcome => ({ id, outcome })))
    }
    if (!running.size) break
    const { id, outcome } = await Promise.race(running.values())
    running.delete(id)
    if (outcome.parked) { park(id, outcome.parked); continue }
    done.add(id)
    merged.push({ id, merge_sha: outcome.merge_sha })
    trace.push({ id, event: 'merged' })
    log(`merged ${id}`)
    if (outcome.result.status === 'PARTIAL') enqueueRemainder(tasks, id, outcome.result, remainders, trace)
  }
  return { merged, parked: Array.from(parked.values()), remainders, trace }
}

function remainderId(tasks, id) {
  for (let n = 0; ; n++) {
    const rid = id + (n < 25 ? String.fromCharCode(98 + n) : 'b' + (n - 23))
    if (!tasks.some(t => t.id === rid)) return rid
  }
}

function enqueueRemainder(tasks, id, result, remainders, trace) {
  const rid = remainderId(tasks, id)
  const task = tasks.find(t => t.id === id)
  for (const t of tasks) if (t.depends_on.includes(id)) t.depends_on.push(rid)
  tasks.push(Object.assign({}, task, { id: rid, depends_on: [id], remainder_of: id,
    remaining_scope: result.remaining_scope || '', remaining_cases: result.remaining_cases || [] }))
  remainders.push({ id: rid, of: id, remaining_cases: result.remaining_cases || [] })
  trace.push({ id: rid, event: 'remainder' })
  log(`PARTIAL ${id} -> ${rid} (${(result.remaining_cases || []).length} cases left)`)
}

phase('Validate')
const input = args || {}
const error = validate(input)
if (error) {
  log('invalid args: ' + error)
  return { error }
}
const width = Math.min(MAX_WRITERS, Math.max(1, Math.floor(input.max_writers === undefined ? MAX_WRITERS : input.max_writers)))
if (input.dry_run) return simulate(normalize(input.tasks), width)
phase('Run')
return await schedule(input, width)
