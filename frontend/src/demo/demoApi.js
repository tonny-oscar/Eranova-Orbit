/**
 * In-memory API used only by `npm run dev:demo` (Vite mode "demo").
 *
 * Lets you click through every screen without the backend or a database.
 * Authentication is bypassed and you act as a Super Admin. All data is
 * sample data, resets on reload and is never sent anywhere.
 */

const DEMO_COMPANY = {
  id: 'demo-company',
  name: 'Eranova Technologies (demo)',
  slug: 'eranova',
  timezone: 'Africa/Nairobi',
}

const ACTIONS = ['read', 'create', 'update', 'delete', 'approve', 'export', 'manage']
const RESOURCES = {
  product: ACTIONS,
  lead: ACTIONS,
  customer: ACTIONS,
  project: ACTIONS,
  task: ACTIONS,
  employee: ACTIONS,
  campaign: ACTIONS,
  invoice: ACTIONS,
  ticket: ACTIONS,
  document: ACTIONS,
  integration: ACTIONS,
  report: ['read', 'create', 'export', 'manage'],
  user: ['read', 'create', 'update', 'delete', 'manage'],
  role: ['read', 'create', 'update', 'delete', 'manage'],
  audit_log: ['read', 'export'],
  settings: ['read', 'update'],
}
const SENSITIVE = new Set(['delete', 'approve', 'export', 'manage'])

const CATALOGUE = Object.entries(RESOURCES).flatMap(([resource, actions]) =>
  actions.map((action) => ({
    key: `${resource}.${action}`,
    resource,
    action,
    description: `${action[0].toUpperCase()}${action.slice(1)} ${resource.replace('_', ' ')}`,
    is_sensitive: SENSITIVE.has(action),
  })),
)
const ALL_KEYS = CATALOGUE.map((p) => p.key).sort()

let seq = 100
const id = (prefix) => `${prefix}-${++seq}`
const now = () => new Date().toISOString()

function makeState() {
  const users = [
    ['u-admin', 'Demo Admin', 'admin@demo.local'],
    ['u-asha', 'Asha Demo', 'asha@demo.local'],
    ['u-brian', 'Brian Demo', 'brian@demo.local'],
    ['u-chen', 'Chen Demo', 'chen@demo.local'],
  ].map(([uid, full_name, email]) => ({
    id: uid,
    full_name,
    email,
    status: 'active',
    last_login_at: now(),
    must_change_password: false,
  }))

  const roles = [
    { id: 'r-super', name: 'Super Admin', slug: 'super_admin', locked: true, perms: ALL_KEYS },
    {
      id: 'r-exec',
      name: 'Executive',
      slug: 'executive',
      perms: ALL_KEYS.filter((k) => k.endsWith('.read')),
    },
    {
      id: 'r-pm',
      name: 'Product Manager',
      slug: 'product_manager',
      perms: ['product.read', 'product.update', 'project.read', 'task.read'],
    },
    {
      id: 'r-dev',
      name: 'Developer',
      slug: 'developer',
      perms: ['product.read', 'task.read', 'task.update'],
    },
    {
      id: 'r-hr',
      name: 'HR',
      slug: 'hr',
      perms: ['employee.read', 'employee.create', 'employee.update', 'user.read'],
    },
  ].map((r) => ({
    id: r.id,
    name: r.name,
    slug: r.slug,
    description: 'Sample role (demo preview).',
    is_system: true,
    is_locked: Boolean(r.locked),
    permissions: r.perms,
  }))

  const departments = [
    { id: 'd-eng', name: 'Engineering', description: 'Sample department.', head_user_id: 'u-asha' },
    { id: 'd-sales', name: 'Sales', description: 'Sample department.', head_user_id: null },
  ]

  const profiles = {
    'u-asha': {
      department_id: 'd-eng',
      job_title: 'Engineering Lead',
      manager_user_id: null,
      employment_type: 'full_time',
      start_date: '2025-03-01',
    },
    'u-brian': {
      department_id: 'd-eng',
      job_title: 'Developer',
      manager_user_id: 'u-asha',
      employment_type: 'full_time',
      start_date: '2025-06-15',
    },
    'u-chen': {
      department_id: 'd-sales',
      job_title: 'Sales Associate',
      manager_user_id: null,
      employment_type: 'contract',
      start_date: null,
    },
  }

  const assignments = [
    { id: 'a-1', user_id: 'u-admin', role_id: 'r-super', scope_type: 'company', scope_id: null },
    { id: 'a-2', user_id: 'u-asha', role_id: 'r-pm', scope_type: 'company', scope_id: null },
    { id: 'a-3', user_id: 'u-brian', role_id: 'r-dev', scope_type: 'company', scope_id: null },
    { id: 'a-4', user_id: 'u-chen', role_id: 'r-hr', scope_type: 'own', scope_id: null },
  ]

  // Launch product names only; every other detail is left blank and unconfirmed.
  const products = ['ShulePoa', 'HostPilot', 'OTPGuard', 'SitePoa', 'MenuPoa'].map((name) => ({
    id: `p-${name.toLowerCase()}`,
    name,
    slug: name.toLowerCase(),
    category: null,
    tagline: null,
    description: '',
    lifecycle_status: 'draft',
    details_confirmed: false,
    owner_user_id: null,
    logo_url: null,
    website_url: null,
    repository_url: null,
    deployment_ref: null,
    docs_url: null,
    status_page_url: null,
    support_email: null,
    analytics_source: null,
    analytics_property_id: null,
    launch_date: null,
    pricing: [],
    created_at: now(),
    updated_at: now(),
  }))

  const history = Object.fromEntries(
    products.map((p) => [
      p.id,
      [
        {
          id: id('h'),
          from_status: null,
          to_status: 'draft',
          reason: 'Registered',
          changed_by: null,
          created_at: now(),
        },
      ],
    ]),
  )

  return {
    signedIn: true,
    users,
    roles,
    departments,
    profiles,
    assignments,
    products,
    history,
    members: {},
    audit: [],
  }
}

let state = makeState()

class DemoError extends Error {
  constructor(status, code, message, details = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

const userById = (uid) => state.users.find((u) => u.id === uid)
const ref = (u) => (u ? { id: u.id, full_name: u.full_name, email: u.email } : null)
const page = (items, query) => {
  const limit = Number(query.limit ?? 25)
  const offset = Number(query.offset ?? 0)
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset }
}
const matches = (q, ...fields) =>
  !q || fields.some((f) => (f ?? '').toLowerCase().includes(String(q).toLowerCase()))

function audit(action, resource_type = null, resource_id = null, outcome = 'success') {
  state.audit.unshift({
    id: id('e'),
    created_at: now(),
    actor_type: 'user',
    actor_user_id: 'u-admin',
    action,
    resource_type,
    resource_id,
    outcome,
    ip_address: '127.0.0.1',
    correlation_id: id('demo'),
    details: {},
  })
}

function me() {
  const admin = userById('u-admin')
  return {
    user: admin,
    company: DEMO_COMPANY,
    permissions: ALL_KEYS,
    roles: state.assignments
      .filter((a) => a.user_id === admin.id)
      .map((a) => {
        const role = state.roles.find((r) => r.id === a.role_id)
        return {
          assignment_id: a.id,
          role_id: role.id,
          role_slug: role.slug,
          role_name: role.name,
          scope_type: a.scope_type,
          scope_id: a.scope_id,
        }
      }),
    csrf_token: 'demo',
    session_expires_at: new Date(Date.now() + 12 * 3600_000).toISOString(),
  }
}

const roleOut = (r) => ({
  ...r,
  assignment_count: state.assignments.filter((a) => a.role_id === r.id).length,
})

function productOut(p) {
  return { ...p, owner: ref(userById(p.owner_user_id)), can_update: true, can_manage: true }
}

function userDetail(u) {
  return {
    ...u,
    roles: state.assignments
      .filter((a) => a.user_id === u.id)
      .map((a) => {
        const role = state.roles.find((r) => r.id === a.role_id)
        return {
          id: a.id,
          role_id: role.id,
          role_slug: role.slug,
          role_name: role.name,
          scope_type: a.scope_type,
          scope_id: a.scope_id,
          granted_by_user_id: 'u-admin',
          created_at: now(),
        }
      }),
    can_update: true,
    can_manage: u.id !== 'u-admin',
  }
}

function employeeOut(u) {
  const profile = state.profiles[u.id]
  const department = state.departments.find((d) => d.id === profile?.department_id)
  return {
    user: ref(u),
    status: u.status,
    department: department ? { id: department.id, name: department.name } : null,
    job_title: profile?.job_title ?? null,
    manager: ref(userById(profile?.manager_user_id)),
    employment_type: profile?.employment_type ?? null,
    start_date: profile?.start_date ?? null,
    has_profile: Boolean(profile),
    can_update: true,
  }
}

function departmentOut(d) {
  return {
    id: d.id,
    name: d.name,
    description: d.description,
    head: ref(userById(d.head_user_id)),
    member_count: Object.values(state.profiles).filter((p) => p.department_id === d.id).length,
    created_at: now(),
  }
}

function tempPassword() {
  return `Demo${Math.random().toString(36).slice(2, 14)}`
}

function findProduct(pid) {
  const product = state.products.find((p) => p.id === pid)
  if (!product) throw new DemoError(404, 'not_found', 'Product not found.')
  return product
}

function findUser(uid) {
  const user = userById(uid)
  if (!user) throw new DemoError(404, 'not_found', 'User not found.')
  return user
}

function findRole(rid) {
  const role = state.roles.find((r) => r.id === rid)
  if (!role) throw new DemoError(404, 'not_found', 'Role not found.')
  return role
}

function summary() {
  const byStatus = {}
  for (const p of state.products) {
    byStatus[p.lifecycle_status] = (byStatus[p.lifecycle_status] ?? 0) + 1
  }
  const active = state.users.filter((u) => u.status === 'active').length
  return {
    generated_at: now(),
    source: 'Demo preview (sample data, not live)',
    products: {
      total: state.products.length,
      by_status: byStatus,
      unconfirmed: state.products.filter((p) => !p.details_confirmed).length,
    },
    people: { active, departments: state.departments.length },
    accounts: {
      active,
      disabled: state.users.filter((u) => u.status === 'disabled').length,
      awaiting_first_sign_in: state.users.filter((u) => u.must_change_password).length,
    },
    recent_activity: state.audit.slice(0, 8),
  }
}

function search(query) {
  const term = (query.q ?? '').trim()
  if (term.length < 2) return { query: term, results: [] }
  const products = state.products
    .filter((p) => matches(term, p.name, p.slug, p.category))
    .map((p) => ({
      type: 'product',
      id: p.id,
      title: p.name,
      subtitle: p.category ?? p.slug,
      url: `/app/products/${p.id}`,
    }))
  const people = state.users
    .filter((u) => matches(term, u.full_name, u.email))
    .map((u) => ({
      type: 'person',
      id: u.id,
      title: u.full_name,
      subtitle: u.email,
      url: `/app/team/${u.id}`,
    }))
  return { query: term, results: [...products, ...people] }
}

const routes = [
  [
    'GET',
    /^\/ready$/,
    () => ({ status: 'ready', environment: 'demo preview', checks: { database: 'ok' } }),
  ],
  ['GET', /^\/health$/, () => ({ status: 'ok', version: 'demo' })],

  // Auth is bypassed: any credentials sign you in as the demo Super Admin.
  [
    'GET',
    /^\/api\/v1\/auth\/me$/,
    () => {
      if (!state.signedIn) throw new DemoError(401, 'not_authenticated', 'Sign in to continue.')
      return me()
    },
  ],
  [
    'POST',
    /^\/api\/v1\/auth\/login$/,
    () => {
      state.signedIn = true
      return me()
    },
  ],
  [
    'POST',
    /^\/api\/v1\/auth\/logout$/,
    () => {
      state.signedIn = false
      return null
    },
  ],
  ['POST', /^\/api\/v1\/auth\/change-password$/, () => null],

  ['GET', /^\/api\/v1\/dashboard\/summary$/, () => summary()],
  ['GET', /^\/api\/v1\/search$/, (_m, q) => search(q)],

  // Products
  [
    'GET',
    /^\/api\/v1\/products$/,
    (_m, q) =>
      page(
        state.products
          .filter((p) => matches(q.q, p.name, p.slug, p.category))
          .filter((p) => !q.status || p.lifecycle_status === q.status)
          .sort((a, b) => a.name.localeCompare(b.name))
          .map(productOut),
        q,
      ),
  ],
  [
    'POST',
    /^\/api\/v1\/products$/,
    (_m, _q, body) => {
      if (state.products.some((p) => p.slug === body.slug)) {
        throw new DemoError(409, 'product_slug_taken', 'Another product already uses this slug.', [
          { field: 'slug', message: 'This slug is already in use.' },
        ])
      }
      const product = {
        ...body,
        id: id('p'),
        lifecycle_status: body.lifecycle_status ?? 'draft',
        created_at: now(),
        updated_at: now(),
      }
      state.products.push(product)
      state.history[product.id] = [
        {
          id: id('h'),
          from_status: null,
          to_status: product.lifecycle_status,
          reason: 'Registered',
          changed_by: ref(userById('u-admin')),
          created_at: now(),
        },
      ]
      audit('product.create', 'product', product.id)
      return productOut(product)
    },
  ],
  ['GET', /^\/api\/v1\/products\/([^/]+)$/, ([pid]) => productOut(findProduct(pid))],
  [
    'PATCH',
    /^\/api\/v1\/products\/([^/]+)$/,
    ([pid], _q, body) => {
      const product = findProduct(pid)
      Object.assign(product, body, { updated_at: now() })
      audit('product.update', 'product', pid)
      return productOut(product)
    },
  ],
  [
    'POST',
    /^\/api\/v1\/products\/([^/]+)\/status$/,
    ([pid], _q, body) => {
      const product = findProduct(pid)
      if (product.lifecycle_status === body.status) {
        throw new DemoError(400, 'status_unchanged', 'The product already has this status.')
      }
      state.history[pid].unshift({
        id: id('h'),
        from_status: product.lifecycle_status,
        to_status: body.status,
        reason: body.reason,
        changed_by: ref(userById('u-admin')),
        created_at: now(),
      })
      product.lifecycle_status = body.status
      product.updated_at = now()
      audit('product.status.change', 'product', pid)
      return productOut(product)
    },
  ],
  ['GET', /^\/api\/v1\/products\/([^/]+)\/status-history$/, ([pid]) => state.history[pid] ?? []],
  ['GET', /^\/api\/v1\/products\/([^/]+)\/members$/, ([pid]) => state.members[pid] ?? []],
  [
    'POST',
    /^\/api\/v1\/products\/([^/]+)\/members$/,
    ([pid], _q, body) => {
      const member = {
        id: id('m'),
        user: ref(userById(body.user_id)),
        team_role: body.team_role,
        created_at: now(),
      }
      state.members[pid] = [...(state.members[pid] ?? []), member]
      audit('product.member.add', 'product', pid)
      return member
    },
  ],
  [
    'DELETE',
    /^\/api\/v1\/products\/([^/]+)\/members\/([^/]+)$/,
    ([pid, mid]) => {
      state.members[pid] = (state.members[pid] ?? []).filter((m) => m.id !== mid)
      return null
    },
  ],

  // Users
  [
    'GET',
    /^\/api\/v1\/users$/,
    (_m, q) =>
      page(
        state.users
          .filter((u) => matches(q.q, u.full_name, u.email))
          .filter((u) => !q.status || u.status === q.status)
          .sort((a, b) => a.full_name.localeCompare(b.full_name))
          .map((u) => ({
            ...u,
            role_names: state.assignments
              .filter((a) => a.user_id === u.id)
              .map((a) => state.roles.find((r) => r.id === a.role_id)?.name),
          })),
        q,
      ),
  ],
  [
    'POST',
    /^\/api\/v1\/users$/,
    (_m, _q, body) => {
      const user = {
        id: id('u'),
        full_name: body.full_name,
        email: body.email.toLowerCase(),
        status: 'active',
        last_login_at: null,
        must_change_password: true,
      }
      state.users.push(user)
      audit('user.create', 'user', user.id)
      return { user, temporary_password: tempPassword() }
    },
  ],
  ['GET', /^\/api\/v1\/users\/([^/]+)$/, ([uid]) => userDetail(findUser(uid))],
  [
    'PATCH',
    /^\/api\/v1\/users\/([^/]+)$/,
    ([uid], _q, body) => {
      const user = findUser(uid)
      Object.assign(user, body)
      audit('user.update', 'user', uid)
      return userDetail(user)
    },
  ],
  [
    'POST',
    /^\/api\/v1\/users\/([^/]+)\/reset-password$/,
    ([uid]) => {
      const user = findUser(uid)
      user.must_change_password = true
      audit('user.password.reset', 'user', uid)
      return { user, temporary_password: tempPassword() }
    },
  ],
  [
    'POST',
    /^\/api\/v1\/users\/([^/]+)\/roles$/,
    ([uid], _q, body) => {
      const assignment = {
        id: id('a'),
        user_id: uid,
        role_id: body.role_id,
        scope_type: body.scope_type,
        scope_id: body.scope_id,
      }
      state.assignments.push(assignment)
      audit('role.assignment.create', 'user', uid)
      return userDetail(findUser(uid)).roles.find((r) => r.id === assignment.id)
    },
  ],
  [
    'DELETE',
    /^\/api\/v1\/users\/([^/]+)\/roles\/([^/]+)$/,
    ([uid, aid]) => {
      state.assignments = state.assignments.filter((a) => a.id !== aid)
      audit('role.assignment.delete', 'user', uid)
      return null
    },
  ],

  // Roles and permissions
  ['GET', /^\/api\/v1\/authz\/permissions$/, () => CATALOGUE],
  ['GET', /^\/api\/v1\/roles$/, () => state.roles.map(roleOut)],
  [
    'POST',
    /^\/api\/v1\/roles$/,
    (_m, _q, body) => {
      const role = {
        id: id('r'),
        name: body.name,
        slug: body.name.toLowerCase().replace(/[^a-z0-9]+/g, '_'),
        description: body.description ?? '',
        is_system: false,
        is_locked: false,
        permissions: [...(body.permissions ?? [])].sort(),
      }
      state.roles.push(role)
      audit('role.create', 'role', role.id)
      return roleOut(role)
    },
  ],
  ['GET', /^\/api\/v1\/roles\/([^/]+)$/, ([rid]) => roleOut(findRole(rid))],
  [
    'PATCH',
    /^\/api\/v1\/roles\/([^/]+)$/,
    ([rid], _q, body) => {
      const role = findRole(rid)
      if (role.is_locked) {
        throw new DemoError(403, 'role_locked', 'The Super Admin role cannot be edited.')
      }
      Object.assign(
        role,
        body,
        body.permissions ? { permissions: [...body.permissions].sort() } : {},
      )
      audit('role.update', 'role', rid)
      return roleOut(role)
    },
  ],
  [
    'DELETE',
    /^\/api\/v1\/roles\/([^/]+)$/,
    ([rid]) => {
      state.roles = state.roles.filter((r) => r.id !== rid)
      audit('role.delete', 'role', rid)
      return null
    },
  ],

  // Audit
  [
    'GET',
    /^\/api\/v1\/audit-logs$/,
    (_m, q) =>
      page(
        state.audit.filter((e) => !q.action || e.action === q.action),
        q,
      ),
  ],

  // People
  [
    'GET',
    /^\/api\/v1\/employees$/,
    (_m, q) =>
      page(
        state.users
          .filter((u) => u.status !== 'disabled' && matches(q.q, u.full_name, u.email))
          .filter(
            (u) => !q.department_id || state.profiles[u.id]?.department_id === q.department_id,
          )
          .sort((a, b) => a.full_name.localeCompare(b.full_name))
          .map(employeeOut),
        q,
      ),
  ],
  ['GET', /^\/api\/v1\/employees\/([^/]+)$/, ([uid]) => employeeOut(findUser(uid))],
  [
    'PUT',
    /^\/api\/v1\/employees\/([^/]+)$/,
    ([uid], _q, body) => {
      state.profiles[uid] = { ...body }
      audit('employee.update', 'employee', uid)
      return employeeOut(findUser(uid))
    },
  ],
  [
    'GET',
    /^\/api\/v1\/departments$/,
    () => [...state.departments].sort((a, b) => a.name.localeCompare(b.name)).map(departmentOut),
  ],
  [
    'POST',
    /^\/api\/v1\/departments$/,
    (_m, _q, body) => {
      const department = {
        id: id('d'),
        name: body.name,
        description: body.description ?? '',
        head_user_id: body.head_user_id,
      }
      state.departments.push(department)
      audit('department.create', 'department', department.id)
      return departmentOut(department)
    },
  ],
  [
    'PATCH',
    /^\/api\/v1\/departments\/([^/]+)$/,
    ([did], _q, body) => {
      const department = state.departments.find((d) => d.id === did)
      Object.assign(department, body)
      audit('department.update', 'department', did)
      return departmentOut(department)
    },
  ],
]

/** Resolves like the real API: returns JSON data or throws { status, code, message, details }. */
export async function demoRequest(method, path, { query = {}, body } = {}) {
  await new Promise((resolve) => setTimeout(resolve, 120))
  for (const [routeMethod, pattern, handler] of routes) {
    if (routeMethod !== method) continue
    const match = pattern.exec(path)
    if (match) return structuredClone(handler(match.slice(1), query, body) ?? null)
  }
  throw new DemoError(404, 'not_found', `Demo preview has no data for ${method} ${path}.`)
}

export function resetDemoState() {
  state = makeState()
}
