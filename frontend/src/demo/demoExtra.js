/**
 * Demo-preview data and handlers for Phases 3–6 (CRM, delivery, portal,
 * integrations, marketing, support, documents, reports and NOVA).
 *
 * Used only by `npm run dev:demo`. Everything is clearly labelled sample data,
 * lives in memory and resets on reload.
 */

const DAY = 86_400_000
const isoDate = (offsetDays = 0) =>
  new Date(Date.now() + offsetDays * DAY).toISOString().slice(0, 10)
const isoTime = (offsetHours = 0) => new Date(Date.now() + offsetHours * 3_600_000).toISOString()

export function createExtra({ getState, page, matches, audit, DemoError, personRef, id, now }) {
  const S = () => getState()
  const users = () => S().users
  const userName = (uid) => users().find((u) => u.id === uid)?.full_name
  const nref = (uid) => (uid && userName(uid) ? { id: uid, name: userName(uid) } : null)
  const product = (pid) => S().products.find((p) => p.id === pid)
  const pref = (pid) => (product(pid) ? { id: pid, name: product(pid).name } : null)
  const notFound = (what) => {
    throw new DemoError(404, 'not_found', `${what} not found.`)
  }
  const bad = (code, message) => {
    throw new DemoError(400, code, message)
  }

  // --- Sample data --------------------------------------------------------------------

  function seed() {
    const st = S()
    if (st.extra) return st.extra
    const leads = [
      ['Amina Otieno (sample)', 'Lakeview Academy (sample)', 'contacted', -2, 'website'],
      ['Brian Kamau (sample)', 'Riverside Hotel (sample)', 'demo_scheduled', 2, 'referral'],
      ['Cynthia Wanjiru (sample)', 'Hilltop School (sample)', 'negotiation', 1, 'event'],
      ['David Mwangi (sample)', 'Coastline Clinic (sample)', 'converted', null, 'website'],
    ]
    leads.forEach(([full_name, organization, status, follow, source], i) => {
      st.leads.push({
        id: `l-extra-${i}`,
        full_name,
        organization,
        email: `lead${i}@demo.local`,
        phone: null,
        product_id: 'p-sample',
        source,
        status,
        priority: i === 2 ? 'high' : 'medium',
        owner_user_id: 'u-chen',
        next_follow_up: follow === null ? null : isoDate(follow),
        expected_value: null,
        currency: null,
        notes: '',
        marketing_consent: false,
        last_enquiry_at: null,
        created_at: isoTime(-24 * (i + 2)),
        enquiries: [],
        converted_customer_id: status === 'converted' ? 'c-coast' : null,
        converted_at: status === 'converted' ? isoTime(-24) : null,
      })
    })

    const extra = {
      stages: [
        ['new', 'New'],
        ['contacted', 'Contacted'],
        ['interested', 'Interested'],
        ['demo_scheduled', 'Demo scheduled'],
        ['negotiation', 'Negotiation'],
        ['converted', 'Converted'],
        ['lost', 'Lost'],
      ].map(([key, name], position) => ({
        id: `st-${key}`,
        key,
        name,
        position,
        is_won: key === 'converted',
        is_lost: key === 'lost',
      })),
      activities: [
        {
          id: 'act-1',
          type: 'call',
          subject: 'Intro call (sample)',
          body: 'Discussed their needs.',
          occurred_at: isoTime(-30),
          lead_id: 'l-extra-0',
          customer_id: null,
          created_by_user_id: 'u-chen',
        },
      ],
      customers: [
        {
          id: 'c-coast',
          name: 'Coastline Clinic (sample)',
          industry: 'Healthcare',
          website: null,
          email: 'info@coastline.demo',
          phone: null,
          status: 'active',
          account_manager_user_id: 'u-chen',
          notes: 'Converted from a lead in the demo.',
          created_at: isoTime(-24),
          contacts: [
            {
              id: 'ct-1',
              full_name: 'Dr. Sample Contact',
              email: 'contact@coastline.demo',
              phone: null,
              job_title: 'Director',
              is_primary: true,
            },
          ],
          subs: [
            {
              id: 'sub-1',
              product_id: 'p-sample',
              plan_name: 'Standard',
              status: 'active',
              start_date: isoDate(-30),
              renewal_date: isoDate(20),
            },
          ],
        },
        {
          id: 'c-sunrise',
          name: 'Sunrise Primary (sample)',
          industry: 'Education',
          website: null,
          email: null,
          phone: null,
          status: 'prospect',
          account_manager_user_id: 'u-chen',
          notes: '',
          created_at: isoTime(-100),
          contacts: [],
          subs: [],
        },
      ],
      projects: [
        {
          id: 'pr-v2',
          name: 'Sample App v2 launch (sample)',
          description: 'Sample project used in the demo preview.',
          status: 'active',
          priority: 'high',
          product_id: 'p-sample',
          manager_user_id: 'u-asha',
          start_date: isoDate(-14),
          due_date: isoDate(30),
          budget_amount: null,
          budget_currency: null,
          repository_url: null,
          docs_url: null,
          members: [
            { id: 'pm-1', user_id: 'u-asha', role_label: 'Lead' },
            { id: 'pm-2', user_id: 'u-brian', role_label: 'Developer' },
          ],
          milestones: [
            { id: 'ms-1', title: 'Beta release', due_date: isoDate(10), completed_at: null },
          ],
        },
      ],
      tasks: [
        ['Fix login timeout (sample)', 'u-brian', -3, 'high', 'in_progress'],
        ['Write release notes (sample)', 'u-admin', 5, 'medium', 'assigned'],
        ['Payment page redesign (sample)', 'u-brian', 7, 'critical', 'submitted'],
        ['Onboarding email sequence (sample)', 'u-chen', 12, 'medium', 'assigned'],
        ['Update help articles (sample)', 'u-admin', -1, 'low', 'in_progress'],
      ].map(([title, assignee, due, priority, status], i) => ({
        id: `t-${i + 1}`,
        project_id: 'pr-v2',
        parent_task_id: null,
        milestone_id: null,
        title,
        description: 'Sample task for the demo preview.',
        status,
        priority,
        assignee_user_id: assignee,
        reporter_user_id: 'u-asha',
        start_date: null,
        due_date: isoDate(due),
        estimate_hours: null,
        completed_at: null,
        updated_at: isoTime(-i),
        comments: [],
        reviews: [],
        events: [
          {
            id: id('ev'),
            actor_user_id: 'u-asha',
            kind: 'created',
            from_value: null,
            to_value: status,
            created_at: isoTime(-48),
          },
        ],
        links: [],
        depends_on: [],
      })),
      leave: [
        {
          id: 'lv-1',
          user_id: 'u-brian',
          type: 'annual',
          start_date: isoDate(7),
          end_date: isoDate(9),
          reason: 'Family visit (sample)',
          status: 'pending',
          decided_by_user_id: null,
          decided_at: null,
          decision_note: null,
          created_at: isoTime(-5),
        },
      ],
      attendance: [],
      notifications: [
        {
          id: 'n-1',
          kind: 'task.overdue',
          title: 'Overdue: Update help articles (sample)',
          body: '',
          link: '/app/tasks/t-5',
          read_at: null,
          created_at: isoTime(-2),
        },
        {
          id: 'n-2',
          kind: 'ticket.assigned',
          title: 'T-1001 assigned to you: Cannot reset password (sample)',
          body: '',
          link: '/app/support/tk-1',
          read_at: null,
          created_at: isoTime(-6),
        },
      ],
      connections: [
        {
          id: 'ic-uptime',
          provider: 'http_monitor',
          name: 'Sample App uptime (sample)',
          product_id: 'p-sample',
          config: { url: 'https://example.com', expected_status: 200 },
          secret_ref: null,
          webhook_secret_ref: null,
          capabilities: ['health_check', 'get_service_status'],
          status: 'active',
          sync_interval_minutes: 15,
          last_sync_at: isoTime(-0.2),
          last_success_at: isoTime(-0.2),
          last_error: null,
        },
        {
          id: 'ic-crm',
          provider: 'product_api',
          name: 'CRM production (sample)',
          product_id: 'p-sample',
          config: {
            base_url: 'https://crm.example.com',
            health_path: '/orbit/health',
            metrics_path: '/orbit/metrics',
          },
          secret_ref: 'INTEGRATION_CRM_API_KEY',
          webhook_secret_ref: null,
          capabilities: [
            'health_check',
            'get_service_status',
            'get_usage_metrics',
            'receive_webhook',
          ],
          status: 'error',
          sync_interval_minutes: 60,
          last_sync_at: isoTime(-1),
          last_success_at: null,
          last_error: 'Server variable INTEGRATION_CRM_API_KEY is not set (demo).',
        },
      ],
      campaigns: [
        {
          id: 'cp-1',
          name: 'Back-to-school launch (sample)',
          product_id: 'p-sample',
          objective: 'Sign up 20 schools.',
          audience: 'Head teachers in Nairobi',
          channels: ['email', 'facebook', 'whatsapp'],
          budget_amount: '50000.00',
          budget_currency: 'KES',
          start_date: isoDate(-5),
          end_date: isoDate(25),
          status: 'active',
          owner_user_id: 'u-chen',
          notes: '',
          created_at: isoTime(-120),
          metrics: [
            {
              id: 'mt-1',
              metric: 'Leads generated',
              value: '12.00',
              period_start: null,
              period_end: isoDate(-1),
              source: 'Sample figure (not real)',
              recorded_by_user_id: 'u-chen',
              created_at: isoTime(-20),
            },
          ],
        },
      ],
      content: [
        ['Launch announcement (sample)', 'announcement', 'facebook', 'draft', null],
        ['Welcome email (sample)', 'email', 'email', 'in_review', null],
        ['WhatsApp teaser (sample)', 'social_caption', 'whatsapp', 'scheduled', isoTime(48)],
      ].map(([title, kind, channel, status, scheduled_for], i) => ({
        id: `ci-${i + 1}`,
        title,
        kind,
        channel,
        status,
        scheduled_for,
        campaign_id: 'cp-1',
        product_id: 'p-sample',
        body: 'Sample copy for the demo. Replace with real content.',
        author_user_id: 'u-chen',
        approved_by_user_id: status === 'scheduled' ? 'u-admin' : null,
        approved_at: status === 'scheduled' ? isoTime(-3) : null,
        review_note: null,
        published_at: null,
        published_url: null,
        publish_method: null,
        published_by_user_id: null,
        failure_reason: null,
        created_at: isoTime(-30 + i),
        updated_at: isoTime(-10 + i),
      })),
      tickets: [
        ['Cannot reset password (sample)', 'high', 'account', 'assigned'],
        ['Invoice shows wrong amount (sample)', 'medium', 'billing', 'open'],
        ['Feature request: SMS reminders (sample)', 'low', 'feature_request', 'new'],
        ['App slow in the morning (sample)', 'urgent', 'bug', 'resolved'],
      ].map(([subject, priority, category, status], i) => ({
        id: `tk-${i + 1}`,
        number: 1001 + i,
        subject,
        priority,
        category,
        status,
        channel: 'email',
        product_id: 'p-sample',
        customer_id: 'c-coast',
        requester_name: 'Sample customer',
        requester_email: 'customer@demo.local',
        assignee_user_id: status === 'assigned' ? 'u-admin' : null,
        description: 'Reported by a sample customer.',
        resolution: status === 'resolved' ? 'Added a database index (sample).' : null,
        first_response_at: status === 'new' ? null : isoTime(-20 + i),
        resolved_at: status === 'resolved' ? isoTime(-2) : null,
        closed_at: null,
        created_at: isoTime(-24 - i * 5),
        updated_at: isoTime(-i),
        messages:
          status === 'new'
            ? []
            : [
                {
                  id: id('msg'),
                  body: "Thanks, we're looking into it.",
                  internal: false,
                  from_customer: false,
                  author_user_id: 'u-admin',
                  created_at: isoTime(-20 + i),
                },
              ],
        events: [
          {
            id: id('tev'),
            kind: 'created',
            from_value: null,
            to_value: 'new',
            actor_user_id: 'u-admin',
            created_at: isoTime(-24 - i * 5),
          },
        ],
      })),
      documents: [
        {
          id: 'doc-1',
          title: 'Leave policy (sample)',
          description: 'Sample document for the demo.',
          category: 'policy',
          visibility: 'scoped',
          product_id: null,
          owner_user_id: 'u-admin',
          current_version: 1,
          updated_at: isoTime(-50),
          members: [],
          versions: [
            {
              version: 1,
              filename: 'leave-policy-sample.txt',
              content_type: 'text/plain; charset=utf-8',
              size_bytes: 52,
              sha256: 'c0ffee0000000000000000000000000000000000000000000000000000000000',
              note: null,
              uploaded_by_user_id: 'u-admin',
              created_at: isoTime(-50),
            },
          ],
        },
      ],
      schedules: [],
      runs: [],
      nova: {
        conversations: [],
        messages: [],
        executions: [],
        memories: [],
        feedback: {},
        profile: null,
      },
    }
    st.extra = extra
    return extra
  }
  const X = () => seed()

  // --- CRM ------------------------------------------------------------------------------

  const activityOut = (a) => ({
    id: a.id,
    type: a.type,
    subject: a.subject,
    body: a.body,
    occurred_at: a.occurred_at,
    lead_id: a.lead_id,
    customer_id: a.customer_id,
    created_by: nref(a.created_by_user_id),
  })
  const findLead = (lid) => S().leads.find((l) => l.id === lid) ?? notFound('Lead')
  function leadSummary(l) {
    return {
      id: l.id,
      full_name: l.full_name,
      organization: l.organization,
      email: l.email,
      phone: l.phone,
      product: pref(l.product_id),
      source: l.source,
      status: l.status,
      priority: l.priority,
      owner: personRef(users().find((u) => u.id === l.owner_user_id)),
      next_follow_up: l.next_follow_up,
      last_enquiry_at: l.last_enquiry_at,
      created_at: l.created_at,
    }
  }
  function leadDetail(l) {
    const customer = X().customers.find((c) => c.id === l.converted_customer_id)
    return {
      ...leadSummary(l),
      notes: l.notes ?? '',
      expected_value: l.expected_value,
      currency: l.currency,
      marketing_consent: l.marketing_consent,
      enquiries: l.enquiries ?? [],
      activities: X()
        .activities.filter((a) => a.lead_id === l.id)
        .map(activityOut)
        .reverse(),
      converted_customer: customer ? { id: customer.id, name: customer.name } : null,
      converted_at: l.converted_at ?? null,
      can_update: true,
      can_convert: !customer,
    }
  }
  const findCustomer = (cid) => X().customers.find((c) => c.id === cid) ?? notFound('Customer')
  function customerSummary(c) {
    const renewals = c.subs
      .filter((s) => s.renewal_date && ['trial', 'active'].includes(s.status))
      .map((s) => s.renewal_date)
      .sort()
    return {
      id: c.id,
      name: c.name,
      industry: c.industry,
      status: c.status,
      email: c.email,
      phone: c.phone,
      account_manager: nref(c.account_manager_user_id),
      products: c.subs.map((s) => pref(s.product_id)).filter(Boolean),
      next_renewal: renewals[0] ?? null,
      created_at: c.created_at,
    }
  }
  function customerDetail(c) {
    return {
      ...customerSummary(c),
      website: c.website,
      notes: c.notes,
      contacts: c.contacts,
      subscriptions: c.subs.map((s) => ({ ...s, product: pref(s.product_id) })),
      activities: X()
        .activities.filter(
          (a) =>
            a.customer_id === c.id ||
            S().leads.some((l) => l.converted_customer_id === c.id && l.id === a.lead_id),
        )
        .map(activityOut)
        .reverse(),
      source_leads: S()
        .leads.filter((l) => l.converted_customer_id === c.id)
        .map((l) => ({ id: l.id, name: l.full_name })),
      can_update: true,
    }
  }

  // --- Work ------------------------------------------------------------------------------

  const findProject = (pid) => X().projects.find((p) => p.id === pid) ?? notFound('Project')
  const findTask = (tid) => X().tasks.find((t) => t.id === tid) ?? notFound('Task')
  const OPEN = [
    'created',
    'assigned',
    'in_progress',
    'submitted',
    'under_review',
    'revision_requested',
    'approved',
  ]
  const overdue = (t) => Boolean(t.due_date && t.due_date < isoDate(0) && OPEN.includes(t.status))
  const taskSummary = (t) => ({
    id: t.id,
    title: t.title,
    status: t.status,
    priority: t.priority,
    project: { id: t.project_id, name: findProject(t.project_id).name },
    assignee: nref(t.assignee_user_id),
    due_date: t.due_date,
    parent_task_id: t.parent_task_id,
    is_overdue: overdue(t),
    updated_at: t.updated_at,
  })
  function counts(pid) {
    const ts = X().tasks.filter((t) => t.project_id === pid)
    return {
      total: ts.length,
      open: ts.filter((t) => OPEN.includes(t.status)).length,
      overdue: ts.filter(overdue).length,
      awaiting_review: ts.filter((t) => ['submitted', 'under_review'].includes(t.status)).length,
      completed: ts.filter((t) => t.status === 'completed').length,
    }
  }
  const projectSummary = (p) => ({
    id: p.id,
    name: p.name,
    status: p.status,
    priority: p.priority,
    product: pref(p.product_id),
    manager: nref(p.manager_user_id),
    start_date: p.start_date,
    due_date: p.due_date,
    tasks: counts(p.id),
  })
  const projectDetail = (p) => ({
    ...projectSummary(p),
    description: p.description,
    budget_amount: p.budget_amount,
    budget_currency: p.budget_currency,
    repository_url: p.repository_url,
    docs_url: p.docs_url,
    members: p.members.map((m) => ({ id: m.id, user: nref(m.user_id), role_label: m.role_label })),
    milestones: p.milestones,
    can_update: true,
    can_create_tasks: true,
  })
  const TRANSITIONS = {
    created: ['in_progress', 'cancelled'],
    assigned: ['in_progress', 'cancelled'],
    in_progress: ['submitted', 'cancelled'],
    submitted: ['under_review', 'cancelled'],
    under_review: [],
    revision_requested: ['in_progress', 'cancelled'],
    approved: ['completed'],
    completed: [],
    cancelled: [],
  }
  const taskEvent = (t, kind, from, to) =>
    t.events.push({
      id: id('ev'),
      actor_user_id: 'u-admin',
      kind,
      from_value: from,
      to_value: to,
      created_at: now(),
    })
  const taskDetail = (t) => ({
    ...taskSummary(t),
    description: t.description,
    milestone_id: t.milestone_id,
    reporter: nref(t.reporter_user_id),
    start_date: t.start_date,
    estimate_hours: t.estimate_hours,
    completed_at: t.completed_at,
    subtasks: X()
      .tasks.filter((s) => s.parent_task_id === t.id)
      .map(taskSummary),
    depends_on: t.depends_on.map((d) => taskSummary(findTask(d))),
    comments: t.comments.map((c) => ({ ...c, author: nref(c.author_user_id) })),
    reviews: t.reviews.map((r) => ({ ...r, reviewer: nref(r.reviewer_user_id) })),
    events: t.events.map((e) => ({ ...e, actor: nref(e.actor_user_id) })),
    links: t.links,
    allowed_transitions: TRANSITIONS[t.status] ?? [],
    can_update: true,
    can_review:
      ['submitted', 'under_review'].includes(t.status) && t.assignee_user_id !== 'u-admin',
  })

  // --- Portal ------------------------------------------------------------------------------

  const leaveOut = (l) => ({
    id: l.id,
    person: nref(l.user_id),
    type: l.type,
    start_date: l.start_date,
    end_date: l.end_date,
    days: Math.round((new Date(l.end_date) - new Date(l.start_date)) / DAY) + 1,
    reason: l.reason,
    status: l.status,
    decided_by: nref(l.decided_by_user_id),
    decided_at: l.decided_at,
    decision_note: l.decision_note,
    created_at: l.created_at,
  })
  const attendanceOut = (a) => ({ ...a, person: nref(a.user_id) })
  const brief = (t) => {
    const s = taskSummary(t)
    return {
      id: s.id,
      title: s.title,
      status: s.status,
      priority: s.priority,
      project: s.project,
      due_date: s.due_date,
      is_overdue: s.is_overdue,
    }
  }

  // --- Integrations -------------------------------------------------------------------------

  const PROVIDERS = [
    [
      'product_api',
      'Eranova product API',
      'Connects a live Eranova product (CRM, ShulePoa, ...) via its Orbit endpoints.',
      [
        ['base_url', 'Product API base URL', true, 'url'],
        ['health_path', 'Health path', false, 'text'],
        ['metrics_path', 'Metrics path', false, 'text'],
      ],
      true,
      true,
    ],
    [
      'github',
      'GitHub',
      'Repository and pull request activity.',
      [
        ['owner', 'Owner', true, 'text'],
        ['repo', 'Repository', true, 'text'],
      ],
      false,
      true,
    ],
    [
      'vercel',
      'Vercel',
      'Deployments and their state.',
      [
        ['project_id', 'Project ID', true, 'text'],
        ['team_id', 'Team ID', false, 'text'],
      ],
      true,
      true,
    ],
    [
      'ga4',
      'Google Analytics 4',
      'Daily users, sessions, page views and conversions.',
      [['property_id', 'Property ID', true, 'text']],
      true,
      false,
    ],
    [
      'http_monitor',
      'Uptime monitor',
      'Status code, latency and TLS expiry.',
      [
        ['url', 'URL to check', true, 'url'],
        ['expected_status', 'Expected status', false, 'text'],
      ],
      false,
      false,
    ],
  ].map(([provider, label, description, fields, secret_required, supports_webhooks]) => ({
    provider,
    label,
    description,
    capabilities: ['health_check'],
    secret_required,
    supports_webhooks,
    secret_help: 'Store the credential as an INTEGRATION_* environment variable on the server.',
    config_fields: fields.map(([name, flabel, required, kind]) => ({
      name,
      label: flabel,
      required,
      help: '',
      kind,
    })),
  }))
  const providerLabel = (p) => PROVIDERS.find((x) => x.provider === p)?.label ?? p
  const findConnection = (cid) =>
    X().connections.find((c) => c.id === cid) ?? notFound('Integration')
  const connectionOut = (c) => ({
    ...c,
    provider_label: providerLabel(c.provider),
    product: pref(c.product_id),
    is_stale: false,
    webhook_url: PROVIDERS.find((p) => p.provider === c.provider)?.supports_webhooks
      ? `https://orbit.example/api/v1/webhooks/${c.provider}/${c.id}`
      : null,
    can_manage: true,
  })
  const uptimeRecord = () => ({
    kind: 'uptime_check',
    external_id: 'latest',
    observed_at: isoTime(-0.2),
    data: {
      up: true,
      status: 200,
      latency_ms: 142,
      error: null,
      certificate_expires_at: isoTime(24 * 60),
    },
  })

  // --- Marketing ----------------------------------------------------------------------------

  const findCampaign = (cid) => X().campaigns.find((c) => c.id === cid) ?? notFound('Campaign')
  const findContent = (cid) => X().content.find((c) => c.id === cid) ?? notFound('Content')
  function campaignOut(c) {
    const countsBy = {}
    for (const i of X().content.filter((i) => i.campaign_id === c.id))
      countsBy[i.status] = (countsBy[i.status] ?? 0) + 1
    // eslint-disable-next-line no-unused-vars
    const { metrics, product_id, owner_user_id, ...rest } = c
    return {
      ...rest,
      product: pref(product_id),
      owner: nref(owner_user_id),
      content_counts: countsBy,
      can_update: true,
    }
  }
  const campaignDetail = (c) => ({
    ...campaignOut(c),
    metrics: c.metrics.map((m) => ({ ...m, recorded_by: nref(m.recorded_by_user_id) })),
  })
  const CONTENT_ACTIONS = {
    submit: [['draft'], 'in_review'],
    approve: [['in_review'], 'approved'],
    request_changes: [['in_review'], 'draft'],
    schedule: [['approved'], 'scheduled'],
    unschedule: [['scheduled'], 'approved'],
    record_published: [['approved', 'scheduled', 'failed'], 'published'],
    record_failed: [['approved', 'scheduled'], 'failed'],
    reopen: [['approved', 'scheduled', 'failed'], 'draft'],
  }
  function contentOut(i) {
    const campaign = X().campaigns.find((c) => c.id === i.campaign_id)
    const allowed = Object.entries(CONTENT_ACTIONS)
      .filter(
        ([action, [from]]) =>
          from.includes(i.status) &&
          !(['approve', 'request_changes'].includes(action) && i.author_user_id === 'u-admin'),
      )
      .map(([action]) => action)
    return {
      id: i.id,
      title: i.title,
      kind: i.kind,
      channel: i.channel,
      body: i.body,
      status: i.status,
      campaign: campaign ? { id: campaign.id, name: campaign.name } : null,
      product: pref(i.product_id),
      author: nref(i.author_user_id),
      approved_by: nref(i.approved_by_user_id),
      approved_at: i.approved_at,
      review_note: i.review_note,
      scheduled_for: i.scheduled_for,
      published_at: i.published_at,
      published_url: i.published_url,
      publish_method: i.publish_method,
      published_by: nref(i.published_by_user_id),
      failure_reason: i.failure_reason,
      created_at: i.created_at,
      updated_at: i.updated_at,
      allowed_actions: allowed,
      can_edit: ['draft', 'in_review'].includes(i.status),
    }
  }

  // --- Support ------------------------------------------------------------------------------

  const findTicket = (tid) => X().tickets.find((t) => t.id === tid) ?? notFound('Ticket')
  const TICKET_FLOW = {
    new: ['open', 'assigned', 'in_progress', 'waiting_customer', 'resolved', 'closed'],
    open: ['assigned', 'in_progress', 'waiting_customer', 'resolved', 'closed'],
    assigned: ['open', 'in_progress', 'waiting_customer', 'resolved'],
    in_progress: ['assigned', 'waiting_customer', 'resolved'],
    waiting_customer: ['in_progress', 'resolved', 'closed'],
    resolved: ['closed', 'open'],
    closed: ['open'],
  }
  const OPEN_TICKETS = ['new', 'open', 'assigned', 'in_progress', 'waiting_customer']
  function ticketSummary(t) {
    const customer = X().customers.find((c) => c.id === t.customer_id)
    return {
      id: t.id,
      number: t.number,
      reference: `T-${t.number}`,
      subject: t.subject,
      status: t.status,
      priority: t.priority,
      category: t.category,
      channel: t.channel,
      product: pref(t.product_id),
      customer: customer ? { id: customer.id, name: customer.name } : null,
      requester_name: t.requester_name,
      requester_email: t.requester_email,
      assignee: nref(t.assignee_user_id),
      first_response_at: t.first_response_at,
      resolved_at: t.resolved_at,
      created_at: t.created_at,
      updated_at: t.updated_at,
    }
  }
  const ticketDetail = (t) => ({
    ...ticketSummary(t),
    description: t.description,
    resolution: t.resolution,
    closed_at: t.closed_at,
    messages: t.messages.map((m) => ({ ...m, author: nref(m.author_user_id) })),
    events: t.events.map((e) => ({ ...e, actor: nref(e.actor_user_id) })),
    allowed_statuses: TICKET_FLOW[t.status],
    can_update: true,
  })
  const ticketEvent = (t, kind, from, to) =>
    t.events.push({
      id: id('tev'),
      kind,
      from_value: from,
      to_value: to,
      actor_user_id: 'u-admin',
      created_at: now(),
    })

  // --- Documents -----------------------------------------------------------------------------

  const findDocument = (did) => X().documents.find((d) => d.id === did) ?? notFound('Document')
  function documentOut(d) {
    const v = d.versions.find((x) => x.version === d.current_version)
    return {
      id: d.id,
      title: d.title,
      description: d.description,
      category: d.category,
      visibility: d.visibility,
      product: pref(d.product_id),
      department: null,
      project: null,
      owner: nref(d.owner_user_id),
      current_version: d.current_version,
      filename: v.filename,
      content_type: v.content_type,
      size_bytes: v.size_bytes,
      updated_at: d.updated_at,
      can_update: true,
    }
  }
  const documentDetail = (d) => ({
    ...documentOut(d),
    versions: [...d.versions]
      .reverse()
      .map((v) => ({ ...v, uploaded_by: nref(v.uploaded_by_user_id) })),
    members: d.members.map(nref).filter(Boolean),
    can_manage_members: d.visibility === 'restricted',
  })
  function fileFromForm(form) {
    const file = form?.get?.('file')
    if (!file || !file.name) bad('file_empty', 'Choose a file to upload.')
    if (file.size > 10 * 1024 * 1024) bad('file_too_large', 'Files must be 10 MB or smaller.')
    const ext = file.name.split('.').pop().toLowerCase()
    const allowed = [
      'pdf',
      'docx',
      'xlsx',
      'pptx',
      'odt',
      'ods',
      'odp',
      'doc',
      'xls',
      'ppt',
      'png',
      'jpg',
      'jpeg',
      'webp',
      'csv',
      'txt',
      'md',
    ]
    if (!allowed.includes(ext))
      bad('file_type', `This file type is not accepted. Allowed: ${allowed.join(', ')}.`)
    return {
      filename: file.name.replace(/[^\w.\- ()]+/g, '_'),
      content_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
    }
  }

  // --- Reports -------------------------------------------------------------------------------

  const REPORTS = [
    ['executive', 'Executive summary', 'Headline figures across every area you can see.'],
    ['sales', 'Sales', 'Leads, conversions, sources and overdue follow-ups.'],
    ['support', 'Support', 'Ticket volumes, response and resolution times, ageing.'],
    ['delivery', 'Delivery', 'Projects, open and overdue tasks, completed work.'],
    ['marketing', 'Marketing', 'Campaigns, content pipeline and confirmed publications.'],
    ['traffic', 'Website traffic', 'Google Analytics totals per product.'],
    ['product', 'Products', 'Per-product subscriptions, work, support and integration health.'],
    ['people', 'People', 'Headcount, leave and attendance in aggregate.'],
  ].map(([key, title, description]) => ({ key, title, description }))
  const metric = (label, value, unit = null) => ({ label, value, unit })
  const section = (title, { metrics = [], columns = [], rows = [], note = null } = {}) => ({
    title,
    metrics,
    columns,
    rows,
    note,
  })
  function sections(key) {
    const leads = S().leads
    const tasks = X().tasks
    const tickets = X().tickets
    const salesSec = section('Sales', {
      metrics: [
        metric('New leads', leads.length),
        metric('Converted to customers', leads.filter((l) => l.status === 'converted').length),
        metric(
          'Overdue follow-ups (now)',
          leads.filter((l) => l.next_follow_up && l.next_follow_up < isoDate(0)).length,
        ),
      ],
    })
    const deliverySec = section('Delivery', {
      metrics: [
        metric('Open tasks (now)', tasks.filter((t) => OPEN.includes(t.status)).length),
        metric('Overdue tasks (now)', tasks.filter(overdue).length),
        metric('Completed in period', tasks.filter((t) => t.status === 'completed').length),
      ],
    })
    const supportSec = section('Support', {
      metrics: [
        metric('Open tickets (now)', tickets.filter((t) => OPEN_TICKETS.includes(t.status)).length),
        metric('Created in period', tickets.length),
        metric('Resolved in period', tickets.filter((t) => t.resolved_at).length),
      ],
    })
    const marketingSec = section('Marketing', {
      metrics: [
        metric('Active campaigns (now)', X().campaigns.filter((c) => c.status === 'active').length),
        metric(
          'Content published in period',
          X().content.filter((c) => c.status === 'published').length,
        ),
        metric('Awaiting review (now)', X().content.filter((c) => c.status === 'in_review').length),
      ],
    })
    const productsSec = section('Products', { metrics: [metric('Products', S().products.length)] })
    const bySource = {}
    for (const l of leads) bySource[l.source] = (bySource[l.source] ?? 0) + 1
    switch (key) {
      case 'executive':
        return [productsSec, salesSec, deliverySec, supportSec, marketingSec]
      case 'sales':
        return [
          salesSec,
          section('New leads by source', {
            columns: ['Source', 'Leads'],
            rows: Object.entries(bySource),
          }),
          section('Overdue follow-ups', {
            columns: ['Lead', 'Organisation', 'Follow-up date', 'Owner'],
            rows: leads
              .filter((l) => l.next_follow_up && l.next_follow_up < isoDate(0))
              .map((l) => [
                l.full_name,
                l.organization,
                l.next_follow_up,
                userName(l.owner_user_id) ?? 'Unassigned',
              ]),
          }),
        ]
      case 'support':
        return [
          supportSec,
          section('Open tickets by age', {
            columns: ['Ticket', 'Subject', 'Status', 'Priority', 'Assignee'],
            rows: tickets
              .filter((t) => OPEN_TICKETS.includes(t.status))
              .map((t) => [
                `T-${t.number}`,
                t.subject,
                t.status,
                t.priority,
                userName(t.assignee_user_id) ?? 'Unassigned',
              ]),
          }),
        ]
      case 'delivery':
        return [
          deliverySec,
          section('Projects', {
            columns: ['Project', 'Open tasks', 'Overdue'],
            rows: X().projects.map((p) => [p.name, counts(p.id).open, counts(p.id).overdue]),
          }),
        ]
      case 'marketing':
        return [
          marketingSec,
          section('Campaigns running in period', {
            columns: ['Campaign', 'Status', 'Start', 'End', 'Budget', 'Currency'],
            rows: X().campaigns.map((c) => [
              c.name,
              c.status,
              c.start_date,
              c.end_date,
              c.budget_amount,
              c.budget_currency,
            ]),
          }),
        ]
      case 'traffic':
        return [
          section('Website traffic by product', {
            columns: ['Product', 'Active users', 'Sessions'],
            rows: [],
            note: 'No Google Analytics data in the demo. Connect GA4 under Integrations.',
          }),
        ]
      case 'product':
        return [
          section('Products', {
            columns: ['Product', 'Status', 'Open tasks', 'Open tickets'],
            rows: S().products.map((p) => [
              p.name,
              p.lifecycle_status,
              p.id === 'p-sample' ? counts('pr-v2').open : 0,
              tickets.filter((t) => t.product_id === p.id && OPEN_TICKETS.includes(t.status))
                .length,
            ]),
          }),
        ]
      default:
        return [
          section('Headcount by department', {
            columns: ['Department', 'Active staff'],
            rows: S().departments.map((d) => [
              d.name,
              Object.values(S().profiles).filter((p) => p.department_id === d.id).length,
            ]),
          }),
        ]
    }
  }
  function runReport(key, q) {
    const r = REPORTS.find((x) => x.key === key) ?? notFound('Report')
    return {
      key,
      title: r.title,
      period: { start: q.start ?? isoDate(-29), end: q.end ?? isoDate(0) },
      product_id: q.product_id ?? null,
      generated_at: now(),
      sections: sections(key),
    }
  }

  // --- NOVA (basic mode, in the browser) -------------------------------------------------------

  const N = () => X().nova
  const profile = () =>
    N().profile ?? {
      preferred_name: null,
      response_style: 'balanced',
      language: 'en',
      learning_enabled: true,
    }
  const SENSITIVE =
    /(password|passcode|pin code|otp|api[_ -]?key|secret|token|private key|cvv|card number|(?:\d[ -]?){13,19})/i
  function remember(content, category, source) {
    const text = content.replace(/\s+/g, ' ').trim().replace(/\.$/, '')
    if (SENSITIVE.test(text))
      bad('memory_sensitive', "NOVA doesn't remember passwords, keys, codes or payment details.")
    const existing = N().memories.find((m) => m.content.toLowerCase() === text.toLowerCase())
    if (existing) return [existing, false]
    const note = {
      id: id('mem'),
      content: text,
      category,
      source,
      active: true,
      use_count: 0,
      last_used_at: null,
      created_at: now(),
      updated_at: now(),
    }
    N().memories.unshift(note)
    return [note, true]
  }
  const link = (label, href) => ({ label, href })
  function novaTool(name, args) {
    switch (name) {
      case 'my_work': {
        const mine = X().tasks.filter(
          (t) => t.assignee_user_id === 'u-admin' && OPEN.includes(t.status),
        )
        const lines = mine.map(
          (t) => `• ${t.title} (due ${t.due_date}${overdue(t) ? ', overdue' : ''})`,
        )
        return [
          `${mine.length} open task(s), ${mine.filter(overdue).length} overdue.\n${lines.join('\n')}`,
          mine.map((t) => link(t.title, `/app/tasks/${t.id}`)),
        ]
      }
      case 'list_tasks': {
        const late = X().tasks.filter(overdue)
        return [
          `${late.length} overdue task(s):\n${late.map((t) => `• ${t.title} (${userName(t.assignee_user_id) ?? 'unassigned'}, due ${t.due_date})`).join('\n')}`,
          late.map((t) => link(t.title, `/app/tasks/${t.id}`)),
        ]
      }
      case 'list_tickets': {
        const open = X().tickets.filter((t) => OPEN_TICKETS.includes(t.status))
        return [
          `${open.length} open ticket(s):\n${open.map((t) => `• T-${t.number} ${t.subject} (${t.priority})`).join('\n')}`,
          open.map((t) => link(`T-${t.number}`, `/app/support/${t.id}`)),
        ]
      }
      case 'business_summary':
        return [
          `Executive summary for the last 30 days:\n${sections('executive')
            .map(
              (s) => `• ${s.title}: ${s.metrics.map((m) => `${m.label}: ${m.value}`).join('; ')}`,
            )
            .join('\n')}`,
          [link('Executive report', '/app/reports/executive')],
        ]
      case 'run_report': {
        const r = runReport(args.key, {})
        return [
          `${r.title} report:\n${r.sections.map((s) => `• ${s.title}: ${s.metrics.length ? s.metrics.map((m) => `${m.label}: ${m.value}`).join('; ') : `${s.rows.length} row(s)`}`).join('\n')}`,
          [link(`${r.title} report`, `/app/reports/${args.key}`)],
        ]
      }
      case 'search_records': {
        const q = args.query
        const hits = [
          ...S()
            .products.filter((p) => matches(q, p.name))
            .map((p) => link(`product: ${p.name}`, `/app/products/${p.id}`)),
          ...S()
            .leads.filter((l) => matches(q, l.full_name, l.organization))
            .map((l) => link(`lead: ${l.full_name}`, `/app/leads/${l.id}`)),
          ...X()
            .customers.filter((c) => matches(q, c.name))
            .map((c) => link(`customer: ${c.name}`, `/app/customers/${c.id}`)),
          ...X()
            .tasks.filter((t) => matches(q, t.title))
            .map((t) => link(`task: ${t.title}`, `/app/tasks/${t.id}`)),
          ...X()
            .tickets.filter((t) => matches(q, t.subject))
            .map((t) => link(`ticket: T-${t.number}`, `/app/support/${t.id}`)),
        ]
        return [
          `Found ${hits.length} matching record(s) for '${q}'.\n${hits
            .slice(0, 10)
            .map((h) => `• ${h.label}`)
            .join('\n')}`,
          hits.slice(0, 10),
        ]
      }
      case 'product_status': {
        const p =
          S().products.find(
            (x) => x.name.toLowerCase() === args.product || x.slug === args.product,
          ) ?? notFound(`Product '${args.product}'`)
        return [
          `${p.name} is ${p.lifecycle_status}.${p.details_confirmed ? '' : ' Its details are not confirmed yet.'}`,
          [link(p.name, `/app/products/${p.id}`)],
        ]
      }
      case 'remember': {
        if (!args.user_asked && !profile().learning_enabled)
          bad('learning_disabled', 'Learning is switched off for this user.')
        const [note, created] = remember(
          args.content,
          args.category,
          args.user_asked ? 'told' : 'learned',
        )
        return [
          `${created ? (args.user_asked ? 'Remembered' : 'Noted for next time') : 'Already knew'}: ${note.content}`,
          [link('What NOVA remembers', '/app/nova/memory')],
        ]
      }
      case 'forget': {
        const words = args.text.toLowerCase().match(/\w{3,}/g) ?? []
        const gone = N().memories.filter((m) =>
          words.every((w) => m.content.toLowerCase().includes(w)),
        )
        N().memories = N().memories.filter((m) => !gone.includes(m))
        return [
          gone.length
            ? `Forgot ${gone.length} note(s).`
            : `Nothing in memory matched '${args.text}'.`,
          [],
        ]
      }
      case 'what_you_know': {
        const notes = N().memories.filter((m) => m.active)
        return [
          `${notes.length} note(s) in memory.\n${notes.map((m) => `• ${m.content}`).join('\n')}`,
          [link('What NOVA remembers', '/app/nova/memory')],
        ]
      }
      default:
        return ['', []]
    }
  }
  const HELP =
    'This is the demo preview, running in basic mode (no AI model), so I can look things up and learn about you. Try:\n' +
    '• "my work", "overdue tasks", "open tickets", "business summary"\n' +
    '• "search sample", "sales report", "status of ShulePoa"\n' +
    '• "remember that I manage ShulePoa", "I prefer short answers", "what do you know about me", "forget ShulePoa"'
  function plan(text) {
    const t = text.trim().toLowerCase()
    let m
    if ((m = text.trim().match(/^(?:please\s+)?remember(?:\s+that)?\s+(.{3,500})$/i)))
      return [
        'remember',
        {
          content: m[1],
          category: /\b(prefer|like|want|always|never)\b/i.test(m[1]) ? 'preference' : 'fact',
          user_asked: true,
        },
      ]
    if ((m = text.trim().match(/^forget(?:\s+that)?\s+(.{2,200})$/i)))
      return ['forget', { text: m[1] }]
    if (/what do you (know|remember) about me|what have you learned/.test(t))
      return ['what_you_know', {}]
    if (
      /^(i (prefer|like|love|want|usually|always|never)|my (role|job|focus|goal) is|i (manage|work on|lead|am responsible for))\b/.test(
        t,
      )
    )
      return [
        'remember',
        {
          content: text.trim(),
          category: /prefer|like|love|want|always|never|usually/.test(t) ? 'preference' : 'fact',
          user_asked: false,
        },
      ]
    if (/\b(help|what can you do)\b/.test(t)) return [null, {}]
    if ((m = t.match(/\b(?:status of|how is)\s+(.+?)\s*\??$/)) && !/business|everything/.test(m[1]))
      return ['product_status', { product: m[1].trim() }]
    if (/\b(summary|overview|how is (the )?business|dashboard)\b/.test(t))
      return ['business_summary', {}]
    for (const r of REPORTS)
      if (new RegExp(`\\b${r.key}\\s+report\\b`).test(t)) return ['run_report', { key: r.key }]
    if (/\boverdue\b/.test(t)) return ['list_tasks', {}]
    if (/\b(my (work|tasks|day)|what should i (do|work on)|todo)\b/.test(t)) return ['my_work', {}]
    if (/\b(tickets?|support queue)\b/.test(t)) return ['list_tickets', {}]
    if ((m = t.match(/\b(?:search|find|look up|lookup)\s+(?:for\s+)?(.+)$/)))
      return ['search_records', { query: m[1].replace(/[?.]$/, '') }]
    return [null, {}]
  }
  function novaReply(conversation, body) {
    const userMsg = {
      id: id('nm'),
      conversation_id: conversation.id,
      role: 'user',
      content: body.content,
      via: body.via ?? 'text',
      links: [],
      status: 'ok',
      provider: null,
      model: null,
      created_at: now(),
      rating: null,
    }
    N().messages.push(userMsg)
    if (conversation.title === 'New conversation') conversation.title = body.content.slice(0, 80)
    const [tool, args] = plan(body.content)
    let content = HELP
    let links = []
    const executions = []
    if (tool) {
      const exec = {
        id: id('nx'),
        conversation_id: conversation.id,
        tool,
        authority: ['remember', 'forget'].includes(tool) ? 'personal' : 'read',
        status: 'succeeded',
        summary: '',
        error: null,
        approval_id: null,
        created_at: now(),
      }
      try {
        ;[content, links] = novaTool(tool, args)
        exec.summary = content.split('\n')[0]
      } catch (error) {
        exec.status = 'failed'
        exec.error = error.message
        content = `I couldn't do that: ${error.message}`
      }
      executions.push(exec)
      N().executions.push(exec)
      if (tool !== 'remember' && tool !== 'forget' && tool !== 'what_you_know')
        content += '\n\n(Demo basic mode: figures come from the sample data; no AI model was used.)'
    }
    const name = profile().preferred_name
    if (!tool && name) content = `Hi ${name}. ${content}`
    const reply = {
      id: id('nm'),
      conversation_id: conversation.id,
      role: 'assistant',
      content,
      via: 'text',
      links,
      status: 'ok',
      provider: 'basic',
      model: null,
      created_at: new Date(Date.now() + 5).toISOString(),
      rating: null,
    }
    N().messages.push(reply)
    conversation.updated_at = reply.created_at
    return { message: reply, executions, approvals: [] }
  }
  const findConversation = (cid) =>
    N().conversations.find((c) => c.id === cid) ?? notFound('Conversation')

  // --- Routes ---------------------------------------------------------------------------------

  const R = (method, pattern, handler) => [method, new RegExp(`^/api/v1/${pattern}$`), handler]
  return [
    // CRM
    R('GET', 'crm/stages', () => X().stages),
    R('POST', 'crm/stages', (_m, _q, b) => {
      const stage = {
        id: id('st'),
        key: b.name.toLowerCase().replace(/\W+/g, '_'),
        name: b.name,
        position: X().stages.length,
        is_won: Boolean(b.is_won),
        is_lost: Boolean(b.is_lost),
      }
      X().stages.push(stage)
      return stage
    }),
    R('PATCH', 'crm/stages/([^/]+)', ([sid], _q, b) =>
      Object.assign(X().stages.find((s) => s.id === sid) ?? notFound('Stage'), b),
    ),
    R('DELETE', 'crm/stages/([^/]+)', ([sid]) => {
      X().stages = X().stages.filter((s) => s.id !== sid)
      return null
    }),
    R('GET', 'leads', (_m, q) => {
      X()
      return page(
        S()
          .leads.filter((l) => matches(q.q, l.full_name, l.email, l.organization))
          .filter((l) => !q.status || l.status === q.status)
          .filter((l) => !q.product_id || l.product_id === q.product_id)
          .map(leadSummary),
        q,
      )
    }),
    R('POST', 'leads', (_m, _q, b) => {
      const lead = {
        id: id('l'),
        phone: null,
        source: 'manual',
        status: 'new',
        priority: 'medium',
        owner_user_id: null,
        next_follow_up: null,
        expected_value: null,
        currency: null,
        notes: '',
        marketing_consent: false,
        last_enquiry_at: null,
        created_at: now(),
        enquiries: [],
        organization: null,
        product_id: null,
        ...b,
      }
      S().leads.unshift(lead)
      audit('lead.create', 'lead', lead.id)
      return leadDetail(lead)
    }),
    R('GET', 'leads/([^/]+)', ([lid]) => (X(), leadDetail(findLead(lid)))),
    R('PATCH', 'leads/([^/]+)', ([lid], _q, b) => {
      const lead = findLead(lid)
      Object.assign(lead, b)
      audit('lead.update', 'lead', lid)
      return leadDetail(lead)
    }),
    R('POST', 'leads/([^/]+)/activities', ([lid], _q, b) => {
      X().activities.push({
        id: id('act'),
        ...b,
        occurred_at: b.occurred_at ?? now(),
        lead_id: lid,
        customer_id: null,
        created_by_user_id: 'u-admin',
      })
      return leadDetail(findLead(lid))
    }),
    R('POST', 'leads/([^/]+)/convert', ([lid], _q, b) => {
      const lead = findLead(lid)
      let customer = b.customer_id ? findCustomer(b.customer_id) : null
      if (!customer) {
        customer = {
          id: id('c'),
          name: b.customer_name || lead.organization || lead.full_name,
          industry: null,
          website: null,
          email: lead.email,
          phone: lead.phone,
          status: 'active',
          account_manager_user_id: b.account_manager_user_id ?? lead.owner_user_id,
          notes: '',
          created_at: now(),
          contacts: [
            {
              id: id('ct'),
              full_name: lead.full_name,
              email: lead.email,
              phone: lead.phone,
              job_title: null,
              is_primary: true,
            },
          ],
          subs: lead.product_id
            ? [
                {
                  id: id('sub'),
                  product_id: lead.product_id,
                  plan_name: null,
                  status: 'active',
                  start_date: isoDate(0),
                  renewal_date: null,
                },
              ]
            : [],
        }
        X().customers.push(customer)
      }
      Object.assign(lead, {
        converted_customer_id: customer.id,
        converted_at: now(),
        status: 'converted',
      })
      return leadDetail(lead)
    }),
    R('GET', 'customers', (_m, q) =>
      page(
        X()
          .customers.filter((c) => matches(q.q, c.name, c.email))
          .filter((c) => !q.status || c.status === q.status)
          .map(customerSummary),
        q,
      ),
    ),
    R('POST', 'customers', (_m, _q, b) => {
      const c = {
        id: id('c'),
        website: null,
        email: null,
        phone: null,
        status: 'active',
        account_manager_user_id: null,
        notes: '',
        industry: null,
        created_at: now(),
        contacts: [],
        subs: [],
        ...b,
      }
      X().customers.push(c)
      return customerDetail(c)
    }),
    R('GET', 'customers/([^/]+)', ([cid]) => customerDetail(findCustomer(cid))),
    R('PATCH', 'customers/([^/]+)', ([cid], _q, b) =>
      customerDetail(Object.assign(findCustomer(cid), b)),
    ),
    R('POST', 'customers/([^/]+)/contacts', ([cid], _q, b) => {
      findCustomer(cid).contacts.push({
        id: id('ct'),
        email: null,
        phone: null,
        job_title: null,
        is_primary: false,
        ...b,
      })
      return customerDetail(findCustomer(cid))
    }),
    R('DELETE', 'customers/([^/]+)/contacts/([^/]+)', ([cid, ctid]) => {
      const c = findCustomer(cid)
      c.contacts = c.contacts.filter((x) => x.id !== ctid)
      return null
    }),
    R('PUT', 'customers/([^/]+)/subscriptions', ([cid], _q, b) => {
      const c = findCustomer(cid)
      const existing = c.subs.find((s) => s.product_id === b.product_id)
      if (existing) Object.assign(existing, b)
      else
        c.subs.push({
          id: id('sub'),
          plan_name: null,
          status: 'active',
          start_date: null,
          renewal_date: null,
          ...b,
        })
      return customerDetail(c)
    }),
    R('DELETE', 'customers/([^/]+)/subscriptions/([^/]+)', ([cid, sid]) => {
      const c = findCustomer(cid)
      c.subs = c.subs.filter((s) => s.id !== sid)
      return null
    }),
    R('POST', 'customers/([^/]+)/activities', ([cid], _q, b) => {
      X().activities.push({
        id: id('act'),
        ...b,
        occurred_at: b.occurred_at ?? now(),
        lead_id: null,
        customer_id: cid,
        created_by_user_id: 'u-admin',
      })
      return customerDetail(findCustomer(cid))
    }),

    // Projects and tasks
    R('GET', 'projects', (_m, q) =>
      page(
        X()
          .projects.filter((p) => matches(q.q, p.name))
          .filter((p) => !q.status || p.status === q.status)
          .map(projectSummary),
        q,
      ),
    ),
    R('POST', 'projects', (_m, _q, b) => {
      const p = {
        id: id('pr'),
        description: '',
        status: 'planned',
        priority: 'medium',
        product_id: null,
        manager_user_id: null,
        start_date: null,
        due_date: null,
        budget_amount: null,
        budget_currency: null,
        repository_url: null,
        docs_url: null,
        members: [],
        milestones: [],
        ...b,
      }
      X().projects.push(p)
      return projectDetail(p)
    }),
    R('GET', 'projects/([^/]+)', ([pid]) => projectDetail(findProject(pid))),
    R('PATCH', 'projects/([^/]+)', ([pid], _q, b) =>
      projectDetail(Object.assign(findProject(pid), b)),
    ),
    R('POST', 'projects/([^/]+)/members', ([pid], _q, b) => {
      findProject(pid).members.push({
        id: id('pm'),
        user_id: b.user_id,
        role_label: b.role_label ?? 'Member',
      })
      return projectDetail(findProject(pid))
    }),
    R('DELETE', 'projects/([^/]+)/members/([^/]+)', ([pid, mid]) => {
      const p = findProject(pid)
      p.members = p.members.filter((m) => m.id !== mid)
      return null
    }),
    R('POST', 'projects/([^/]+)/milestones', ([pid], _q, b) => {
      findProject(pid).milestones.push({
        id: id('ms'),
        title: b.title,
        due_date: b.due_date ?? null,
        completed_at: b.completed ? now() : null,
      })
      return projectDetail(findProject(pid))
    }),
    R('PUT', 'projects/([^/]+)/milestones/([^/]+)', ([pid, mid], _q, b) => {
      const ms = findProject(pid).milestones.find((m) => m.id === mid) ?? notFound('Milestone')
      Object.assign(ms, {
        title: b.title,
        due_date: b.due_date ?? null,
        completed_at: b.completed ? (ms.completed_at ?? now()) : null,
      })
      return projectDetail(findProject(pid))
    }),
    R('GET', 'tasks', (_m, q) => {
      let ts = X().tasks
      if (q.project_id) ts = ts.filter((t) => t.project_id === q.project_id)
      if (q.mine === 'true') ts = ts.filter((t) => t.assignee_user_id === 'u-admin')
      if (q.status) ts = ts.filter((t) => t.status === q.status)
      if (q.open_only === 'true') ts = ts.filter((t) => OPEN.includes(t.status))
      if (q.overdue === 'true') ts = ts.filter(overdue)
      if (q.top_level !== 'false') ts = ts.filter((t) => !t.parent_task_id)
      if (q.q) ts = ts.filter((t) => matches(q.q, t.title))
      return page(
        [...ts]
          .sort((a, b) => (a.due_date ?? '9').localeCompare(b.due_date ?? '9'))
          .map(taskSummary),
        q,
      )
    }),
    R('POST', 'tasks', (_m, _q, b) => {
      const t = {
        id: id('t'),
        parent_task_id: null,
        milestone_id: null,
        description: '',
        priority: 'medium',
        assignee_user_id: null,
        start_date: null,
        due_date: null,
        estimate_hours: null,
        ...b,
        status: b.assignee_user_id ? 'assigned' : 'created',
        reporter_user_id: 'u-admin',
        completed_at: null,
        updated_at: now(),
        comments: [],
        reviews: [],
        events: [],
        links: [],
        depends_on: [],
      }
      taskEvent(t, 'created', null, t.status)
      X().tasks.push(t)
      return taskDetail(t)
    }),
    R('GET', 'tasks/([^/]+)', ([tid]) => taskDetail(findTask(tid))),
    R('PATCH', 'tasks/([^/]+)', ([tid], _q, b) => {
      const t = findTask(tid)
      Object.assign(t, b, { updated_at: now() })
      if (b.assignee_user_id && t.status === 'created') t.status = 'assigned'
      return taskDetail(t)
    }),
    R('POST', 'tasks/([^/]+)/transition', ([tid], _q, b) => {
      const t = findTask(tid)
      if (!(TRANSITIONS[t.status] ?? []).includes(b.to))
        throw new DemoError(
          403,
          'transition_not_allowed',
          `You cannot move this task from '${t.status}' to '${b.to}'.`,
        )
      taskEvent(t, 'status', t.status, b.to)
      t.status = b.to
      if (b.to === 'completed') t.completed_at = now()
      t.updated_at = now()
      return taskDetail(t)
    }),
    R('POST', 'tasks/([^/]+)/review', ([tid], _q, b) => {
      const t = findTask(tid)
      t.reviews.push({
        id: id('rv'),
        reviewer_user_id: 'u-admin',
        decision: b.decision,
        comment: b.comment ?? '',
        created_at: now(),
      })
      taskEvent(t, 'status', t.status, b.decision)
      t.status = b.decision
      return taskDetail(t)
    }),
    R('POST', 'tasks/([^/]+)/comments', ([tid], _q, b) => {
      findTask(tid).comments.push({
        id: id('cm'),
        author_user_id: 'u-admin',
        body: b.body,
        created_at: now(),
      })
      return taskDetail(findTask(tid))
    }),
    R('POST', 'tasks/([^/]+)/dependencies', ([tid], _q, b) => {
      findTask(tid).depends_on.push(b.depends_on_task_id)
      return taskDetail(findTask(tid))
    }),
    R('DELETE', 'tasks/([^/]+)/dependencies/([^/]+)', ([tid, dep]) => {
      const t = findTask(tid)
      t.depends_on = t.depends_on.filter((d) => d !== dep)
      return null
    }),
    R('POST', 'tasks/([^/]+)/links', ([tid], _q, b) => {
      findTask(tid).links.push({
        id: id('lk'),
        kind: b.kind,
        url: b.url,
        title: b.title ?? null,
        created_at: now(),
      })
      return taskDetail(findTask(tid))
    }),

    // Employee portal and notifications
    R('GET', 'me/work', () => ({
      open_tasks: X()
        .tasks.filter((t) => t.assignee_user_id === 'u-admin' && OPEN.includes(t.status))
        .map(brief),
      awaiting_my_review: X()
        .tasks.filter(
          (t) =>
            ['submitted', 'under_review'].includes(t.status) && t.assignee_user_id !== 'u-admin',
        )
        .map(brief),
      leave_requests: X()
        .leave.filter((l) => l.user_id === 'u-admin')
        .map(leaveOut),
      leave_to_approve: X()
        .leave.filter((l) => l.user_id !== 'u-admin' && l.status === 'pending')
        .map(leaveOut),
      attendance_today:
        X()
          .attendance.filter((a) => a.user_id === 'u-admin' && a.work_date === isoDate(0))
          .map(attendanceOut)[0] ?? null,
      unread_notifications: X().notifications.filter((n) => !n.read_at).length,
    })),
    R('POST', 'leave-requests', (_m, _q, b) => {
      const l = {
        id: id('lv'),
        user_id: 'u-admin',
        reason: '',
        ...b,
        status: 'pending',
        decided_by_user_id: null,
        decided_at: null,
        decision_note: null,
        created_at: now(),
      }
      X().leave.push(l)
      return leaveOut(l)
    }),
    R('POST', 'leave-requests/([^/]+)/decision', ([lid], _q, b) => {
      const l = X().leave.find((x) => x.id === lid) ?? notFound('Leave request')
      Object.assign(l, {
        status: b.decision,
        decided_by_user_id: 'u-admin',
        decided_at: now(),
        decision_note: b.note || null,
      })
      return leaveOut(l)
    }),
    R('POST', 'leave-requests/([^/]+)/cancel', ([lid]) =>
      leaveOut(
        Object.assign(X().leave.find((x) => x.id === lid) ?? notFound('Leave request'), {
          status: 'cancelled',
        }),
      ),
    ),
    R('POST', 'attendance/check-in', (_m, _q, b) => {
      const a = {
        id: id('at'),
        user_id: 'u-admin',
        work_date: isoDate(0),
        check_in_at: now(),
        check_out_at: null,
        note: b?.note ?? null,
      }
      X().attendance.push(a)
      return attendanceOut(a)
    }),
    R('POST', 'attendance/check-out', () => {
      const a =
        X().attendance.find((x) => x.user_id === 'u-admin' && x.work_date === isoDate(0)) ??
        bad('not_checked_in', 'Check in first.')
      a.check_out_at = now()
      return attendanceOut(a)
    }),
    R('GET', 'attendance', () => X().attendance.map(attendanceOut)),
    R('GET', 'notifications', (_m, q) => ({
      ...page(X().notifications, q),
      unread: X().notifications.filter((n) => !n.read_at).length,
    })),
    R('POST', 'notifications/read-all', () => {
      X().notifications.forEach((n) => (n.read_at ??= now()))
      return null
    }),
    R('POST', 'notifications/([^/]+)/read', ([nid]) => {
      const n = X().notifications.find((x) => x.id === nid)
      if (n) n.read_at ??= now()
      return null
    }),

    // Integrations, monitoring and analytics
    R('GET', 'integrations/providers', () => PROVIDERS),
    R('GET', 'integrations', (_m, q) =>
      X()
        .connections.filter((c) => !q.product_id || c.product_id === q.product_id)
        .map(connectionOut),
    ),
    R('POST', 'integrations', (_m, _q, b) => {
      if (b.secret_ref && !/^INTEGRATION_[A-Z0-9_]{3,60}$/.test(b.secret_ref))
        bad('invalid_secret_ref', 'Credential variables must be named INTEGRATION_…')
      const c = {
        id: id('ic'),
        webhook_secret_ref: null,
        secret_ref: null,
        product_id: null,
        sync_interval_minutes: 60,
        ...b,
        capabilities: ['health_check'],
        status: 'active',
        last_sync_at: null,
        last_success_at: null,
        last_error: null,
      }
      X().connections.push(c)
      return connectionOut(c)
    }),
    R('GET', 'integrations/([^/]+)', ([cid]) => connectionOut(findConnection(cid))),
    R('PATCH', 'integrations/([^/]+)', ([cid], _q, b) =>
      connectionOut(Object.assign(findConnection(cid), b)),
    ),
    R('DELETE', 'integrations/([^/]+)', ([cid]) => {
      X().connections = X().connections.filter((c) => c.id !== cid)
      return null
    }),
    R('POST', 'integrations/([^/]+)/test', ([cid]) => {
      const c = findConnection(cid)
      return c.provider === 'http_monitor'
        ? { ok: true, message: 'Responded with HTTP 200 in 142 ms (demo).', details: {} }
        : { ok: false, message: 'Demo preview cannot reach external services.', details: {} }
    }),
    R('POST', 'integrations/([^/]+)/sync', ([cid]) => {
      const c = findConnection(cid)
      const ok = c.provider === 'http_monitor'
      Object.assign(c, {
        last_sync_at: now(),
        ...(ok
          ? { last_success_at: now(), last_error: null, status: 'active' }
          : { last_error: 'Demo preview cannot reach external services.', status: 'error' }),
      })
      return {
        id: id('run'),
        trigger: 'manual',
        status: ok ? 'success' : 'failed',
        started_at: now(),
        finished_at: now(),
        summary: ok ? { up: true, latency_ms: 142 } : {},
        error: ok ? null : c.last_error,
      }
    }),
    R('GET', 'integrations/([^/]+)/runs', ([cid]) => {
      const c = findConnection(cid)
      return c.last_sync_at
        ? [
            {
              id: `run-${cid}`,
              trigger: 'scheduled',
              status: c.last_error ? 'failed' : 'success',
              started_at: c.last_sync_at,
              finished_at: c.last_sync_at,
              summary: c.last_error ? {} : { up: true, latency_ms: 142 },
              error: c.last_error,
            },
          ]
        : []
    }),
    R('GET', 'products/([^/]+)/operations', ([pid]) => {
      const conns = X().connections.filter((c) => c.product_id === pid)
      const fresh = (provider) => {
        const c = conns.find((x) => x.provider === provider)
        return c ? { source: c.name, last_success_at: c.last_success_at, stale: false } : null
      }
      return {
        integrations: conns.map((c) => ({
          id: c.id,
          name: c.name,
          provider: c.provider,
          status: c.status,
          last_success_at: c.last_success_at,
          last_error: c.last_error,
          stale: false,
        })),
        deployments: [],
        pull_requests: [],
        uptime: conns.some((c) => c.provider === 'http_monitor') ? uptimeRecord() : null,
        product_metrics: null,
        traffic: null,
        freshness: {
          ga4: null,
          http_monitor: fresh('http_monitor'),
          vercel: null,
          github: null,
          product_api: fresh('product_api'),
        },
      }
    }),
    R('GET', 'monitoring/overview', () => ({
      integrations: X().connections.map((c) => ({
        id: c.id,
        name: c.name,
        provider: c.provider,
        product: pref(c.product_id),
        status: c.status,
        last_success_at: c.last_success_at,
        last_error: c.last_error,
        stale: false,
      })),
      monitors: X()
        .connections.filter((c) => c.provider === 'http_monitor')
        .map((c) => ({
          id: c.id,
          name: c.name,
          product: pref(c.product_id),
          url: c.config.url,
          latest: uptimeRecord(),
          uptime_percent: 100,
          checks: 48,
        })),
      deployments: [],
    })),
    R('GET', 'analytics/overview', () =>
      S().products.map((p) => ({
        product: { id: p.id, name: p.name },
        traffic: null,
        traffic_freshness: null,
        product_metrics: null,
        product_metrics_freshness:
          p.id === 'p-sample'
            ? { source: 'CRM production (sample)', last_success_at: null, stale: false }
            : null,
      })),
    ),

    // Marketing
    R('GET', 'marketing/campaigns', (_m, q) =>
      page(
        X()
          .campaigns.filter((c) => !q.status || c.status === q.status)
          .map(campaignOut),
        q,
      ),
    ),
    R('POST', 'marketing/campaigns', (_m, _q, b) => {
      const c = {
        id: id('cp'),
        objective: '',
        audience: '',
        channels: [],
        budget_amount: null,
        budget_currency: null,
        start_date: null,
        end_date: null,
        status: 'planned',
        owner_user_id: 'u-admin',
        notes: '',
        product_id: null,
        created_at: now(),
        metrics: [],
        ...b,
      }
      X().campaigns.push(c)
      return campaignDetail(c)
    }),
    R('GET', 'marketing/campaigns/([^/]+)', ([cid]) => campaignDetail(findCampaign(cid))),
    R('PATCH', 'marketing/campaigns/([^/]+)', ([cid], _q, b) =>
      campaignDetail(Object.assign(findCampaign(cid), b)),
    ),
    R('DELETE', 'marketing/campaigns/([^/]+)', ([cid]) => {
      if (X().content.some((i) => i.campaign_id === cid && i.status === 'published'))
        bad(
          'campaign_has_published_content',
          'This campaign has published content. Mark it cancelled or completed instead.',
        )
      X().campaigns = X().campaigns.filter((c) => c.id !== cid)
      return null
    }),
    R('POST', 'marketing/campaigns/([^/]+)/metrics', ([cid], _q, b) => {
      findCampaign(cid).metrics.unshift({
        id: id('mt'),
        period_start: null,
        period_end: null,
        ...b,
        recorded_by_user_id: 'u-admin',
        created_at: now(),
      })
      return campaignDetail(findCampaign(cid))
    }),
    R('DELETE', 'marketing/campaigns/([^/]+)/metrics/([^/]+)', ([cid, mid]) => {
      const c = findCampaign(cid)
      c.metrics = c.metrics.filter((m) => m.id !== mid)
      return null
    }),
    R('GET', 'marketing/content', (_m, q) =>
      page(
        X()
          .content.filter((i) => !q.status || i.status === q.status)
          .filter((i) => !q.kind || i.kind === q.kind)
          .filter((i) => !q.campaign_id || i.campaign_id === q.campaign_id)
          .map(contentOut),
        q,
      ),
    ),
    R('POST', 'marketing/content', (_m, _q, b) => {
      const campaign = b.campaign_id ? findCampaign(b.campaign_id) : null
      const i = {
        id: id('ci'),
        body: '',
        channel: null,
        ...b,
        product_id: campaign?.product_id ?? b.product_id ?? null,
        status: 'draft',
        scheduled_for: null,
        author_user_id: 'u-admin',
        approved_by_user_id: null,
        approved_at: null,
        review_note: null,
        published_at: null,
        published_url: null,
        publish_method: null,
        published_by_user_id: null,
        failure_reason: null,
        created_at: now(),
        updated_at: now(),
      }
      X().content.push(i)
      return contentOut(i)
    }),
    R('GET', 'marketing/content/([^/]+)', ([cid]) => contentOut(findContent(cid))),
    R('PATCH', 'marketing/content/([^/]+)', ([cid], _q, b) => {
      const i = findContent(cid)
      if (!['draft', 'in_review'].includes(i.status))
        bad('content_locked', 'Approved content is locked. Reopen it as a draft to edit.')
      Object.assign(i, b, { status: 'draft', updated_at: now() })
      return contentOut(i)
    }),
    R('DELETE', 'marketing/content/([^/]+)', ([cid]) => {
      X().content = X().content.filter((i) => i.id !== cid)
      return null
    }),
    R('POST', 'marketing/content/([^/]+)/actions', ([cid], _q, b) => {
      const i = findContent(cid)
      const out = contentOut(i)
      if (!out.allowed_actions.includes(b.action)) {
        if (b.action === 'approve')
          throw new DemoError(
            403,
            'permission_denied',
            'Someone other than the author must approve this content.',
          )
        bad('invalid_transition', `'${b.action}' is not available while content is ${i.status}.`)
      }
      if (b.action === 'schedule' && (!b.scheduled_for || new Date(b.scheduled_for) <= new Date()))
        bad('invalid_schedule', 'Choose a future date and time to schedule.')
      if (b.action === 'record_published' && !b.published_url)
        bad(
          'published_url_required',
          'Add the link to the live post so the publication can be verified.',
        )
      if (['request_changes', 'record_failed'].includes(b.action) && !b.note)
        bad('note_required', 'Add a note.')
      Object.assign(i, {
        status: CONTENT_ACTIONS[b.action][1],
        updated_at: now(),
        ...(b.action === 'schedule' && { scheduled_for: b.scheduled_for }),
        ...(b.action === 'approve' && {
          approved_by_user_id: 'u-admin',
          approved_at: now(),
          review_note: b.note ?? null,
        }),
        ...(b.action === 'request_changes' && { review_note: b.note }),
        ...(b.action === 'record_published' && {
          published_url: b.published_url,
          published_at: now(),
          publish_method: 'manual',
          published_by_user_id: 'u-admin',
        }),
        ...(b.action === 'record_failed' && { failure_reason: b.note }),
        ...(['reopen', 'unschedule'].includes(b.action) && { scheduled_for: null }),
      })
      return contentOut(i)
    }),
    R('GET', 'marketing/calendar', (_m, q) => ({
      content: X()
        .content.filter((i) => {
          const when = i.published_at ?? i.scheduled_for
          return when && when >= q.start && when < q.end
        })
        .map(contentOut),
      campaigns: X()
        .campaigns.filter((c) => c.status !== 'cancelled')
        .map(campaignOut),
    })),

    // Support
    R('GET', 'support/metrics', () => ({
      window_days: 30,
      generated_at: now(),
      open: X().tickets.filter((t) => OPEN_TICKETS.includes(t.status)).length,
      by_status: {},
      open_by_priority: {},
      created: X().tickets.length,
      resolved: X().tickets.filter((t) => t.resolved_at).length,
      median_first_response_hours: 3.5,
      median_resolution_hours: 22,
      by_category: {},
    })),
    R('GET', 'support/tickets', (_m, q) => {
      let ts = X().tickets
      if (q.status) ts = ts.filter((t) => t.status === q.status)
      if (q.open_only === 'true') ts = ts.filter((t) => OPEN_TICKETS.includes(t.status))
      if (q.assignee === 'me') ts = ts.filter((t) => t.assignee_user_id === 'u-admin')
      if (q.assignee === 'unassigned') ts = ts.filter((t) => !t.assignee_user_id)
      if (q.q)
        ts = ts.filter((t) =>
          matches(q.q.replace(/^t-/i, ''), t.subject, String(t.number), t.requester_email),
        )
      return page(
        [...ts].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).map(ticketSummary),
        q,
      )
    }),
    R('POST', 'support/tickets', (_m, _q, b) => {
      const t = {
        id: id('tk'),
        number: 1001 + X().tickets.length,
        description: '',
        channel: 'email',
        category: 'question',
        priority: 'medium',
        product_id: null,
        customer_id: null,
        requester_name: null,
        requester_email: null,
        assignee_user_id: null,
        ...b,
        status: b.assignee_user_id ? 'assigned' : 'new',
        resolution: null,
        first_response_at: null,
        resolved_at: null,
        closed_at: null,
        created_at: now(),
        updated_at: now(),
        messages: [],
        events: [],
      }
      ticketEvent(t, 'created', null, t.status)
      X().tickets.push(t)
      return ticketDetail(t)
    }),
    R('GET', 'support/tickets/([^/]+)', ([tid]) => ticketDetail(findTicket(tid))),
    R('PATCH', 'support/tickets/([^/]+)', ([tid], _q, b) => {
      const t = findTicket(tid)
      Object.assign(t, b, { updated_at: now() })
      if (b.assignee_user_id && ['new', 'open'].includes(t.status)) t.status = 'assigned'
      return ticketDetail(t)
    }),
    R('POST', 'support/tickets/([^/]+)/transition', ([tid], _q, b) => {
      const t = findTicket(tid)
      if (!TICKET_FLOW[t.status].includes(b.status))
        bad('invalid_transition', `A ticket cannot move from ${t.status} to ${b.status}.`)
      if (['resolved', 'closed'].includes(b.status)) {
        const resolution = (b.resolution ?? t.resolution ?? '').trim()
        if (!resolution) bad('resolution_required', 'Record how the ticket was resolved.')
        t.resolution = resolution
        t.resolved_at ??= now()
        if (b.status === 'closed') t.closed_at = now()
      }
      if (b.status === 'open') t.resolved_at = t.closed_at = null
      ticketEvent(t, 'status', t.status, b.status)
      Object.assign(t, { status: b.status, updated_at: now() })
      return ticketDetail(t)
    }),
    R('POST', 'support/tickets/([^/]+)/messages', ([tid], _q, b) => {
      const t = findTicket(tid)
      t.messages.push({
        id: id('msg'),
        body: b.body,
        internal: Boolean(b.internal),
        from_customer: Boolean(b.from_customer),
        author_user_id: 'u-admin',
        created_at: now(),
      })
      if (!b.internal && !b.from_customer) {
        t.first_response_at ??= now()
        if (t.status === 'new') t.status = 'open'
      }
      t.updated_at = now()
      return ticketDetail(t)
    }),

    // Documents
    R('GET', 'documents', (_m, q) =>
      page(
        X()
          .documents.filter((d) => matches(q.q, d.title, d.description))
          .filter((d) => !q.category || d.category === q.category)
          .map(documentOut),
        q,
      ),
    ),
    R('POST', 'documents', (_m, _q, form) => {
      const file = fileFromForm(form)
      const d = {
        id: id('doc'),
        title: form.get('title'),
        description: form.get('description') ?? '',
        category: form.get('category') ?? 'other',
        visibility: form.get('visibility') ?? 'scoped',
        product_id: form.get('product_id') || null,
        owner_user_id: 'u-admin',
        current_version: 1,
        updated_at: now(),
        members: [],
        versions: [
          {
            version: 1,
            ...file,
            sha256: 'demo'.padEnd(64, '0'),
            note: null,
            uploaded_by_user_id: 'u-admin',
            created_at: now(),
          },
        ],
      }
      X().documents.unshift(d)
      return documentDetail(d)
    }),
    R('GET', 'documents/([^/]+)', ([did]) => documentDetail(findDocument(did))),
    R('PATCH', 'documents/([^/]+)', ([did], _q, b) =>
      documentDetail(Object.assign(findDocument(did), b, { updated_at: now() })),
    ),
    R('POST', 'documents/([^/]+)/versions', ([did], _q, form) => {
      const d = findDocument(did)
      d.current_version += 1
      d.versions.push({
        version: d.current_version,
        ...fileFromForm(form),
        sha256: 'demo'.padEnd(64, '0'),
        note: form.get('note') || null,
        uploaded_by_user_id: 'u-admin',
        created_at: now(),
      })
      d.updated_at = now()
      return documentDetail(d)
    }),
    R('PUT', 'documents/([^/]+)/members', ([did], _q, b) =>
      documentDetail(Object.assign(findDocument(did), { members: b.user_ids })),
    ),
    R('DELETE', 'documents/([^/]+)', ([did]) => {
      X().documents = X().documents.filter((d) => d.id !== did)
      return null
    }),

    // Reports
    R('GET', 'reports', () => REPORTS),
    R('GET', 'reports/schedules', () => X().schedules),
    R('POST', 'reports/schedules', (_m, _q, b) => {
      const s = {
        id: id('rs'),
        ...b,
        report_title: REPORTS.find((r) => r.key === b.report_key)?.title,
        recipients: b.recipient_user_ids.map(nref).filter(Boolean),
        owner: nref('u-admin'),
        active: true,
        next_run_at: isoTime(14),
        last_run_at: null,
        can_manage: true,
      }
      X().schedules.push(s)
      return s
    }),
    R('PATCH', 'reports/schedules/([^/]+)', ([sid], _q, b) =>
      Object.assign(X().schedules.find((s) => s.id === sid) ?? notFound('Schedule'), b),
    ),
    R('DELETE', 'reports/schedules/([^/]+)', ([sid]) => {
      X().schedules = X().schedules.filter((s) => s.id !== sid)
      return null
    }),
    R('GET', 'reports/runs', () => X().runs),
    R(
      'GET',
      'reports/runs/([^/]+)',
      ([rid]) => X().runs.find((r) => r.id === rid) ?? notFound('Report'),
    ),
    R('GET', 'reports/([a-z]+)', ([key], q) => runReport(key, q)),

    // NOVA
    R('GET', 'nova/status', () => ({
      mode: 'basic',
      provider: null,
      model: null,
      capabilities: {
        tool_calling: false,
        streaming: false,
        json_output: false,
        context_tokens: null,
      },
      tools: [],
      retention_days: 180,
      shares_contact_details: false,
      can_view_company_usage: true,
    })),
    R('POST', 'nova/test', () => ({
      ok: false,
      mode: 'basic',
      message: 'The demo preview has no AI model. Run the full app after `npm run nova:setup`.',
    })),
    R('GET', 'nova/conversations', () =>
      [...N().conversations].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    ),
    R('POST', 'nova/conversations', () => {
      const c = { id: id('nc'), title: 'New conversation', updated_at: now() }
      N().conversations.push(c)
      return c
    }),
    R('GET', 'nova/conversations/([^/]+)', ([cid]) => ({
      conversation: findConversation(cid),
      messages: N()
        .messages.filter((m) => m.conversation_id === cid)
        .map((m) => ({ ...m, rating: N().feedback[m.id] ?? null })),
      executions: N().executions.filter((e) => e.conversation_id === cid),
    })),
    R('DELETE', 'nova/conversations/([^/]+)', ([cid]) => {
      N().conversations = N().conversations.filter((c) => c.id !== cid)
      return null
    }),
    R('POST', 'nova/conversations/([^/]+)/messages', ([cid], _q, b) =>
      novaReply(findConversation(cid), b),
    ),
    R('GET', 'nova/approvals', () => []),
    R('GET', 'nova/usage', () => ({
      window_days: 30,
      scope: 'company',
      replies: N().messages.filter((m) => m.role === 'assistant').length,
      prompt_tokens: 0,
      completion_tokens: 0,
      cost_usd: null,
      avg_latency_ms: 0,
      provider_errors: 0,
      tool_outcomes: {},
      by_user: [],
      daily_token_limit: 200000,
    })),
    R('GET', 'nova/profile', () => profile()),
    R(
      'PUT',
      'nova/profile',
      (_m, _q, b) => (N().profile = { ...b, preferred_name: b.preferred_name?.trim() || null }),
    ),
    R('GET', 'nova/memories', () => N().memories),
    R('POST', 'nova/memories', (_m, _q, b) => remember(b.content, b.category, 'told')[0]),
    R('PATCH', 'nova/memories/([^/]+)', ([mid], _q, b) => {
      const note = N().memories.find((m) => m.id === mid) ?? notFound('Memory')
      if (b.content) {
        if (SENSITIVE.test(b.content))
          bad(
            'memory_sensitive',
            "NOVA doesn't remember passwords, keys, codes or payment details.",
          )
        note.source = 'told'
      }
      return Object.assign(
        note,
        Object.fromEntries(Object.entries(b).filter(([, v]) => v !== null && v !== undefined)),
        { updated_at: now() },
      )
    }),
    R('DELETE', 'nova/memories/([^/]+)', ([mid]) => {
      N().memories = N().memories.filter((m) => m.id !== mid)
      return null
    }),
    R('DELETE', 'nova/memories', () => {
      N().memories = []
      return null
    }),
    R('POST', 'nova/messages/([^/]+)/feedback', ([mid], _q, b) => {
      N().feedback[mid] = b.rating
      if (b.rating === -1 && b.comment && profile().learning_enabled)
        remember(`When answering: ${b.comment}`, 'style', 'feedback')
      return null
    }),
  ]
}
